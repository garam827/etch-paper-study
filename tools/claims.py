"""주장 장부(claim ledger) 도구 — 검증 규칙을 모델 판단이 아니라 코드로 강제한다.

장부: ledger/<주제>.json   (비공개, .gitignore)
검증 보고: ledger/<주제>.verify.jsonl (추가만 하는 기록. 작성자가 고치지 않는다)

명령:
  python tools/claims.py lint    <장부>            # 스키마·단위·날짜·조건 검사
  python tools/claims.py blind   <장부> [ID…]      # 검증자에게 줄 입력 (작성자 메모·판정 제외)
  python tools/claims.py record  <장부> <보고.json> # 검증자 보고를 그대로 추가 (해시 고정)
  python tools/claims.py gate    <장부>            # 채택 판정 (규칙표에 따라 자동)
  python tools/claims.py summary <장부>            # 사람용 요약 표 (Markdown)

핵심 규칙
- 주장 내용 해시(statement·scope·quantity·event·evidence 위치)가 바뀌면 이전 검증은 무효.
- 검증 보고는 verifier_run ≠ author_run 이어야 유효.
- 채택(adopt)은 gate만 결정한다. 작성자가 decision 필드를 직접 바꾸지 않는다.
"""
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

TIERS = {"T1", "T2", "T3", "T4", "T5"}
RELATIONS = {"supports", "partially_supports", "refutes", "unrelated", "unassessed"}
VERDICTS = {"supported", "partially_supported", "refuted", "conflicting", "insufficient"}
ACCESS = {"full_text", "abstract_only", "metadata_only", "secondary"}
ENERGY_METRICS = re.compile(r"energy|에너지", re.I)


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def content_hash(c):
    core = {k: c.get(k) for k in ("statement", "scope", "quantity", "event")}
    core["evidence"] = [{k: e.get(k) for k in ("doi", "url", "locator")} for e in c.get("evidence", [])]
    return hashlib.sha256(json.dumps(core, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]


def reports(ledger_path):
    p = Path(ledger_path).with_suffix(".verify.jsonl")
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


# ---------------------------------------------------------------- lint
def lint(led):
    probs = []
    ids = set()
    for c in led["claims"]:
        cid = c.get("claim_id", "?")
        P = lambda lvl, msg: probs.append((cid, lvl, msg))
        if cid in ids: P("error", "claim_id 중복")
        ids.add(cid)
        for f in ("statement", "as_of", "risk", "evidence"):
            if not c.get(f): P("error", f"필수 필드 없음: {f}")
        s = c.get("statement", "")
        q = c.get("quantity") or {}
        # 단위: 입자 에너지는 eV, 전압은 V
        if q.get("metric") and ENERGY_METRICS.search(q["metric"]) and q.get("unit") in ("V", "kV", "MV"):
            P("error", f"에너지 지표({q['metric']})에 전압 단위 {q['unit']} → eV/keV")
        if re.search(r"\d\s*kV\s*(Ar|이온|ion|O|Cl|F)", s) or re.search(r"이온 에너지[^.]*\d\s*V\b", s):
            P("error", "문장에 이온 에너지를 전압 단위(V/kV)로 표기")
        if q.get("value") is not None and not q.get("unit") and q.get("metric") not in ("ratio", "count", "비", "개수"):
            P("warn", "수치에 단위 없음")
        # 수치가 있으면 조건·가정이 있어야 함 (교과서 모델 수치의 일반화 방지)
        sc = c.get("scope") or {}
        if q.get("value") is not None and not (sc.get("conditions") or sc.get("assumptions")):
            P("warn", "수치에 적용 조건·모델 가정이 없음 (일반값처럼 읽힘)")
        # 날짜: 사건 종류·실제/계획 구분
        ev = c.get("event") or {}
        if ev.get("date") and not (ev.get("type") and ev.get("planned_or_actual")):
            P("warn", "사건 날짜에 사건 종류(발표/양산/출하…)나 계획·실제 구분이 없음")
        if re.search(r"(20\d\d)년", s) and not ev.get("date"):
            P("warn", "문장에 연도가 있는데 event.date 없음 (발표일·출시일·분석일 혼동 위험)")
        # 노드 이름을 치수로 쓰지 않기
        if sc.get("node_label") and q.get("metric") in ("gate_length", "pitch") and str(q.get("value")) in sc["node_label"]:
            P("warn", "노드 이름의 숫자를 실제 치수로 쓴 것 같음")
        for e in c.get("evidence", []):
            if e.get("tier") not in TIERS: P("error", f"근거 {e.get('source_id')}: tier 없음/잘못됨")
            if not (e.get("doi") or e.get("url")): P("error", f"근거 {e.get('source_id')}: DOI·URL 없음")
            if e.get("access_level") not in ACCESS: P("error", f"근거 {e.get('source_id')}: access_level 필요 {sorted(ACCESS)}")
            if e.get("relation") not in RELATIONS: P("error", f"근거 {e.get('source_id')}: relation 잘못됨")
            if not e.get("origin_group"): P("warn", f"근거 {e.get('source_id')}: origin_group 없음 (같은 보도자료 재인용 구분 불가)")
            if e.get("access_level") == "full_text" and not e.get("locator"): P("warn", f"근거 {e.get('source_id')}: 원문을 봤다면 위치(locator) 필요")
        if c.get("decision", {}).get("status") == "adopt" and c.get("decision", {}).get("by") != "gate":
            P("error", "decision=adopt 를 gate가 아닌 쪽이 기록함")
    return probs


# ---------------------------------------------------------------- blind
def blind(led, only=None):
    out = []
    for c in led["claims"]:
        if only and c["claim_id"] not in only:
            continue
        out.append({
            "claim_id": c["claim_id"], "content_hash": content_hash(c), "statement": c["statement"],
            "as_of": c["as_of"], "scope": c.get("scope"), "quantity": c.get("quantity"), "event": c.get("event"),
            # 작성자가 고른 근거의 위치만 준다 (판단·발췌·relation은 주지 않음)
            "evidence_locators": [{"source_id": e["source_id"], "doi": e.get("doi"), "url": e.get("url"),
                                   "locator": e.get("locator")} for e in c.get("evidence", [])],
        })
    return out


# ---------------------------------------------------------------- record
def record(ledger_path, report_path):
    led = load(ledger_path)
    rep = load(report_path)
    items = rep if isinstance(rep, list) else rep.get("verdicts", [rep])
    by_id = {c["claim_id"]: c for c in led["claims"]}
    out = Path(ledger_path).with_suffix(".verify.jsonl")
    n = 0
    with out.open("a", encoding="utf-8") as f:
        for v in items:
            c = by_id.get(v.get("claim_id"))
            if c is None:
                print("무시(없는 ID):", v.get("claim_id")); continue
            if v.get("verdict") not in VERDICTS:
                print("무시(판정 값 잘못됨):", v.get("claim_id"), v.get("verdict")); continue
            if v.get("content_hash") != content_hash(c):
                print("무시(검증 후 주장이 바뀜 — 다시 검증 필요):", v["claim_id"]); continue
            v = dict(v)
            v["recorded_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            v["report_hash"] = hashlib.sha256(json.dumps(v, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]
            f.write(json.dumps(v, ensure_ascii=False) + "\n"); n += 1
    print(f"기록 {n}건 → {out.name}")


# ---------------------------------------------------------------- gate
def gate(ledger_path):
    led = load(ledger_path)
    reps = reports(ledger_path)
    lint_err = {cid for cid, lvl, _ in lint(led) if lvl == "error"}
    res = []
    for c in led["claims"]:
        cid, h = c["claim_id"], content_hash(c)
        valid = [r for r in reps if r["claim_id"] == cid and r["content_hash"] == h
                 and r.get("verifier_run") and r.get("verifier_run") != c.get("author_run")]
        tiers = {e["tier"] for e in c.get("evidence", [])}
        origins = {e.get("origin_group") for e in c.get("evidence", []) if e.get("relation") in ("supports", "partially_supports")}
        origins |= {o for r in valid for o in r.get("independent_origins", [])}
        if cid in lint_err:
            d, why = "hold", "lint 오류"
        elif not valid:
            stale = any(r["claim_id"] == cid for r in reps)
            d, why = "hold", "검증 후 주장이 바뀌어 재검증 필요" if stale else "독립 검증 없음"
        else:
            vs = [r["verdict"] for r in valid]
            if "refuted" in vs:
                d, why = "reject", "검증자가 반박"
            elif "conflicting" in vs or len(set(vs)) > 1:
                d, why = "hold", "판정 충돌 — 조건·정의·시점 차이 조사 필요 (jev로 종결하지 않음)"
            elif "insufficient" in vs:
                d, why = "hold", "근거 부족"
            elif tiers <= {"T5"}:
                d, why = "reject", "루머·커뮤니티 근거만 있음 (탐색 단서로만)"
            elif "partially_supported" in vs:
                d, why = "conditional", "부분 지지 — 조건을 문장에 넣어야 함"
            elif c.get("risk") == "high" and len(origins - {None}) < 2:
                d, why = "conditional", "고위험 주장인데 독립 근거 계보 1개 (단일 출처 표시)"
            elif not (tiers & {"T1", "T2", "T3"}):
                d, why = "conditional", "언론 근거만 — 원근거 추적 필요"
            else:
                d, why = "adopt", "독립 검증 지지"
        res.append({"claim_id": cid, "decision": d, "reason": why, "valid_reports": len(valid)})
    return res


def summary(ledger_path):
    led = load(ledger_path)
    g = {r["claim_id"]: r for r in gate(ledger_path)}
    reps = reports(ledger_path)
    lines = ["| ID | 주장 | 근거 등급 | 검증 | 판정 | 이유 |", "|---|---|---|---|---|---|"]
    for c in led["claims"]:
        v = [r["verdict"] for r in reps if r["claim_id"] == c["claim_id"] and r["content_hash"] == content_hash(c)]
        tiers = ",".join(sorted({e["tier"] for e in c.get("evidence", [])}))
        r = g[c["claim_id"]]
        lines.append(f"| {c['claim_id']} | {c['statement']} | {tiers} | {'/'.join(v) or '-'} | {r['decision']} | {r['reason']} |")
    return "\n".join(lines)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(2)
    cmd, path = sys.argv[1], sys.argv[2]
    if cmd == "lint":
        p = lint(load(path))
        for cid, lvl, msg in p: print(f"[{lvl}] {cid}: {msg}")
        print(f"오류 {sum(l == 'error' for _, l, _ in p)}, 경고 {sum(l == 'warn' for _, l, _ in p)}")
        sys.exit(1 if any(l == "error" for _, l, _ in p) else 0)
    elif cmd == "blind":
        print(json.dumps(blind(load(path), set(sys.argv[3:]) or None), ensure_ascii=False, indent=1))
    elif cmd == "record":
        record(path, sys.argv[3])
    elif cmd == "gate":
        print(json.dumps(gate(path), ensure_ascii=False, indent=1))
    elif cmd == "summary":
        print(summary(path))
    else:
        print(__doc__); sys.exit(2)


if __name__ == "__main__":
    main()
