#!/usr/bin/env python3
"""OES 지식 그래프·RAG 카드 → DB 적재 + 기업 서버 미러링 (단방향 스냅숏 동기화).

표준 라이브러리만 쓴다(기업 서버에 추가 패키지 설치가 어려운 경우를 고려). PostgreSQL은 psql로 적재할 SQL 파일을 만든다.

  # 1) 온라인: 공개 사이트에서 받아 SQLite 미러 갱신 (사내 프록시는 HTTPS_PROXY 환경 변수)
  python oes_kg_mirror.py sync --source https://<계정>.github.io/etch-paper-study/research/oes_kg/ --sqlite /srv/oes/oes_kg.sqlite
  # 2) 오프라인(망 분리): 반입 폴더(manifest.json·graph.json·cards.jsonl)에서
  python oes_kg_mirror.py sync --source /mnt/import/oes_kg/ --sqlite /srv/oes/oes_kg.sqlite
  # 3) PostgreSQL: 적재 SQL 생성 → psql로 실행 (스테이징 스키마에 넣고 검사 뒤 원자적 교체)
  python oes_kg_mirror.py pg-sql --source <위와 같음> --out load_oes_kg.sql
  psql "$PGURL" -v ON_ERROR_STOP=1 -f load_oes_kg.sql
  # 4) 반입용 묶음 만들기(인터넷 되는 PC에서) → 사내로 옮김
  python oes_kg_mirror.py bundle --source https://.../research/oes_kg/ --out ./oes_kg_bundle/
  # 5) 상태·질의
  python oes_kg_mirror.py status --sqlite /srv/oes/oes_kg.sqlite
  python oes_kg_mirror.py query --sqlite /srv/oes/oes_kg.sqlite peak 519.8 --tol 0.5
  python oes_kg_mirror.py query --sqlite /srv/oes/oes_kg.sqlite search "SiN 종말점 CO"

원칙: 공개 원본 → 사내 방향으로만 흐른다(사내 데이터는 밖으로 나가지 않는다). 받은 파일은 manifest의 SHA-256·크기·개수와
맞아야 적재하고, 검사에 실패하면 기존 DB를 그대로 둔다. 사내 고유 데이터는 oes_local(PostgreSQL 스키마) / local_* 테이블에 두며 동기화가 덮어쓰지 않는다.
"""
import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

SCHEMA_VERSION = "1"
FILES = ("graph.json", "cards.jsonl")
KEEP_VERSIONS = 3


