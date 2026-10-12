"""질의응답 주제 해설 페이지 (research/snupal_qna_knowledge.html)

    python tools/snupal_page.py prepare <export.json>   # 비공개 export → kb/snupal/page.json (페이지에 싣는 것만)
    python tools/snupal_page.py build                   # kb/snupal/page.json + kb/snupal/topics.json → 페이지 (build_site.py가 부름)

공개 범위(2026-10-13 결정): 글별 요약·색인은 싣지 않는다. 주제별 종합 해설 + 대표 글 링크, 용어마다 정의 1개와 그 근거 글 링크 1개만.
"""
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KB = ROOT / "kb" / "snupal"
OUT = ROOT / "research" / "snupal_qna_knowledge.html"
e = html.escape


def prepare(export_path):
    data = json.loads(Path(export_path).read_text(encoding="utf-8"))
    topics = json.loads((KB / "topics.json").read_text(encoding="utf-8"))["topics"]
    terms, used = [], set()
    for t in topics:
        used.update(t["picks"])
        for s in t["sections"]:
            used.update(s["refs"])
    for t in data["terms"]:
        ds = sorted(t["defs"], key=lambda d: len(d["d"]))
        d = ds[len(ds) // 2]
        used.add(d["id"])
        terms.append({"ko": t["ko"], "en": t.get("en"), "alt": t.get("alt") or [], "def": d["d"], "post": d["id"]})
    posts = {str(p["id"]): {"title": p["title"], "url": p["url"]} for p in data["posts"] if p["id"] in used}
    m = data["meta"]
    meta = {"source": m["source"], "board": m["board"], "posts": m["posts"], "period": m["period"]}
    (KB / "page.json").write_text(json.dumps({"meta": meta, "posts": posts, "terms": terms}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("kb/snupal/page.json: 용어", len(terms), "· 링크 글", len(posts))


def render():
    data = json.loads((KB / "page.json").read_text(encoding="utf-8"))
    topics = json.loads((KB / "topics.json").read_text(encoding="utf-8"))["topics"]
    m, posts = data["meta"], data["posts"]

    def plink(i, title=False):
        p = posts[str(i)]
        label = e(p["title"]) if title else f"글 {i}"
        return f'<a href="{e(p["url"])}" target="_blank" rel="noopener" title="{e(p["title"])}">{label}</a>'

    nav, body, n_sec = [], [], 0
    for t in topics:
        nav.append(f'<a href="#t-{t["key"]}">{e(t["name"])}</a>')
        secs = []
        for s in t["sections"]:
            n_sec += 1
            secs.append(f'<div class="card"><h4>{e(s["title"])}</h4><p>{e(s["text"])}</p>'
                        f'<div class="links">근거 글: {" ".join(plink(r) for r in s["refs"])}</div></div>')
        picks = "".join(f"<li>{plink(i, True)}</li>" for i in t["picks"])
        body.append(f'<section class="topic" id="t-{t["key"]}"><h2>{e(t["name"])}</h2>'
                    f'<p class="intro">{e(t["intro"])}</p>{"".join(secs)}'
                    f'<div class="picks"><b>먼저 읽어 볼 글</b><ol>{picks}</ol></div></section>')

    terms = []
    for t in data["terms"]:
        key = " ".join([t["ko"], t["en"] or "", *t["alt"]]).lower()
        en = f' <span class="en">{e(t["en"])}</span>' if t["en"] else ""
        alt = f'<div class="links">다른 표기: {e(", ".join(t["alt"]))}</div>' if t["alt"] else ""
        terms.append(f'<li data-k="{e(key)}"><b>{e(t["ko"])}</b>{en} — {e(t["def"])} '
                     f'<span class="links">{plink(t["post"])}</span>{alt}</li>')

    page = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>플라즈마 질의응답 주제 해설</title>
<style>
  :root {{ --bg:#f7f8fb; --card:#fff; --ink:#1f2937; --muted:#6b7280; --line:#e5e7eb; --accent:#2563eb; --pl:#0f766e; --pl-bg:#ccfbf1; }}
  * {{ box-sizing:border-box; }}
  html {{ color-scheme: light; }}
  body {{ margin:0; background:var(--bg); color:var(--ink); font:15px/1.75 "Pretendard","Malgun Gothic","Apple SD Gothic Neo",system-ui,sans-serif; }}
  .wrap {{ max-width:960px; margin:0 auto; padding:40px 16px 80px; }}
  h1 {{ font-size:28px; margin:0 0 6px; line-height:1.3; }}
  h2 {{ font-size:21px; margin:40px 0 10px; padding-bottom:6px; border-bottom:2px solid var(--line); color:var(--pl); }}
  h4 {{ margin:0 0 4px; font-size:16px; }}
  a {{ color:var(--accent); }}
  .sub, .note, .links {{ color:var(--muted); }}
  .note, .links {{ font-size:13px; }}
  .links a {{ margin-right:6px; white-space:nowrap; }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px 18px; margin:10px 0; }}
  .card p {{ margin:0 0 6px; }}
  .intro {{ font-size:15.5px; }}
  .picks {{ background:var(--pl-bg); border-radius:12px; padding:10px 18px; margin:12px 0; font-size:14px; }}
  .picks ol {{ margin:4px 0 0; padding-left:20px; }}
  .toc {{ display:flex; flex-wrap:wrap; gap:6px; margin:16px 0; }}
  .toc a {{ font-size:13.5px; padding:4px 12px; border:1px solid #cbd5e1; border-radius:999px; background:#fff; text-decoration:none; color:var(--ink); }}
  .warn {{ background:#fffbeb; border:1px solid #fde68a; border-radius:10px; padding:12px 16px; font-size:14px; }}
  #q {{ width:100%; font:inherit; padding:8px 12px; border:1px solid #cbd5e1; border-radius:10px; background:#fff; margin:6px 0; }}
  #terms {{ list-style:none; padding:0; margin:0; }}
  #terms li {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:8px 14px; margin:6px 0; font-size:14.5px; }}
  #terms .en {{ color:var(--muted); }}
</style>
</head>
<body>
<div class="wrap">
  <h1>플라즈마 질의응답 주제 해설</h1>
  <p class="sub" style="margin-top:6px"><a href="../index.html">← 목차</a> · <a href="a20_etch_knowledge_graph.html">식각 지식 그래프</a> · <a href="plasma_etch_principles.html">플라즈마 식각 원리 노트</a></p>
  <p><a href="{e(m["board"])}">{e(m["source"])}</a>에서 연구실 답변이 반복해 설명하는 내용을 <b>주제 {len(topics)}개 · 해설 {n_sec}개</b>로 종합하고, 용어 {len(data["terms"])}개를 정리했다. 해설마다 근거가 된 글 링크를 붙였다. 개별 글은 게시판에서 직접 찾아 읽을 수 있다.</p>
  <div class="warn">이 페이지는 게시판 글을 옮기거나 글마다 요약한 것이 아니라, 여러 답변에 공통으로 나오는 원리를 <b>우리 말로 다시 쓴 종합 해설</b>이다(모델 초안 + 근거 글 대조). 정확한 표현·수식·그림과 조건은 근거 글 원문에서 확인할 것. 게시판 글의 저작권은 원 게시자와 연구실에 있다.</div>
  <nav class="toc">{"".join(nav)}<a href="#terms-h">용어 사전</a></nav>
  {"".join(body)}
  <h2 id="terms-h">용어 사전</h2>
  <p class="note">용어마다 대표 정의 1개와 그 정의의 근거 글. 다른 표기로도 찾을 수 있다.</p>
  <input id="q" type="search" placeholder="용어 찾기 (예: 쉬스, self bias, 랭뮤어)">
  <ul id="terms">{"".join(terms)}</ul>
  <h2>만든 방법</h2>
  <ol class="note" style="font-size:14px">
    <li>게시판 글 {m["posts"]}개({m["period"][0]} ~ {m["period"][1]})의 연구실 답변에서 지식 항목과 용어를 재서술로 추출했다. 원문은 로컬에만 보관한다.</li>
    <li>게시판 분류를 주제 {len(topics)}개로 묶고, 각 주제의 지식 항목 전체를 astra(GPT 계열)에 주어 "여러 글에 공통으로 나오는 원리"를 해설로 종합하게 했다. 입력에 없는 사실은 쓰지 않게 하고, 근거 글 번호를 함께 받았다.</li>
    <li>검사: 근거 글 번호는 모두 실제 글이며 해당 주제 분류에 속한다. 해설과 근거 글 원문의 최장 연속 일치는 14자다(공백·기호 제외).</li>
  </ol>
</div>
<script>
const q = document.getElementById("q"), items = [...document.querySelectorAll("#terms li")];
q.oninput = () => {{ const s = q.value.trim().toLowerCase(); items.forEach(li => li.hidden = !!s && !(li.dataset.k.includes(s) || li.textContent.toLowerCase().includes(s))); }};
</script>
</body>
</html>
"""

    return page


if __name__ == "__main__":
    if sys.argv[1] == "prepare":
        prepare(sys.argv[2])
    else:
        OUT.write_text(render(), encoding="utf-8")
        print("written", OUT)
