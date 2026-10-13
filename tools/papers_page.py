"""레퍼런스 논문 요약 페이지: kb/papers/papers.json → research/papers.html  (build_site.py가 부른다)

쓰인 곳(그래프 노드·페이지)은 원본에 적지 않고 매번 계산한다:
  그래프 — kb/graph/nodes.json의 출처 키 → sources.json URL → 논문
  페이지 — 공개 HTML 안의 논문 URL
요약 검증 상태는 kb/claims/papers_summary.json(claims_export.py 결과)에서 읽는다.
"""
import json
import os
import re
from html import escape as e
from pathlib import Path

import paper_links

ROOT = Path(__file__).resolve().parent.parent
KB = ROOT / "kb"
GENERATED = {"research/papers.html", "research/claims_status.html", "research/a20_etch_knowledge_graph.html"}
DEC = {"adopt": ("요약 검증: 채택", "ok"), "conditional": ("요약 검증: 조건부", "cond"), "hold": ("요약 검증: 보류", "hold"), "reject": ("요약 검증: 제외", "rej")}


def load(p):
    return json.loads((KB / p).read_text(encoding="utf-8"))


def uses():
    find = paper_links.matcher()
    src, nodes = load("graph/sources.json"), load("graph/nodes.json")
    graph = {}
    for n in nodes:
        for k in n.get("src", []):
            pid = find(src[k]["url"]) if k in src else None
            if pid:
                graph.setdefault(pid, []).append((n["id"], n["name"]))
    titles = {p["href"]: p["title"] for p in load("pages.json")["pages"]}
    pages = {}
    for p in sorted(paper_links.public_pages()):
        rel = p.relative_to(ROOT).as_posix()
        if rel in GENERATED:
            continue
        text = p.read_text(encoding="utf-8")
        title = titles.get(rel) or (re.search(r"<title>(.*?)</title>", text, re.S) or [None, rel])[1].strip()
        for pid in {find(u) for u in re.findall(r'https?://[^"\'\s<>]+', text)} - {None}:
            pages.setdefault(pid, []).append((rel, title))
    return graph, pages


