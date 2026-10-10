"""SNU PAL 질의응답 추출 결과(astra JSONL) → DB 표 + 자동 검사 + 공개용 JSON.

사용법:
    python tools/snupal_merge.py load [--by 모델] <추출.jsonl>...   # DB(extract_*)에 넣기, 추출 모델 기록
    python tools/snupal_merge.py check                 # 자동 검사 (이름 노출·원문 복사·누락)
    python tools/snupal_merge.py export <out.json>     # 공개용 (재서술 + 링크만)

공개 JSON에는 원문 본문·작성자 이름을 넣지 않는다.
"""
import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "snupal" / "snupal.db"
SCHEMA = """
create table if not exists extract_posts(doc_id integer primary key, answer_type text, topics text, question text, raw text);
create table if not exists extract_knowledge(id integer primary key autoincrement, doc_id integer, ord integer, point text, condition text);
create table if not exists extract_terms(id integer primary key autoincrement, doc_id integer, ko text, en text, def text);
"""


def db():
    c = sqlite3.connect(DB); c.executescript(SCHEMA)
    if "extractor" not in [r[1] for r in c.execute("pragma table_info(extract_posts)")]:
        c.execute("alter table extract_posts add column extractor text")
    return c


def load(files, by=None):
    c = db(); n = bad = 0
    valid = {r[0] for r in c.execute("select doc_id from posts")}
    for f in files:
        for line in Path(f).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line.startswith("{"): continue
            try: o = json.loads(line)
            except ValueError: bad += 1; continue
            d = o.get("doc_id")
            if d not in valid: bad += 1; continue
            c.execute("delete from extract_knowledge where doc_id=?", (d,)); c.execute("delete from extract_terms where doc_id=?", (d,))
            c.execute("insert or replace into extract_posts(doc_id, answer_type, topics, question, raw, extractor) values(?,?,?,?,?,?)",
                      (d, o.get("answer_type"), json.dumps(o.get("topics", []), ensure_ascii=False), o.get("question"), line, by))
            for i, k in enumerate(o.get("knowledge") or []):
                if isinstance(k, dict) and k.get("point"):
                    c.execute("insert into extract_knowledge(doc_id, ord, point, condition) values(?,?,?,?)", (d, i, k["point"], k.get("condition")))
            for t in o.get("terms") or []:
                if isinstance(t, dict) and t.get("ko"):
                    c.execute("insert into extract_terms(doc_id, ko, en, def) values(?,?,?,?)", (d, t["ko"].strip(), (t.get("en") or "").strip() or None, t.get("def")))
            n += 1
    c.commit(); print(f"적재 {n}개 글, 버린 줄 {bad}")


def copied(s, src, k=30):
    """s의 길이 k 조각이 원문에 그대로 있으면 True (공백 정규화 후). 원문 연속 복사 검사."""
    a, b = re.sub(r"\s+", " ", s), re.sub(r"\s+", " ", src)
    return any(a[i:i + k] in b for i in range(0, max(1, len(a) - k + 1), 5)) if len(a) >= k else False


def check():
    c = db(); q = lambda s, *p: c.execute(s, p).fetchall()
    total = q("select count(*) from posts")[0][0]
    done = {r[0] for r in q("select doc_id from extract_posts")}
    missing = [r[0] for r in q("select doc_id from posts") if r[0] not in done]
    leaks, copies = [], []
    texts = {}
    for d, qt in q("select doc_id, question_text from posts"):
        texts[d] = (qt or "") + "\n" + "\n".join(r[0] or "" for r in q("select text from comments where doc_id=?", d))
    # 작성자 이름 중, 일반 단어처럼 여러 글 본문에 나오는 것(예: 닉네임 '플라' ⊂ '플라즈마')은 제외
    alltext = list(texts.values())
    names = {r[0] for r in q("select author from posts union select author from comments") if r[0] and len(r[0]) >= 2} - {"관리자", "PAL Archive"}
    names = {nm for nm in names if sum(nm in t for t in alltext) <= 3}
    names = {nm for nm in names if not re.fullmatch(r"[A-Za-z ]+", nm)}
    # 앞 글자가 한글이면 다른 단어의 일부 (예: '프로브로' 속 '브로') — 이름으로 보지 않음
    name_re = re.compile(r"(?<![가-힣])(?:" + "|".join(map(re.escape, sorted(names, key=len, reverse=True))) + ")") if names else None
    for d, s in q("select doc_id, point from extract_knowledge") + q("select doc_id, question from extract_posts") + q("select doc_id, def from extract_terms"):
        if not s: continue
        m = name_re.search(s) if name_re else None
        if m: leaks.append((d, m.group(0)))
        if copied(s, texts.get(d, "")): copies.append((d, s[:60]))
    at = dict(q("select answer_type, count(*) from extract_posts group by 1"))
    print(f"추출 {len(done)}/{total}, 누락 {len(missing)} {missing[:20]}")
    print("답변 유형:", at, "/ 추출 모델:", dict(q("select extractor, count(*) from extract_posts group by 1")))
    print("지식", q("select count(*) from extract_knowledge")[0][0], "/ 용어(중복 포함)", q("select count(*) from extract_terms")[0][0],
          "/ 고유 용어", q("select count(distinct lower(ko)) from extract_terms")[0][0])
    print(f"이름 노출 의심 {len(leaks)}: {leaks[:10]}")
    print(f"원문 30자 이상 연속 복사 {len(copies)}: {copies[:8]}")
    return missing, leaks, copies


