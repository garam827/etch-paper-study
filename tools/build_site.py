"""사이트 생성: kb/ 원본 → research/ 결과물

    python tools/build_site.py            # 생성
    python tools/build_site.py --check    # 생성 결과가 커밋된 파일과 같은지만 확인 (다르면 종료 코드 1)

원본(손으로 고치는 곳)과 결과물(고치지 않는 곳):
  kb/graph/{types,nodes,edges,sources}.json + tools/templates/a20_etch_knowledge_graph.html
      → research/a20_etch_knowledge_graph.html
  kb/pages.json + tools/templates/index.html → index.html (목차·학습 경로·검색)
  kb/snupal/{page,topics}.json → research/snupal_qna_knowledge.html   (tools/snupal_page.py)
  OES 페이지는 별도 비공개 저장소 데이터가 필요해 여기서 만들지 않는다 → tools/oes_page.py (CLAUDE.md 참고)
그 밖의 페이지(보고서·노트·3D·기록)는 HTML 자체가 원본이다.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import snupal_page  # noqa: E402

KB = ROOT / "kb"


def load(p):
    return json.loads((KB / p).read_text(encoding="utf-8"))


def js_list(rows):
    return "[\n" + ",\n".join("  " + json.dumps(r, ensure_ascii=False) for r in rows) + ",\n]"


def js_obj(d, multiline=True):
    if not multiline:
        return json.dumps(d, ensure_ascii=False, separators=(",", ":"))
    return "{\n" + "".join(f"  {json.dumps(k, ensure_ascii=False)}: {json.dumps(v, ensure_ascii=False)},\n" for k, v in d.items()) + "}"


def check_graph(types, nodes, edges, src):
    errs, ids = [], [n["id"] for n in nodes]
    idset = set(ids)
    if len(ids) != len(idset):
        errs.append("중복 노드 id: " + ", ".join(sorted({i for i in ids if ids.count(i) > 1})))
    for n in nodes:
        if n["type"] not in types["types"]:
            errs.append(f'{n["id"]}: 없는 분류 {n["type"]}')
        if n.get("area") not in types["area_labels"]:
            errs.append(f'{n["id"]}: 없는 영역 {n.get("area")}')
        errs += [f'{n["id"]}: 없는 출처 {k}' for k in n.get("src", []) if k not in src]
    for x in edges:
        for end in (x["from"], x["to"]):
            if end not in idset:
                errs.append(f'관계 {x["from"]}>{x["to"]}: 없는 노드 {end}')
    return errs


def build_graph():
    types, nodes, edges, src = load("graph/types.json"), load("graph/nodes.json"), load("graph/edges.json"), load("graph/sources.json")
    errs = check_graph(types, nodes, edges, src)
    if errs:
        raise SystemExit("그래프 원본 오류:\n  " + "\n  ".join(errs))
    blocks = {
        "TYPES": "{\n" + "".join(f"  {k}: {json.dumps(v, ensure_ascii=False)},\n" for k, v in types["types"].items()) + "}",
        "NODES": js_list([[n["id"], n["name"], n["en"], n["type"], n["desc"], n["etch"]] for n in nodes]),
        "EDGES": js_list([[x["from"], x["to"], x["label"]] for x in edges]),
        "SRC": js_obj({k: [v["title"], v["url"]] for k, v in src.items()}),
        "SOURCES": js_obj({n["id"]: n["src"] for n in nodes if n.get("src")}),
        "EDGE_SRC": js_obj({f'{x["from"]}>{x["to"]}': x["posts"] for x in edges if x.get("posts")}, False),
        "AREA_LABEL": js_obj(types["area_labels"], False),
        "AREA": js_obj({n["id"]: n["area"] for n in nodes}, False),
    }
    page = (ROOT / "tools/templates/a20_etch_knowledge_graph.html").read_text(encoding="utf-8")
    for k, v in blocks.items():
        page = page.replace(f"__KB_{k}__", v)
    if "__KB_" in page:
        raise SystemExit("템플릿에 채우지 못한 자리가 남음")
    print(f"그래프: 노드 {len(nodes)} · 관계 {len(edges)} · 출처 {len(src)}")
    return page


def build_index():
    from html import escape as e
    cfg, nodes = load("pages.json"), load("graph/nodes.json")
    pages = {p["href"]: p for p in cfg["pages"]}
    bad = [h for s in cfg["path"] for h in s["pages"] if h not in pages]
    bad += [p["href"] for p in cfg["pages"] if p["section"] not in {s["id"] for s in cfg["sections"]}]
    bad += [p["href"] for p in cfg["pages"] if not (ROOT / p["href"]).exists()]
    if bad:
        raise SystemExit("목차 원본 오류: " + ", ".join(bad))

    def item(p):
        tags = ([f'<span class="tag etch">{e(p["etch_tag"])}</span>'] if p.get("etch_tag") else []) + \
               [f'<span class="tag">{e(t)}</span>' for t in p["tags"] if t != p.get("etch_tag")] + \
               ([f'<span class="tag">{p["date"]}</span>'] if p.get("date") else [])
        return (f'    <a class="item" href="{e(p["href"])}">\n      <h3>{e(p["title"])}</h3>\n      <p>{e(p["desc"])}</p>\n'
                f'      <div class="tags">{"".join(tags)}</div>\n      <span class="go">{e(p["go"])}</span>\n    </a>\n')

    secs = []
    for s in cfg["sections"]:
        ps = sorted((p for p in cfg["pages"] if p["section"] == s["id"]), key=lambda p: p.get("date") or "", reverse=True)
        secs.append(f'\n  <h2 id="s-{s["id"]}">{e(s["title"])}</h2>\n  <p class="sdesc">{e(s["desc"])}</p>\n  <div class="list">\n{"".join(item(p) for p in ps)}  </div>\n')
    toc = "".join(f'<a href="#s-{s["id"]}">{e(s["title"])}</a>' for s in cfg["sections"])
    path = "".join(f'<li><b>{e(s["title"])}</b>' + "".join(f'<a href="{e(h)}">{e(pages[h]["title"])}</a>' for h in s["pages"]) + "</li>"
                   for s in cfg["path"])
    idx = [{"t": p["title"], "u": p["href"], "c": "자료", "d": "", "p": 0,
            "k": " ".join([p["title"], p["desc"], *p["tags"], *p.get("keywords", [])]).lower()} for p in cfg["pages"]]
    idx += [{"t": f'{n["name"]} ({n["en"]})' if n["en"] and n["en"] != n["name"] else n["name"],
             "u": f'research/a20_etch_knowledge_graph.html#{n["id"]}', "c": "용어 · 지식 그래프",
             "d": n["desc"][:90] + ("…" if len(n["desc"]) > 90 else ""), "p": 1,
             "k": " ".join([n["name"], n["en"] or ""]).lower()} for n in nodes]
    blob = json.dumps(idx, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    page = (ROOT / "tools/templates/index.html").read_text(encoding="utf-8")
    for k, v in {"__TOC__": toc, "__PATH__": path, "__SECTIONS__": "".join(secs).rstrip("\n"), "__INDEX__": blob}.items():
        page = page.replace(k, v)
    print(f"목차: 자료 {len(cfg['pages'])} · 영역 {len(cfg['sections'])} · 검색 항목 {len(idx)}")
    return page


def build_claims():
    from html import escape as e
    sets = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((KB / "claims").glob("*.json"))]
    claims = [c for s in sets for c in s["claims"]]
    PAGE = {"a20": ("Apple A20 (TSMC 2nm) 식각 공정 보고서", "tsmc_n2_a20_etch_report.html"),
            "graph": ("식각 지식 그래프 · 용어집", "a20_etch_knowledge_graph.html")}
    DEC = {"adopt": ("채택", "ok"), "conditional": ("조건부 채택", "cond"), "hold": ("보류", "hold"), "reject": ("제외", "rej")}
    VER = {"supported": "지지", "partially_supported": "부분 지지", "refuted": "반박", "conflicting": "충돌", "insufficient": "확인 불가"}
    n = {k: sum(c["decision"] == k for c in claims) for k in DEC}
    secs = []
    for key, (title, href) in PAGE.items():
        rows = []
        for c in (c for c in claims if c["page"] == key):
            lab, cls = DEC[c["decision"]]
            cond = f'<p class="c"><b>조건</b> {e(c["conditions"])}</p>' if c["conditions"] else ""
            links = " ".join(f'<a href="{e(u)}" target="_blank" rel="noopener">출처 {i}</a>' for i, u in enumerate(c["checked"], 1))
            rows.append(f'<div class="cl" id="{c["id"]}"><div class="h"><span class="id">{c["id"]}</span>'
                        f'<span class="b {cls}">{lab}</span><span class="v">검증: {VER.get(c["verdict"], "—")} · 검토일 {c["reviewed"]}</span></div>'
                        f'<p class="s">{e(c["statement"])}</p>{cond}<p class="n">{e(c["note"])}</p>'
                        f'<p class="r">채택 판정 이유: {e(c["reason"])}{" · " + links if links else ""}</p></div>')
        secs.append(f'<h2>{e(title)} <a class="src" href="{href}">페이지 열기 →</a></h2>{"".join(rows)}')
    page = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>핵심 주장 검증 현황</title>
<style>
  :root {{ --bg:#f7f8fb; --card:#fff; --ink:#1f2937; --muted:#6b7280; --line:#e5e7eb; --accent:#2563eb; }}
  * {{ box-sizing:border-box; }}
  html {{ color-scheme: light; }}
  body {{ margin:0; background:var(--bg); color:var(--ink); font:15px/1.7 "Pretendard","Malgun Gothic","Apple SD Gothic Neo",system-ui,sans-serif; }}
  .wrap {{ max-width:900px; margin:0 auto; padding:40px 16px 80px; }}
  h1 {{ font-size:28px; margin:0 0 6px; }}
  h2 {{ font-size:20px; margin:36px 0 10px; padding-bottom:6px; border-bottom:2px solid var(--line); }}
  h2 .src {{ font-size:13px; font-weight:600; margin-left:8px; }}
  a {{ color:var(--accent); }}
  .sub, .n, .r, .v {{ color:var(--muted); }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; margin:16px 0; }}
  .kpi {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:12px 16px; }}
  .kpi b {{ display:block; font-size:22px; }} .kpi span {{ color:var(--muted); font-size:13px; }}
  .cl {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:12px 18px; margin:10px 0; scroll-margin-top:16px; }}
  .cl:target {{ border-color:var(--accent); box-shadow:0 0 0 2px #bfdbfe; }}
  .h {{ display:flex; flex-wrap:wrap; gap:8px; align-items:center; font-size:13px; }}
  .id {{ font-weight:700; font-family:ui-monospace,Consolas,monospace; }}
  .b {{ font-weight:700; padding:1px 10px; border-radius:999px; font-size:12px; }}
  .b.ok {{ background:#dcfce7; color:#166534; }} .b.cond {{ background:#fef3c7; color:#92400e; }}
  .b.hold {{ background:#f3f4f6; color:#4b5563; }} .b.rej {{ background:#fee2e2; color:#991b1b; }}
  .s {{ margin:6px 0 4px; font-weight:600; }}
  .c {{ margin:4px 0; font-size:14px; background:#fffbeb; border-radius:8px; padding:6px 10px; }}
  .n, .r {{ margin:4px 0 0; font-size:13.5px; }}
  .r a {{ margin-right:6px; }}
  .box {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:12px 18px; font-size:14px; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>핵심 주장 검증 현황</h1>
  <p class="sub"><a href="../index.html">← 목차</a> · <a href="semi_research_system.html">리서치 검증 체계</a></p>
  <p>초기 결과물(A20 보고서, 지식 그래프)에서 결론을 좌우하는 수치·날짜·비교 주장 {len(claims)}개를 골라, 작성 과정을 모르는 검증 에이전트가 원문과 다시 대조했다. 채택 여부는 규칙(gate)이 정한다.</p>
  <div class="grid">
    <div class="kpi"><b>{len(claims)}</b><span>검증한 주장</span></div>
    <div class="kpi"><b>{n["adopt"]}</b><span>채택</span></div>
    <div class="kpi"><b>{n["conditional"]}</b><span>조건부 채택</span></div>
    <div class="kpi"><b>{n["hold"] + n["reject"]}</b><span>보류·제외</span></div>
  </div>
  <div class="box"><b>읽는 법</b> — <b>채택</b>: 원문이 지지함. <b>조건부 채택</b>: 맞지만 근거가 회사 발표 한 곳뿐이거나, 원문 범위에 맞추려면 "조건"을 붙여 읽어야 함. 검토일 이후 바뀐 사실은 반영되지 않는다.</div>
  {"".join(secs)}
</div>
</body>
</html>
"""
    print(f"검증 현황: 주장 {len(claims)}")
    return page


TARGETS = {
    "index.html": build_index,
    "research/claims_status.html": build_claims,
    "research/a20_etch_knowledge_graph.html": build_graph,
    "research/snupal_qna_knowledge.html": snupal_page.render,
}

if __name__ == "__main__":
    check = "--check" in sys.argv
    stale = []
    for rel, fn in TARGETS.items():
        out = ROOT / rel
        page = fn()
        if check:
            if not out.exists() or out.read_text(encoding="utf-8") != page:
                stale.append(rel)
        else:
            out.write_text(page, encoding="utf-8")
            print("written", rel)
    if check:
        print("최신 아님: " + ", ".join(stale) if stale else "모든 생성 결과가 최신")
        sys.exit(1 if stale else 0)