# ---------- 원본 읽기 ----------
def _fetch(source, name):
    if source.startswith(("http://", "https://")):
        url = source.rstrip("/") + "/" + name
        req = urllib.request.Request(url, headers={"User-Agent": "oes-kg-mirror/1"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()
    return (Path(source) / name).read_bytes()


def load_snapshot(source):
    """manifest를 읽고 파일을 받아 SHA-256·크기를 검증한 뒤 파싱한다. 하나라도 틀리면 예외."""
    man = json.loads(_fetch(source, "manifest.json"))
    if str(man.get("schema_version")) != SCHEMA_VERSION:
        raise SystemExit(f"스키마 버전 불일치: 원본 {man.get('schema_version')} / 이 스크립트 {SCHEMA_VERSION} — 스크립트를 새 버전으로 바꿔야 한다")
    raw = {}
    for name in FILES:
        b = _fetch(source, name)
        exp = man["files"][name]
        if len(b) != exp["bytes"] or hashlib.sha256(b).hexdigest() != exp["sha256"]:
            raise SystemExit(f"무결성 실패: {name} (크기 {len(b)} / 기대 {exp['bytes']}) — 적재하지 않음")
        raw[name] = b
    graph = json.loads(raw["graph.json"])
    cards = [json.loads(l) for l in raw["cards.jsonl"].decode("utf-8").splitlines() if l.strip()]
    validate(man, graph, cards)
    return man, graph, cards, raw


def validate(man, graph, cards):
    ids = {n["id"] for n in graph["nodes"]}
    bad = [e for e in graph["edges"] if e["s"] not in ids or e["t"] not in ids]
    if bad:
        raise SystemExit(f"끊긴 관계 {len(bad)}건 — 적재하지 않음")
    c = man["counts"]
    if (len(graph["nodes"]), len(graph["edges"]), len(cards)) != (c["nodes"], c["edges"], c["cards"]):
        raise SystemExit("개수 불일치(manifest와 다름) — 적재하지 않음")
    if any(x["id"] not in ids for x in cards):
        raise SystemExit("그래프에 없는 노드의 카드가 있음 — 적재하지 않음")


# ---------- 행으로 펼치기 (SQLite·PostgreSQL 공통) ----------
CORE = ("id", "type", "label")


def rows(graph, cards):
    node, edge, pt, rg, card = [], [], [], [], []
    for n in graph["nodes"]:
        props = {k: v for k, v in n.items() if k not in CORE}
        node.append((n["id"], n["type"], n["label"], n.get("decision"), json.dumps(props, ensure_ascii=False)))
        for p in n.get("points", []) or []:
            pt.append((n["id"], n.get("species"), float(p)))
        for lo, hi in n.get("ranges", []) or []:
            rg.append((n["id"], n.get("species"), float(lo), float(hi)))
    for i, e in enumerate(graph["edges"], 1):
        props = {k: v for k, v in e.items() if k not in ("s", "t", "rel")}
        edge.append((i, e["s"], e["t"], e["rel"], json.dumps(props, ensure_ascii=False)))
    for c in cards:
        card.append((c["id"], c["type"], c["title"], c["text"], c.get("decision"),
                     json.dumps(c.get("citations", []), ensure_ascii=False), json.dumps(c.get("neighbors", []), ensure_ascii=False)))
    return node, edge, pt, rg, card


# ---------- SQLite ----------
SQLITE_DDL = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE node (id TEXT PRIMARY KEY, type TEXT NOT NULL, label TEXT NOT NULL, decision TEXT, props TEXT NOT NULL);
CREATE TABLE edge (id INTEGER PRIMARY KEY, s TEXT NOT NULL REFERENCES node(id), t TEXT NOT NULL REFERENCES node(id), rel TEXT NOT NULL, props TEXT NOT NULL);
CREATE TABLE emission_point (node_id TEXT NOT NULL REFERENCES node(id), species TEXT, nm REAL NOT NULL);
CREATE TABLE emission_range (node_id TEXT NOT NULL REFERENCES node(id), species TEXT, lo REAL NOT NULL, hi REAL NOT NULL);
CREATE TABLE card (id TEXT PRIMARY KEY REFERENCES node(id), type TEXT NOT NULL, title TEXT NOT NULL, text TEXT NOT NULL, decision TEXT, citations TEXT NOT NULL, neighbors TEXT NOT NULL);
CREATE VIRTUAL TABLE card_fts USING fts5(id UNINDEXED, title, text, tokenize='unicode61');
CREATE TABLE card_embedding (id TEXT PRIMARY KEY REFERENCES card(id), model TEXT NOT NULL, dim INTEGER NOT NULL, vec BLOB NOT NULL);
CREATE INDEX node_type ON node(type);
CREATE INDEX edge_s ON edge(s, rel);
CREATE INDEX edge_t ON edge(t, rel);
CREATE INDEX ep_nm ON emission_point(nm);
CREATE INDEX er_lo ON emission_range(lo, hi);
"""


def build_sqlite(path, man, graph, cards):
    node, edge, pt, rg, card = rows(graph, cards)
    con = sqlite3.connect(path)
    con.executescript(SQLITE_DDL)
    with con:
        con.executemany("INSERT INTO node VALUES (?,?,?,?,?)", node)
        con.executemany("INSERT INTO edge VALUES (?,?,?,?,?)", edge)
        con.executemany("INSERT INTO emission_point VALUES (?,?,?)", pt)
        con.executemany("INSERT INTO emission_range VALUES (?,?,?,?)", rg)
        con.executemany("INSERT INTO card VALUES (?,?,?,?,?,?,?)", card)
        con.executemany("INSERT INTO card_fts VALUES (?,?,?)", [(c[0], c[2], c[3]) for c in card])
        meta = {"schema_version": SCHEMA_VERSION, "version": man["version"], "source_generated_from": man.get("generated_from", ""),
                "loaded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "manifest": json.dumps(man, ensure_ascii=False)}
        con.executemany("INSERT INTO meta VALUES (?,?)", meta.items())
    check_db(con, man)
    con.close()


def check_db(con, man):
    """적재 뒤 검사: 개수, 관계 무결성, 대표 질의(시험 문항 축약)."""
    c = man["counts"]
    got = tuple(con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("node", "edge", "card"))
    if got != (c["nodes"], c["edges"], c["cards"]):
        raise SystemExit(f"적재 개수 불일치 {got}")
    if con.execute("SELECT count(*) FROM edge WHERE s NOT IN (SELECT id FROM node) OR t NOT IN (SELECT id FROM node)").fetchone()[0]:
        raise SystemExit("적재 후 끊긴 관계")
    for nm, sp in man.get("smoke", []):
        hit = con.execute("SELECT 1 FROM emission_point WHERE species=? AND abs(nm-?)<=0.5 LIMIT 1", (sp, nm)).fetchone()
        if not hit:
            raise SystemExit(f"대표 질의 실패: {nm} nm → {sp}")


def current_version(path):
    if not Path(path).exists():
        return None
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        v = con.execute("SELECT value FROM meta WHERE key='version'").fetchone()
        con.close()
        return v[0] if v else None
    except sqlite3.Error:
        return None


def sync_sqlite(source, path, force=False):
    path = Path(path)
    man, graph, cards, _ = load_snapshot(source)
    cur = current_version(path)
    if cur == man["version"] and not force:
        print(f"최신 상태 (버전 {cur}) — 할 일 없음")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".oes_kg_", suffix=".sqlite", dir=path.parent)
    os.close(fd)
    os.remove(tmp)
    try:
        build_sqlite(tmp, man, graph, cards)          # 스테이징 파일에 적재·검사
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    if path.exists():                                   # 이전 버전 보관 (롤백용)
        vdir = path.parent / "versions"
        vdir.mkdir(exist_ok=True)
        shutil.copy2(path, vdir / f"{path.stem}.{cur or 'unknown'}.sqlite")
        for old in sorted(vdir.glob(f"{path.stem}.*.sqlite"), key=os.path.getmtime)[:-KEEP_VERSIONS]:
            old.unlink()
    os.replace(tmp, path)                               # 원자적 교체
    print(f"갱신: {cur} → {man['version']} · 노드 {man['counts']['nodes']} · 관계 {man['counts']['edges']} · 카드 {man['counts']['cards']}")


# ---------- PostgreSQL (psql로 실행할 SQL 생성) ----------
def _q(v):
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


PG_DDL = """
CREATE TABLE {s}.meta (key text PRIMARY KEY, value text NOT NULL);
CREATE TABLE {s}.node (id text PRIMARY KEY, type text NOT NULL, label text NOT NULL, decision text, props jsonb NOT NULL);
CREATE TABLE {s}.edge (id integer PRIMARY KEY, s text NOT NULL REFERENCES {s}.node(id), t text NOT NULL REFERENCES {s}.node(id), rel text NOT NULL, props jsonb NOT NULL);
CREATE TABLE {s}.emission_point (node_id text NOT NULL REFERENCES {s}.node(id), species text, nm double precision NOT NULL);
CREATE TABLE {s}.emission_range (node_id text NOT NULL REFERENCES {s}.node(id), species text, lo double precision NOT NULL, hi double precision NOT NULL);
CREATE TABLE {s}.card (id text PRIMARY KEY REFERENCES {s}.node(id), type text NOT NULL, title text NOT NULL, text text NOT NULL, decision text,
  citations jsonb NOT NULL, neighbors jsonb NOT NULL,
  tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', title || ' ' || text)) STORED);
CREATE INDEX ON {s}.node(type);
CREATE INDEX ON {s}.edge(s, rel);
CREATE INDEX ON {s}.edge(t, rel);
CREATE INDEX ON {s}.emission_point(nm);
CREATE INDEX ON {s}.emission_range(lo, hi);
CREATE INDEX ON {s}.card USING gin(tsv);
"""


def pg_sql(man, graph, cards):
    node, edge, pt, rg, card = rows(graph, cards)
    s = "oes_kg_staging"
    out = ["\\set ON_ERROR_STOP on", "BEGIN;", f"DROP SCHEMA IF EXISTS {s} CASCADE;", f"CREATE SCHEMA {s};", PG_DDL.format(s=s)]

    def ins(table, rs, casts=()):
        for i in range(0, len(rs), 200):
            vals = ",\n".join("(" + ",".join(_q(v) + (casts[j] if j < len(casts) else "") for j, v in enumerate(r)) + ")" for r in rs[i:i + 200])
            out.append(f"INSERT INTO {s}.{table} VALUES\n{vals};")

    ins("node", node, ("", "", "", "", "::jsonb"))
    ins("edge", edge, ("", "", "", "", "::jsonb"))
    ins("emission_point", pt)
    ins("emission_range", rg)
    ins("card", card, ("", "", "", "", "", "::jsonb", "::jsonb"))
    meta = {"schema_version": SCHEMA_VERSION, "version": man["version"], "manifest": json.dumps(man, ensure_ascii=False)}
    ins("meta", list(meta.items()))
    c = man["counts"]
    # 검사: 개수가 manifest와 다르면 예외 → 트랜잭션 전체 취소, 기존 oes_kg 그대로
    out.append(f"""DO $$ BEGIN
  IF (SELECT count(*) FROM {s}.node) <> {c['nodes']} OR (SELECT count(*) FROM {s}.edge) <> {c['edges']} OR (SELECT count(*) FROM {s}.card) <> {c['cards']}
  THEN RAISE EXCEPTION 'oes_kg 적재 개수 불일치'; END IF;
END $$;""")
    for nm, sp in man.get("smoke", []):
        out.append(f"""DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM {s}.emission_point WHERE species={_q(sp)} AND abs(nm-{nm})<=0.5)
  THEN RAISE EXCEPTION 'oes_kg 대표 질의 실패 {nm}'; END IF; END $$;""")
    out += [
        "-- 원자적 교체: 기존 oes_kg는 oes_kg_prev 로 1개 보관(롤백용), 그보다 오래된 것은 지운다.",
        "-- 사내 고유 데이터는 oes_local 스키마에 두며 이 스크립트는 건드리지 않는다.",
        "DROP SCHEMA IF EXISTS oes_kg_prev CASCADE;",
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname='oes_kg') THEN",
        "  EXECUTE 'ALTER SCHEMA oes_kg RENAME TO oes_kg_prev'; END IF; END $$;",
        f"ALTER SCHEMA {s} RENAME TO oes_kg;",
        "CREATE SCHEMA IF NOT EXISTS oes_local;",
        "COMMIT;",
    ]
    return "\n".join(out) + "\n"


# ---------- 질의 (SQLite) ----------
def q_peak(con, nm, tol):
    sql = """SELECT p.species, p.nm, n.id, n.label, n.decision FROM emission_point p JOIN node n ON n.id=p.node_id
             WHERE p.nm BETWEEN ? AND ? ORDER BY abs(p.nm-?)"""
    return con.execute(sql, (nm - tol, nm + tol, nm)).fetchall()


def q_search(con, text, k=8):
    """RAG 검색 단계: FTS(bm25)로 카드 순위 → 1단계 이웃 카드 덧붙임. 생성(LLM)은 이 결과를 근거로만 쓴다."""
    toks = [t for t in text.replace('"', " ").split() if t]
    if not toks:
        return []
    match = " OR ".join('"' + t + '"' for t in toks)
    hits = con.execute("SELECT id, bm25(card_fts) FROM card_fts WHERE card_fts MATCH ? ORDER BY bm25(card_fts) LIMIT ?", (match, k)).fetchall()
    out = []
    for cid, score in hits:
        c = con.execute("SELECT id, title, text, decision, citations FROM card WHERE id=?", (cid,)).fetchone()
        out.append({"id": c[0], "score": round(-score, 3), "title": c[1], "decision": c[3], "citations": json.loads(c[4]), "text": c[2]})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("sync"); a.add_argument("--source", required=True); a.add_argument("--sqlite", required=True); a.add_argument("--force", action="store_true")
    a = sub.add_parser("pg-sql"); a.add_argument("--source", required=True); a.add_argument("--out", required=True)
    a = sub.add_parser("bundle"); a.add_argument("--source", required=True); a.add_argument("--out", required=True)
    a = sub.add_parser("status"); a.add_argument("--sqlite", required=True)
    a = sub.add_parser("query"); a.add_argument("--sqlite", required=True); a.add_argument("kind", choices=["peak", "search"]); a.add_argument("arg")
    a.add_argument("--tol", type=float, default=0.5)
    args = ap.parse_args()
    if args.cmd == "sync":
        sync_sqlite(args.source, args.sqlite, args.force)
    elif args.cmd == "pg-sql":
        man, graph, cards, _ = load_snapshot(args.source)
        Path(args.out).write_text(pg_sql(man, graph, cards), encoding="utf-8")
        print(f"작성: {args.out} (버전 {man['version']}) — psql \"$PGURL\" -v ON_ERROR_STOP=1 -f {args.out}")
    elif args.cmd == "bundle":
        man, _, _, raw = load_snapshot(args.source)          # 받으면서 검증까지 한 뒤 저장
        o = Path(args.out); o.mkdir(parents=True, exist_ok=True)
        for name, b in raw.items():
            (o / name).write_bytes(b)
        (o / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
        shutil.copy2(__file__, o / Path(__file__).name)
        print(f"묶음: {o} (버전 {man['version']}) — 이 폴더를 사내로 옮긴 뒤 sync --source <폴더>")
    elif args.cmd == "status":
        con = sqlite3.connect(f"file:{args.sqlite}?mode=ro", uri=True)
        meta = dict(con.execute("SELECT key, value FROM meta"))
        print(json.dumps({k: v for k, v in meta.items() if k != "manifest"}, ensure_ascii=False, indent=1))
        for t in ("node", "edge", "card", "emission_point", "card_embedding"):
            print(t, con.execute(f"SELECT count(*) FROM {t}").fetchone()[0])
    elif args.cmd == "query":
        con = sqlite3.connect(f"file:{args.sqlite}?mode=ro", uri=True)
        res = q_peak(con, float(args.arg), args.tol) if args.kind == "peak" else q_search(con, args.arg)
        print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