# 사이트 기존 표기에 맞춘 대표 한국어 (영문 키 → 한국어)
CANON = {
    "self bias": "자기 바이어스", "dc self bias": "자기 바이어스", "floating potential": "부유 전위", "impedance matching": "임피던스 정합",
    "radical": "라디칼", "debye length": "Debye 길이", "debye shielding": "Debye 차폐", "skin depth": "표피 깊이", "global model": "전역 모델",
    "capacitively coupled plasma": "용량성 결합 플라즈마", "ccp": "용량성 결합 플라즈마", "inductively coupled plasma": "유도 결합 플라즈마",
    "icp": "유도 결합 플라즈마", "secondary electron": "이차 전자", "secondary electron emission": "이차 전자 방출",
    "mean free path": "평균 자유 행로", "standing wave": "정재파", "electronegative plasma": "전기음성 플라즈마",
    "paschen's law": "파셴 법칙", "paschen curve": "파셴 곡선", "bohm velocity": "Bohm 속도", "bohm criterion": "Bohm 기준",
    "rate constant": "반응 속도 상수", "edge ring": "에지 링", "dbd": "유전체 장벽 방전", "dielectric barrier discharge": "유전체 장벽 방전",
    "electron temperature": "전자 온도", "oes": "광방출 분광", "optical emission spectroscopy": "광방출 분광", "matcher": "정합기",
    "remote plasma source": "원격 플라즈마 소스", "rps": "원격 플라즈마 소스", "remote plasma": "원격 플라즈마", "lorentz force": "로런츠 힘",
    "plasma potential": "플라즈마 전위", "ion energy distribution": "이온 에너지 분포", "iedf": "이온 에너지 분포 함수",
    "electron energy distribution function": "전자 에너지 분포", "eedf": "전자 에너지 분포", "langmuir probe": "랭뮤어 탐침",
    "sheath": "쉬스", "endpoint detection": "식각 종말점 검출", "residence time": "체류 시간", "breakdown": "절연 파괴",
}
# 본문 표기 고침 (잘못된 음차)
FIXES = [(r"패션\s*곡선", "파셴 곡선"), (r"파[센쉔]", "파셴"), (r"[디드]바이\s*(길이|차폐)", r"Debye "), (r"라디컬", "라디칼"), (r"(?<![가-힣])시스(?!템)", "쉬스")]


def fix_text(s):
    if not s: return s
    for a, b in FIXES: s = re.sub(a, b, s)
    return s


def en_key(en):
    k = re.sub(r"\s*[\(\[].*?[\)\]]", "", en or "").lower().replace("-", " ").replace("’", "'").strip()
    return re.sub(r"\s+", " ", k)


def norm(s):
    return re.sub(r"[\s·\-_()（）]", "", (s or "").lower())


def export(out):
    c = db(); q = lambda s, *p: c.execute(s, p).fetchall()
    posts = []
    for d, url, title, cat, date, at, topics, qs, by in q("""select p.doc_id, p.url, p.title, p.category, p.date, e.answer_type, e.topics, e.question, e.extractor
                                                         from posts p join extract_posts e using(doc_id) order by p.doc_id desc"""):
        posts.append({"id": d, "url": url, "title": title, "cat": cat, "date": date, "type": at, "by": by, "topics": [fix_text(x) for x in json.loads(topics or "[]")],
                      "q": fix_text(qs), "k": [{"p": fix_text(p), "c": fix_text(cd)} for p, cd in q("select point, condition from extract_knowledge where doc_id=? order by ord", d)]})
    # 용어 병합: 영문이 있으면 영문 기준(같은 개념의 한국어 표기 차이를 합침), 없으면 한국어 기준.
    # 대표 한국어는 사이트 기존 표기(CANON) → 없으면 가장 많이 쓰인 표기. 나머지는 '다른 표기'로 남겨 검색되게 한다.
    groups = defaultdict(list)
    for d, ko, en, df in q("select doc_id, ko, en, def from extract_terms"):
        ko, df = fix_text(ko), fix_text(df)
        key = "en:" + en_key(en) if en and en_key(en) else "ko:" + norm(ko)
        groups[key].append((d, ko, en, df))
    terms = []
    for k, rows in groups.items():
        kos = defaultdict(int); ens = defaultdict(int)
        for _, ko, en, _ in rows:
            kos[ko] += 1
            if en: ens[en] += 1
        main = CANON.get(k[3:]) if k.startswith("en:") else None
        main = main or max(kos, key=kos.get)
        docs = sorted({r[0] for r in rows}, reverse=True)
        alt = sorted({x for x in kos if norm(x) != norm(main)})
        terms.append({"ko": main, "en": max(ens, key=ens.get) if ens else None, "alt": alt, "n": len(docs),
                      "defs": [{"d": r[3], "id": r[0]} for r in rows if r[3]][:4], "docs": docs})
    terms.sort(key=lambda t: (-t["n"], t["ko"]))
    meta = {"source": "서울대학교 플라즈마 응용 연구실(SNU PAL) 질의응답 게시판", "board": "https://snupal.snu.ac.kr/qna/list/",
            "posts": len(posts), "fetched": q("select min(date(fetched_at)), max(date(fetched_at)) from posts")[0],
            "period": q("select min(date), max(date) from posts")[0]}
    Path(out).write_text(json.dumps({"meta": meta, "posts": posts, "terms": terms}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"내보냄: 글 {len(posts)}, 용어 {len(terms)} → {out}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1]
    if cmd == "load":
        a = sys.argv[2:]
        by = a[a.index("--by") + 1] if "--by" in a else None
        load([x for i, x in enumerate(a) if x != "--by" and (i == 0 or a[i - 1] != "--by")], by)
    elif cmd == "check": check()
    elif cmd == "export": export(sys.argv[2])
