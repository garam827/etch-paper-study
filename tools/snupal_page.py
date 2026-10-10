"""공개용 JSON(snupal_merge.py export) → research/snupal_qna_knowledge.html (데이터 내장, 검색·필터)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
src = Path(sys.argv[1])
data = json.loads(src.read_text(encoding="utf-8"))
m = data["meta"]
n_sub = sum(p["type"] == "substantive" for p in data["posts"])
n_k = sum(len(p["k"]) for p in data["posts"])
blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

html = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>플라즈마 질의응답 지식</title>
<style>
  :root { --bg:#f7f8fb; --card:#fff; --ink:#1f2937; --muted:#6b7280; --line:#e5e7eb; --accent:#2563eb; --pl:#0f766e; --pl-bg:#ccfbf1; }
  * { box-sizing:border-box; }
  html { color-scheme: light; }
  body { margin:0; background:var(--bg); color:var(--ink); font:15px/1.7 "Pretendard","Malgun Gothic","Apple SD Gothic Neo",system-ui,sans-serif; }
  .wrap { max-width:1040px; margin:0 auto; padding:40px 16px 80px; }
  h1 { font-size:28px; margin:0 0 6px; line-height:1.3; }
  h2 { font-size:21px; margin:36px 0 12px; padding-bottom:6px; border-bottom:2px solid var(--line); }
  a { color:var(--accent); }
  .sub, .note { color:var(--muted); }
  .note { font-size:13px; }
  .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px; margin:18px 0; }
  .kpi { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px 16px; }
  .kpi b { display:block; font-size:22px; color:var(--pl); font-variant-numeric:tabular-nums; }
  .kpi span { color:var(--muted); font-size:13px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px 18px; margin:10px 0; }
  .bar { position:sticky; top:0; z-index:5; background:var(--bg); padding:10px 0; display:flex; flex-wrap:wrap; gap:8px; align-items:center; border-bottom:1px solid var(--line); }
  .bar input { flex:1 1 260px; font:inherit; padding:8px 12px; border:1px solid #cbd5e1; border-radius:10px; background:#fff; }
  .bar select { font:inherit; padding:8px 10px; border:1px solid #cbd5e1; border-radius:10px; background:#fff; }
  .tabs { display:flex; gap:6px; }
  .tabs button { font:inherit; font-weight:600; padding:7px 14px; border:1px solid #cbd5e1; border-radius:999px; background:#fff; cursor:pointer; color:var(--ink); }
  .tabs button.on { background:var(--pl); border-color:var(--pl); color:#fff; }
  .count { color:var(--muted); font-size:13px; margin:10px 0 0; }
  .term h3 { margin:0; font-size:16px; } .term .en { color:var(--muted); font-weight:400; font-size:14px; margin-left:6px; }
  .term ul { margin:6px 0 0; padding-left:18px; } .term li { margin:2px 0; }
  .links { font-size:13px; margin-top:6px; color:var(--muted); }
  .links a { margin-right:6px; white-space:nowrap; }
  .chip { display:inline-block; font-size:12px; padding:1px 8px; border-radius:999px; background:var(--pl-bg); color:var(--pl); margin:0 4px 4px 0; font-weight:600; }
  .chip.g { background:#f3f4f6; color:#4b5563; }
  .post h3 { font-size:15.5px; margin:0 0 4px; }
  .post .meta { font-size:12.5px; color:var(--muted); margin-bottom:6px; }
  .post ol { margin:6px 0 0; padding-left:20px; } .post li { margin:3px 0; }
  .cond { color:var(--muted); font-size:13px; }
  .catblock h3 { font-size:17px; margin:22px 0 6px; color:var(--pl); }
  .more { display:block; margin:14px auto; font:inherit; padding:8px 18px; border-radius:10px; border:1px solid #cbd5e1; background:#fff; cursor:pointer; }
  .warn { background:#fffbeb; border:1px solid #fde68a; border-radius:10px; padding:12px 16px; font-size:14px; }
  mark { background:#fef08a; padding:0 1px; }
</style>
</head>
<body>
<div class="wrap">
  <h1>플라즈마 질의응답 지식 — SNU PAL 게시판 정리</h1>
  <p class="sub" style="margin-top:6px"><a href="../index.html">← 목차</a> · <a href="a20_etch_knowledge_graph.html">식각 지식 그래프</a> · <a href="plasma_etch_principles.html">플라즈마 식각 원리 노트</a></p>
  <p>__SOURCE__의 질문·답변 <b>__N__개</b>(__P0__ ~ __P1__)를 한 글씩 데이터베이스로 만들고, 연구실 답변에서 지식과 용어를 뽑아 정리했다. 모든 항목에 <b>원문 글 링크</b>가 붙어 있다.</p>
  <div class="warn">여기 글은 원문을 옮긴 것이 아니라 <b>우리 말로 재서술한 요약</b>이다(원문 본문·작성자 이름은 싣지 않음). 추출은 모델 자동 추출(astra·Claude) + 자동 검사·표본 대조로 했으므로, 정확한 표현·수식·그림은 반드시 원문 링크에서 확인할 것. 게시판의 저작권은 원 게시자와 연구실에 있다.</div>
  <div class="grid">
    <div class="kpi"><b>__N__</b><span>수집한 글</span></div>
    <div class="kpi"><b>__NSUB__</b><span>실질적 답변이 있는 글</span></div>
    <div class="kpi"><b>__NK__</b><span>지식 항목</span></div>
    <div class="kpi"><b>__NT__</b><span>용어 (병합 후)</span></div>
  </div>

  <div class="bar">
    <div class="tabs"><button data-t="terms" class="on">용어 사전</button><button data-t="know">분류별 지식</button><button data-t="posts">글 목록</button></div>
    <input id="q" type="search" placeholder="검색 (예: 쉬스, self bias, 랭뮤어, IEDF)">
    <select id="cat"><option value="">전체 분류</option></select>
  </div>
  <p class="count" id="count"></p>
  <div id="out"></div>
  <button class="more" id="more" hidden>더 보기</button>

  <h2>만든 방법</h2>
  <ol class="note" style="font-size:14px">
    <li>게시판 목록 34쪽에서 글 __N__개의 번호·제목·작성일을 읽고, 글마다 본문과 댓글(답변)을 받아 로컬 SQLite 데이터베이스에 저장 (1초 간격, robots.txt 허용 범위). 원문은 로컬에만 보관.</li>
    <li>글을 50개씩 묶어 모델이 글마다 질문 요지·답변 유형·지식·용어를 재서술로 추출 — 앞 __NA__개는 astra(GPT 계열), 나머지 __NC__개는 사용량 한도 때문에 Claude(Sonnet)로, 같은 지시문·같은 형식. 질문자의 추측이 아니라 <b>연구실 답변</b>(연구실 교수·연구실이 올린 글·스스로 연구실 학생이라 밝힌 답변자)에서만 지식을 뽑음. 옛 게시판에서 이관된 글은 본문의 "답변" 뒤를 연구실 답변으로 처리.</li>
    <li>자동 검사(전체 글): 누락 0, 작성자 이름 노출 0, 원문 30자 이상 연속 일치 __NCP__건(책 제목·용어 나열 등 짧은 구절). 표본 검증: 두 모델의 추출 결과에서 무작위 10개 글을 원문 답변과 대조 — 10개 모두 답변 내용과 일치, 답변에 없는 내용 추가 없음.</li>
    <li>용어는 영문 기준으로 같은 개념을 합치고, 대표 표기는 이 사이트의 기존 표기(쉬스·자기 바이어스·표피 깊이·Debye 길이·파셴 등)에 맞춤. 다른 표기도 검색됨. 각 용어에 그 용어가 나온 글 링크를 모두 붙임.</li>
    <li>"답변 없음"은 연구실 답변이 없거나 "자료가 없다"는 답만 있는 글, "안내"는 교재·게시판 검색어 안내 위주인 글.</li>
  </ol>
</div>
<script>
const DATA = __DATA__;
const byId = Object.fromEntries(DATA.posts.map(p => [p.id, p]));
let tab = "terms", shown = 60;
const $ = s => document.querySelector(s);
const esc = s => (s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const cats = [...new Set(DATA.posts.map(p => p.cat || "기타"))].sort();
cats.forEach(c => $("#cat").insertAdjacentHTML("beforeend", `<option>${esc(c)}</option>`));
try { const u = new URLSearchParams(location.search).get("q"); if (u) $("#q").value = u; } catch (e) {}
const hl = (s, q) => { s = esc(s); if (!q) return s; const i = s.toLowerCase().indexOf(q.toLowerCase()); return i < 0 ? s : s.slice(0, i) + "<mark>" + s.slice(i, i + q.length) + "</mark>" + s.slice(i + q.length); };
const link = id => { const p = byId[id]; return p ? `<a href="${p.url}" target="_blank" rel="noopener" title="${esc(p.title)}">#${p.id}</a>` : ""; };
const typeName = { substantive: "답변 있음", pointer: "안내", none: "답변 없음" };

function render() {
  const q = $("#q").value.trim(), cat = $("#cat").value, ql = q.toLowerCase();
  const inCat = p => !cat || (p.cat || "기타") === cat;
  let items, html = "";
  if (tab === "terms") {
    items = DATA.terms.filter(t => (!cat || t.docs.some(d => byId[d] && inCat(byId[d]))) &&
      (!q || [t.ko, t.en, ...(t.alt || []), ...t.defs.map(d => d.d)].some(s => (s || "").toLowerCase().includes(ql))));
    html = items.slice(0, shown).map(t => `<div class="card term"><h3>${hl(t.ko, q)}${t.en ? `<span class="en">${hl(t.en, q)}</span>` : ""} <span class="chip g">${t.n}개 글</span></h3>${t.alt && t.alt.length ? `<div class="links">다른 표기: ${t.alt.map(a => hl(a, q)).join(", ")}</div>` : ""}
      <ul>${t.defs.map(d => `<li>${hl(d.d, q)} <span class="links">${link(d.id)}</span></li>`).join("")}</ul>
      <div class="links">출처 글: ${t.docs.slice(0, 30).map(link).join("")}${t.docs.length > 30 ? ` 외 ${t.docs.length - 30}개` : ""}</div></div>`).join("");
  } else if (tab === "know") {
    const ps = DATA.posts.filter(p => p.k.length && inCat(p) && (!q || [p.title, p.q, ...p.topics, ...p.k.map(k => k.p + " " + (k.c || ""))].some(s => (s || "").toLowerCase().includes(ql))));
    items = ps; const groups = {};
    ps.slice(0, shown).forEach(p => (groups[p.cat || "기타"] ??= []).push(p));
    html = Object.entries(groups).map(([c, arr]) => `<div class="catblock"><h3>${esc(c)}</h3>${arr.map(p => `<div class="card post">
      <h3>${hl(p.title, q)} <span class="links">${link(p.id)}</span></h3>
      <div>${p.topics.map(t => `<span class="chip">${hl(t, q)}</span>`).join("")}</div>
      <ol>${p.k.map(k => `<li>${hl(k.p, q)}${k.c ? ` <span class="cond">— 조건: ${hl(k.c, q)}</span>` : ""}</li>`).join("")}</ol></div>`).join("")}</div>`).join("");
  } else {
    items = DATA.posts.filter(p => inCat(p) && (!q || [p.title, p.q, ...p.topics].some(s => (s || "").toLowerCase().includes(ql))));
    html = items.slice(0, shown).map(p => `<div class="card post"><h3><a href="${p.url}" target="_blank" rel="noopener">${hl(p.title, q)}</a></h3>
      <div class="meta">#${p.id} · ${esc(p.cat || "기타")} · ${esc(p.date)} · ${typeName[p.type] || ""} · 지식 ${p.k.length}개</div>
      <div>${hl(p.q, q)}</div><div style="margin-top:6px">${p.topics.map(t => `<span class="chip">${esc(t)}</span>`).join("")}</div></div>`).join("");
  }
  $("#out").innerHTML = html || `<p class="note">검색 결과가 없습니다.</p>`;
  $("#count").textContent = `${items.length}개 중 ${Math.min(shown, items.length)}개 표시`;
  $("#more").hidden = items.length <= shown;
}
document.querySelectorAll(".tabs button").forEach(b => b.onclick = () => { tab = b.dataset.t; shown = 60; document.querySelectorAll(".tabs button").forEach(x => x.classList.toggle("on", x === b)); render(); });
$("#q").oninput = () => { shown = 60; render(); };
$("#cat").onchange = () => { shown = 60; render(); };
$("#more").onclick = () => { shown += 60; render(); };
render();
</script>
</body>
</html>
"""
for k, v in {"__NA__": str(sum(p.get("by") == "astra" for p in data["posts"])), "__NC__": str(sum(p.get("by") != "astra" for p in data["posts"])), "__NCP__": sys.argv[2] if len(sys.argv) > 2 else "?", "__SOURCE__": f'<a href="{m["board"]}">{m["source"]}</a>', "__NSUB__": str(n_sub), "__NK__": str(n_k),
             "__NT__": str(len(data["terms"])), "__N__": str(m["posts"]), "__P0__": m["period"][0], "__P1__": m["period"][1]}.items():
    html = html.replace(k, v)
html = html.replace("__DATA__", blob)
out = ROOT / "research" / "snupal_qna_knowledge.html"
out.write_text(html, encoding="utf-8")
print("written", out, round(out.stat().st_size / 1024), "KB")