def render():
    cfg = load("papers/papers.json")
    ps = cfg["papers"]
    ids = [p["id"] for p in ps]
    if len(ids) != len(set(ids)):
        raise SystemExit("논문 id 중복")
    claims = {}
    cp = KB / "claims/papers_summary.json"
    if cp.exists():
        claims = {c["id"]: c for c in json.loads(cp.read_text(encoding="utf-8"))["claims"]}
    graph, pages = uses()

    def card(p):
        url = f'https://doi.org/{p["doi"]}' if p.get("doi") else p["url"]
        if (p.get("doi") or "").startswith("10.48550/arxiv."):
            url = "https://arxiv.org/abs/" + p["doi"].split("arxiv.")[1]
        c = claims.get("P-" + p["id"])
        badge = (f'<a class="b {DEC[c["decision"]][1]}" href="claims_status.html#P-{p["id"]}">{DEC[c["decision"]][0]}</a>' if c
                 else '<span class="b none">요약 검증 전</span>')
        cond = f'<p class="cond"><b>읽을 때 주의</b> {e(c["conditions"])}</p>' if c and c.get("conditions") else ""
        used = [f'<a href="a20_etch_knowledge_graph.html#{nid}">{e(name)}</a>' for nid, name in graph.get(p["id"], [])]
        used += [f'<a href="{e(Path(os.path.relpath(rel, "research")).as_posix())}">{e(t)}</a>' for rel, t in pages.get(p["id"], [])]
        pts = "".join(f"<li>{e(x)}</li>" for x in p.get("points", []))
        return (f'<article class="pp" id="{p["id"]}" data-k="{e((p["title"] + " " + p["authors"] + " " + p["summary"]).lower())}">'
                f'<div class="h"><span class="yr">{p["year"]}</span><span class="t">{e(p["kind"])}</span>'
                f'<span class="t">근거: {e(p["basis"])}</span>{badge}</div>'
                f'<h3><a href="{e(url)}" target="_blank" rel="noopener">{e(p["title"])}</a></h3>'
                f'<p class="meta">{e(p["authors"])} · {e(p["venue"])}{" · DOI " + e(p["doi"]) if p.get("doi") and not p["doi"].startswith("10.48550") else ""}</p>'
                f'<p class="sum">{e(p["summary"])}</p>{f"<ul>{pts}</ul>" if pts else ""}{cond}'
                f'<p class="use"><b>이 프로젝트에서</b> {e(p["use"])}</p>'
                f'{"<p class=used><b>쓰인 곳</b> " + " · ".join(used) + "</p>" if used else ""}</article>')

    secs, nav = [], []
    for key, label in cfg["areas"].items():
        rows = sorted((p for p in ps if p["area"] == key), key=lambda p: (p["year"], p["id"]))
        if not rows:
            continue
        nav.append(f'<a href="#a-{key}">{e(label)} <small>{len(rows)}</small></a>')
        secs.append(f'<h2 id="a-{key}">{e(label)}</h2>' + "".join(card(p) for p in rows))
    n_dec = {k: sum(1 for p in ps if claims.get("P-" + p["id"], {}).get("decision") == k) for k in DEC}
    n_basis = {b: sum(1 for p in ps if p["basis"] == b) for b in dict.fromkeys(p["basis"] for p in ps)}
    basis_txt = " · ".join(f"{k} {v}" for k, v in n_basis.items())
    print(f"논문 요약: {len(ps)}편 · 그래프 연결 {sum(len(v) for v in graph.values())} · 페이지 연결 {sum(len(v) for v in pages.values())}")
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>레퍼런스 논문 요약</title>
<style>
  :root {{ --bg:#f7f8fb; --card:#fff; --ink:#1f2937; --muted:#6b7280; --line:#e5e7eb; --accent:#2563eb; }}
  * {{ box-sizing:border-box; }}
  html {{ color-scheme: light; }}
  body {{ margin:0; background:var(--bg); color:var(--ink); font:15px/1.7 "Pretendard","Malgun Gothic","Apple SD Gothic Neo",system-ui,sans-serif; }}
  .wrap {{ max-width:920px; margin:0 auto; padding:40px 16px 80px; }}
  h1 {{ font-size:28px; margin:0 0 6px; }}
  h2 {{ font-size:20px; margin:36px 0 10px; padding-bottom:6px; border-bottom:2px solid var(--line); scroll-margin-top:12px; }}
  a {{ color:var(--accent); }}
  .sub, .meta, .use, .used {{ color:var(--muted); }}
  .nav {{ display:flex; flex-wrap:wrap; gap:8px; margin:14px 0; }}
  .nav a {{ background:var(--card); border:1px solid var(--line); border-radius:999px; padding:3px 12px; text-decoration:none; font-size:14px; }}
  .nav small {{ color:var(--muted); }}
  input#q {{ width:100%; padding:9px 14px; border:1px solid var(--line); border-radius:10px; font:inherit; background:var(--card); }}
  .box {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:12px 18px; font-size:14px; margin:14px 0; }}
  .pp {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px 18px; margin:10px 0; scroll-margin-top:16px; }}
  .pp:target {{ border-color:var(--accent); box-shadow:0 0 0 2px #bfdbfe; }}
  .pp h3 {{ font-size:16px; margin:6px 0 2px; line-height:1.45; }}
  .pp h3 a {{ color:var(--ink); text-decoration:none; }} .pp h3 a:hover {{ color:var(--accent); text-decoration:underline; }}
  .h {{ display:flex; flex-wrap:wrap; gap:6px; align-items:center; font-size:12px; }}
  .yr {{ font-weight:700; font-family:ui-monospace,Consolas,monospace; font-size:13px; }}
  .t {{ background:#f3f4f6; color:#374151; border-radius:999px; padding:1px 9px; }}
  .b {{ font-weight:700; padding:1px 10px; border-radius:999px; text-decoration:none; }}
  .b.ok {{ background:#dcfce7; color:#166534; }} .b.cond {{ background:#fef3c7; color:#92400e; }}
  .b.hold, .b.none {{ background:#f3f4f6; color:#4b5563; }} .b.rej {{ background:#fee2e2; color:#991b1b; }}
  .meta {{ margin:0 0 6px; font-size:13.5px; }}
  .sum {{ margin:6px 0; }}
  .pp ul {{ margin:4px 0 6px; padding-left:20px; font-size:14px; }}
  .cond {{ margin:6px 0; font-size:14px; background:#fffbeb; border-radius:8px; padding:6px 10px; }}
  .use, .used {{ margin:4px 0 0; font-size:13.5px; }}
  .used a {{ white-space:nowrap; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>레퍼런스 논문 요약</h1>
  <p class="sub"><a href="../index.html">← 목차</a> · <a href="a20_etch_knowledge_graph.html">식각 지식 그래프</a> · <a href="claims_status.html">검증 현황</a></p>
  <p>이 사이트의 보고서·지식 그래프·OES 표가 근거로 인용한 논문 {len(ps)}편을 한 곳에 모아 요약했다. 그래프 노드와 보고서의 논문 링크 옆 <b>요약</b>을 누르면 여기로 온다. 각 요약 아래 <b>쓰인 곳</b>에서 거꾸로 해당 노드·페이지로 갈 수 있다.</p>
  <div class="box"><b>읽는 법</b> — 요약은 원문을 옮기지 않고 다시 쓴 것이다. <b>근거</b>는 요약할 때 본 범위다(공개 원문 / 초록 / 서지 정보만). 유료 논문은 대부분 초록 기준이라 세부 수치·조건은 원문을 확인해야 한다. 각 요약의 핵심 문장은 작성 과정을 모르는 검증 에이전트가 원문과 대조했다(채택 {n_dec["adopt"]} · 조건부 {n_dec["conditional"]} · 보류·제외 {n_dec["hold"] + n_dec["reject"]}). 근거 범위: {e(basis_txt)}.</div>
  <input id="q" type="search" placeholder="제목·저자·내용 검색 (예: SAQP, actinometry, HfO2)" aria-label="논문 검색">
  <nav class="nav">{"".join(nav)}</nav>
  {"".join(secs)}
</div>
<script>
const q = document.getElementById("q"), cards = [...document.querySelectorAll(".pp")], hs = [...document.querySelectorAll("h2")];
q.addEventListener("input", () => {{
  const w = q.value.trim().toLowerCase().split(/\\s+/).filter(Boolean);
  cards.forEach(c => c.hidden = !w.every(x => c.dataset.k.includes(x)));
  hs.forEach(h => {{ let n = h.nextElementSibling, any = false; while (n && n.tagName !== "H2") {{ if (!n.hidden) any = true; n = n.nextElementSibling; }} h.hidden = !any; }});
}});
</script>
</body>
</html>
"""
