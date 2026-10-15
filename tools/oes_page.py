"""OES Assistant(별도 프로젝트)의 식각 화학 데이터 → 정적 읽기 전용 페이지.

    python tools/oes_page.py <oes_assistant 폴더> <파장검증.json> [조합검증.json]

- 읽는 것: <폴더>/data/etch_knowledge.json (막질×기체 조합 67개), data/spectra.json (기준 파장).
  앱 코드·.env·worker는 읽지 않는다.
- 파장검증.json: [species, nm, source_id, 원문일치(bool), medium, kind] 목록 (NIST 표·논문 원문 대조 결과).
- 조합검증.json: {claim_id: {"combo": id, "verdict": ..., "notes": ...}} (표본 독립 검증, 선택).
- kb/oes/combos_extra.json(이 사이트에서 따로 조사·검증한 막질×기체 조합, #54)과 그 검증 상태 kb/claims/oes_extra.json이 있으면 조합 표에 합친다.
- tools/oes_supplement.json이 있으면 보완 절(원자선·분자 방출·종말점·actinometry·겹침)을 덧붙인다 (tools/oes_supplement_build.py).
출력: research/oes_etch_chemistry.html
"""
import html
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
src = Path(sys.argv[1])
K = json.load(open(src / "data/etch_knowledge.json", encoding="utf-8"))
SP = json.load(open(src / "data/spectra.json", encoding="utf-8"))
VER = json.load(open(sys.argv[2], encoding="utf-8"))
CV = json.load(open(sys.argv[3], encoding="utf-8")) if len(sys.argv) > 3 else {}
e = html.escape

KIND = {"atomic_line": "원자선", "ionic_line": "이온선", "molecular_band": "분자 진단 위치", "molecular_diagnostic": "분자 진단 위치"}
EVID = {"provided_feed": "공급 가스", "chemical_inference": "추론", "reported_in_reference": "문헌 보고"}
BASIS = {"reference_example": "출처의 공정 예시", "literature_family": "문헌의 반응 계열", "chemistry_variant": "화학 변형 예시"}
VERD = {"supported": ("지지", "adopt"), "partial": ("부분 지지", "cond"), "contradicted": ("반박", "reject"), "unverifiable": ("확인 불가", "hold")}
SUPP_F = ROOT / "tools/oes_supplement.json"
SUP = json.load(open(SUPP_F, encoding="utf-8")) if SUPP_F.exists() else None
DEC = {"adopt": ("채택", "adopt"), "conditional": ("조건부", "cond")}
supp_species = set(SUP["atomic"]) | {m["sp"] for m in SUP["mol"]} if SUP else set()
BX_F = ROOT / "kb/oes/bands_extra.json"
BX = json.load(open(BX_F, encoding="utf-8")) if BX_F.exists() else {"atomic": {}, "mol": []}
supp_species |= set(BX["atomic"]) | {m["sp"] for m in BX["mol"]}

# 화학종 → 관련 OES 파장 (조합 표의 "관련 OES 파장" 열)
def _f(w): return f"{w:.1f}"
def _j(ws): return " · ".join(dict.fromkeys(_f(w) for w in ws))  # 소수 첫째 자리에서 겹치는 선은 한 번만
WL = {}
for name, s in SP["species"].items():
    WL.setdefault(name, []).append(["v", _j(s["wavelengths_nm"]), "기준 파장"])
for src_atomic in ([SUP["atomic"]] if SUP else []) + [BX["atomic"]]:
    for name, v in src_atomic.items():
        WL.setdefault(name, []).append(["s", _j(l["nm"] for l in v["lines"]), v["spectrum"] + " NIST 강한 선"])
for m in (SUP["mol"] if SUP else []) + BX["mol"]:
    WL.setdefault(m["sp"], []).append(["s", m["nm"], m.get("tr", "")])

EX_F, EXS_F = ROOT / "kb/oes/combos_extra.json", ROOT / "kb/claims/oes_extra.json"
EX = json.load(open(EX_F, encoding="utf-8")) if EX_F.exists() else None
EXS = {c["id"]: c for c in json.load(open(EXS_F, encoding="utf-8"))["claims"]} if EX and EXS_F.exists() else {}
sources = {**K["sources"], **SP["sources"], **(EX["sources"] if EX else {})}
ok = {(v[0], v[1]): v[3] for v in VER}
n_ok = sum(v[3] for v in VER)

# 1) 기준 파장
rows = []
for name, s in SP["species"].items():
    src_ = SP["sources"][s["source_id"]]
    marks = " ".join(f'{w}{"" if ok.get((name, w)) else " ⚠"}' for w in s["wavelengths_nm"])
    rows.append(f'<tr><td><b>{e(name)}</b></td><td>{KIND.get(s["kind"], e(s["kind"]))}</td><td class="num">{marks}</td>'
                f'<td>{e(s["medium"])}</td><td><a href="{e(src_["url"])}" target="_blank" rel="noopener">{e(src_["title"])}</a></td></tr>')
spectra_tbl = "\n".join(rows)

# 2) 조합 (JS에서 필터)
combo_verdict = {v["combo"]: v for v in CV.values()}
items = []
for x in K["items"]:
    sp = [{"f": s["formula"], "e": s["evidence"], "w": bool(s.get("spectrum")), "w2": (not s.get("spectrum")) and s["formula"] in supp_species} for s in x["species"]]
    items.append({"id": x["id"], "film": x["film"]["name"], "fam": x["family_label"], "gas": x["gases"], "mode": x["mode_label"],
                  "basis": BASIS.get(x["basis"], x["basis"]), "src": x["sources"], "prod": x.get("products", []),
                  "res": x.get("residues", []), "note": x.get("note", ""), "sp": sp,
                  "v": combo_verdict.get(x["id"], {}).get("verdict")})
def wl_of(forms, extra=None):
    out, none = [], []
    for f in dict.fromkeys(forms):
        rows = [r for r in (extra or {}).get(f, [])] + WL.get(f, [])
        (out.append([f, rows]) if rows else none.append(f))
    return out, none
for i in items:
    i["wl"], i["nowl"] = wl_of([s["f"] for s in i["sp"]])
n_base = len(items)
EV = {"feed": "provided_feed", "rep": "reported_in_reference", "": "chemical_inference"}
DECL = {"adopt": ("채택", "adopt"), "conditional": ("조건부", "cond"), "hold": ("보류", "hold"), "reject": ("제외", "reject")}
ex_dec = Counter()
for x in (EX["items"] if EX else []):
    f = EX["films"][x["film"]]
    c = EXS.get(x.get("claim", "OE" + x["id"][3:]), {})
    d = c.get("decision")
    if d in ("hold", "reject"):
        continue  # 검증을 통과하지 못한 조합은 싣지 않는다
    ex_dec[d or "미검증"] += 1
    sp = [{"f": s, "e": EV[k], "w": s in SP["species"], "w2": s not in SP["species"] and s in supp_species} for s, k in x["sp"]]
    items.append({"id": x["id"], "film": f["name"], "fam": f["family_label"], "gas": x["gases"],
                  "mode": K["modes"].get(x["mode"]) or EX["modes"][x["mode"]], "basis": "보완 조사(2026-10-15)",
                  "src": x["src"], "prod": [], "res": [], "note": x["note"], "sp": sp, "v": None,
                  "d": list(DECL[d]) if d else None})
    items[-1]["wl"], items[-1]["nowl"] = wl_of([s for s, _ in x["sp"]], {k: [["r", v, "이 조합 출처 측정"]] for k, v in x.get("wl", {}).items()})
ev = Counter(s["e"] for i in items for s in i["sp"])
src_js = {k: [v["title"], v["url"]] for k, v in sources.items()}
fams = sorted(set(i["fam"] for i in items))

# 3) 표본 검증 표
cv_rows = ""
for cid, v in sorted(CV.items()):
    x = next(i for i in K["items"] if i["id"] == v["combo"])
    lab, cls = VERD.get(v["verdict"], (v["verdict"], "hold"))
    cv_rows += (f'<tr><td>{e(cid)}</td><td>{e(x["id"])}</td><td>{e(x["film"]["name"])} · {e(" + ".join(x["gases"]))}</td>'
                f'<td><span class="tag {cls}">{lab}</span></td><td>{e(v.get("notes", ""))}</td></tr>')
cv_count = Counter(v["verdict"] for v in CV.values())

limits = "".join(f"<li>{e(t)}</li>" for t in K["limitations"])
src_rows = "".join(f'<tr><td><code>{e(k)}</code></td><td><a href="{e(v["url"])}" target="_blank" rel="noopener">{e(v["title"])}</a></td>'
                   f'<td>{e(v.get("kind", "파장 기준"))}</td></tr>' for k, v in sorted(sources.items()))

# 4) 보완 절
supp_html = ""
if SUP:
    def srcs(r): return "<br>".join(f'<a href="{e(u)}" target="_blank" rel="noopener">{e(n)}</a>' for n, u in r["src"])
    def tag(r): lab, cls = DEC[r["decision"]]; return f'<span class="tag {cls}">{lab}</span>'
    def note(r): return f'<div class="note">{e(r["note"])}</div>' if r.get("note") else ""
    at = "".join(f'<tr><td><b>{e(k)}</b></td><td>{e(v["spectrum"])}</td><td class="num">{" ".join(str(l["nm"]) for l in v["lines"])}</td>'
                 f'<td><a href="{e(v["url"])}" target="_blank" rel="noopener">NIST · Strong Lines</a></td></tr>' for k, v in sorted(SUP["atomic"].items()))
    mol = "".join(f'<tr><td><b>{e(r["sp"])}</b></td><td class="num">{e(r["nm"])}</td><td>{e(r["tr"])}</td><td>{e(r["cond"])}</td>'
                  f'<td>{tag(r)} <code>{r["id"]}</code>{note(r)}</td><td>{srcs(r)}</td></tr>' for r in SUP["mol"])
    epd = "".join(f'<tr><td>{e(r["film"])}</td><td>{e(r["chem"])}</td><td><b>{e(r["sig"])}</b></td><td>{e(r["cond"])}</td>'
                  f'<td>{tag(r)} <code>{r["id"]}</code>{note(r)}</td><td>{srcs(r)}</td></tr>' for r in SUP["epd"])
    act = "".join(f'<tr><td><b>{e(r["t"])}</b></td><td>{e(r["pair"])}</td><td>{e(r["cond"])}</td>'
                  f'<td>{tag(r)} <code>{r["id"]}</code>{note(r)}</td><td>{srcs(r)}</td></tr>' for r in SUP["act"])
    ovl = "".join(f'<tr><td><b>{e(r["pair"])}</b></td><td class="num">{e(r["nm"])}</td><td>{tag(r)} <code>{r["id"]}</code>{note(r)}</td><td>{srcs(r)}</td></tr>' for r in SUP["ovl"])
    n_all = sum(len(SUP[k]) for k in ("mol", "epd", "act", "ovl")); n_ex = len(SUP["excluded"])
    ex = ", ".join(f'{r["id"]}({r["decision"]})' for r in SUP["excluded"])
    supp_html = f"""
  <h2 id="supp">보완 (2026-10-11 조사)</h2>
  <p>위 기준 목록에 없던 화학종의 방출 위치와, 실제 식각에서 OES를 어떻게 쓰는지를 따로 조사해 보탰다. 원자선은 NIST 표에서 기계적으로 뽑았고, 나머지는 주장 장부 → 독립 검증(웹 원문만 보는 별도 에이전트) → 규칙 채택을 거쳐 <b>채택·조건부 {n_all}개</b>만 실었다{f" (보류·제외 {n_ex}개: {e(ex)})" if n_ex else ""}. 조합 표에서 <span class="sp w2">보완 위치 있음</span>으로 표시된다.</p>

  <h3 id="supp-atomic">원자·이온 선 (NIST 강한 선 표, {len(SUP["atomic"])}종)</h3>
  <p class="note">각 원소 표(공기 중 파장)에서 200–900 nm 구간의 상대 세기 상위 4개를 1 nm 안 중복을 빼고 뽑았다. 상대 세기는 원소마다 기준이 달라 원소끼리 비교할 수 없고, 식각 장비에서 실제로 잘 보이는 선과 다를 수 있다.</p>
  <div class="tbl"><table><thead><tr><th>화학종</th><th>스펙트럼</th><th>파장 (nm, 공기)</th><th>출처</th></tr></thead><tbody>{at}</tbody></table></div>

  <h3 id="supp-mol">분자 방출 위치</h3>
  <p class="note">밴드 헤드, 넓은 밴드의 최대점, 장비 감시 채널값이 섞여 있다(“값” 열 그대로). 공기/진공 기준은 대부분 출처에 명시되지 않았다. 식각이 아닌 실험(광해리 형광, LIBS, 대기 방출)에서 확인한 값은 조건 열에 적었다.</p>
  <div class="tbl"><table><thead><tr><th>화학종</th><th>값 (nm)</th><th>전이</th><th>조건</th><th>판정</th><th>출처</th></tr></thead><tbody>{mol}</tbody></table></div>

  <h3 id="supp-epd">식각 종말점 검출(EPD)에서 감시하는 방출</h3>
  <p class="note">↑/↓는 그 출처의 공정에서 관측한 변화다. 같은 파장도 어떤 계면을 지나느냐에 따라 방향이 바뀔 수 있어 고정 규칙으로 쓰면 안 된다. 특허·장비사 자료는 출처 이름에 표시했다.</p>
  <div class="tbl"><table><thead><tr><th>막질 · 경계</th><th>화학</th><th>감시 방출</th><th>조건</th><th>판정</th><th>출처</th></tr></thead><tbody>{epd}</tbody></table></div>

  <h3 id="supp-act">Actinometry 선 쌍</h3>
  <p class="note">방출 세기 비를 밀도 비로 바꾸려면 두 선의 들뜸률 비가 조건에 따라 크게 변하지 않아야 한다. 해리 들뜸(분자가 깨지며 들뜬 원자가 생김), 준안정 상태, 들뜸 에너지 차이가 오차 원인이다.</p>
  <div class="tbl"><table><thead><tr><th>대상</th><th>선 쌍 (nm)</th><th>조건</th><th>판정</th><th>출처</th></tr></thead><tbody>{act}</tbody></table></div>

  <h3 id="supp-ovl">가까운 선 주의</h3>
  <div class="tbl"><table><thead><tr><th>조합</th><th>위치 (nm)</th><th>판정</th><th>출처</th></tr></thead><tbody>{ovl}</tbody></table></div>
  <p class="note">위 기준 목록의 CF₂ 251.9 nm와 Si 251.92 nm(NIST)도 같은 경우다.</p>
"""

bx_html = ""
if BX["atomic"] or BX["mol"]:
    bxa = "".join(f'<tr><td><b>{e(k)}</b></td><td>{e(v["spectrum"])}</td><td class="num">{" · ".join(format(l["nm"], ".3f") for l in v["lines"])}</td>'
                  f'<td><a href="{e(v["url"])}" target="_blank" rel="noopener">NIST · Strong Lines</a></td></tr>' for k, v in sorted(BX["atomic"].items()))
    bxm = "".join(f'<tr><td><b>{e(m["sp"])}</b></td><td class="num">{e(m["nm"])}</td><td>{e(m["tr"])}</td><td>{e(m["cond"])}</td>'
                  f'<td><span class="tag {DECL[m["decision"]][1]}">{DECL[m["decision"]][0]}</span> <code>{e(m["id"])}</code></td>'
                  f'<td><a href="{e(m["url"])}" target="_blank" rel="noopener">{e(m["title"])}</a></td></tr>' for m in BX["mol"])
    bx_html = f"""
  <h3 id="supp-bands">조합별 파장 표시를 위한 보완 (2026-10-15)</h3>
  <p class="note">조합 표의 화학종 중 근거 있는 파장이 없던 것을 채우려고 보탰다. 원자선은 위와 같은 규칙(NIST 강한 선 표, 공기 중, 200–900 nm 중성 원자선 상대 세기 상위 4개)으로 기계적으로 뽑았고, 분자 밴드는 출처 1편과 문장 하나로 묶어 독립 검증을 받은 것(채택·조건부)만 실었다. 분광 선목록·고전 분광 문헌에서 온 범위는 식각 장비에서 실제 감시에 쓰는 위치와 다를 수 있다.</p>
  {'<div class="tbl"><table><thead><tr><th>화학종</th><th>스펙트럼</th><th>파장 (nm, 공기)</th><th>출처</th></tr></thead><tbody>' + bxa + '</tbody></table></div>' if bxa else ''}
  {'<div class="tbl"><table><thead><tr><th>화학종</th><th>위치 (nm)</th><th>전이</th><th>조건</th><th>판정</th><th>출처</th></tr></thead><tbody>' + bxm + '</tbody></table></div>' if bxm else ''}
"""

page = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>식각 화학·OES 파장</title>
<style>
  :root {{ --bg:#f7f8fb; --card:#fff; --ink:#1f2937; --muted:#6b7280; --line:#e5e7eb; --accent:#2563eb;
          --ok:#166534; --ok-bg:#dcfce7; --cd:#1e40af; --cd-bg:#dbeafe; --hold:#92400e; --hold-bg:#fef3c7; --rej:#991b1b; --rej-bg:#fee2e2; }}
  * {{ box-sizing:border-box; }}
  html {{ color-scheme: light; }}
  body {{ margin:0; background:var(--bg); color:var(--ink); font:15px/1.7 "Pretendard","Malgun Gothic","Apple SD Gothic Neo",system-ui,sans-serif; }}
  .wrap {{ max-width:1100px; margin:0 auto; padding:40px 16px 80px; }}
  h1 {{ font-size:28px; margin:0 0 6px; line-height:1.3; }}
  h2 {{ font-size:21px; margin:40px 0 12px; padding-bottom:6px; border-bottom:2px solid var(--line); }}
  p, ul {{ max-width:84ch; }} a {{ color:var(--accent); }}
  .sub, .note {{ color:var(--muted); }} .note {{ font-size:13px; }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px 18px; margin:12px 0; }}
  table {{ border-collapse:collapse; width:100%; font-size:14px; background:#fff; }}
  th, td {{ border:1px solid var(--line); padding:7px 9px; text-align:left; vertical-align:top; }}
  th {{ background:#f3f6fb; white-space:nowrap; }}
  td.num {{ font-variant-numeric:tabular-nums; }}
  .tbl {{ overflow-x:auto; border-radius:10px; }}
  .tag {{ display:inline-block; font-size:12px; font-weight:700; padding:1px 9px; border-radius:999px; white-space:nowrap; }}
  .adopt {{ background:var(--ok-bg); color:var(--ok); }} .cond {{ background:var(--cd-bg); color:var(--cd); }}
  .hold {{ background:var(--hold-bg); color:var(--hold); }} .reject {{ background:var(--rej-bg); color:var(--rej); }}
  .sp {{ display:inline-block; font-size:12.5px; border:1px solid var(--line); border-radius:6px; padding:0 6px; margin:1px 2px; background:#fff; }}
  .sp.feed {{ background:#f3f4f6; color:#4b5563; }} .sp.rep {{ border-color:#16a34a; color:#166534; }}
  .sp.w::after {{ content:" ✦"; color:#7c3aed; }}
  .sp.w2::after {{ content:" ✧"; color:#0891b2; }}
  h3 {{ font-size:17px; margin:26px 0 8px; }}
  td.wl {{ font-size:12.5px; min-width:190px; }} td.wl div {{ margin:1px 0; }}
  .wv {{ font-variant-numeric:tabular-nums; white-space:nowrap; }} .wv.v {{ color:#6d28d9; }} .wv.s {{ color:#0e7490; }} .wv.r {{ color:#166534; font-weight:600; }}
  .bar {{ display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin:8px 0 10px; }}
  input, select {{ font:inherit; padding:6px 10px; border:1px solid var(--line); border-radius:8px; background:#fff; }}
  input {{ flex:1 1 240px; }}
  code {{ background:#eef2f7; padding:1px 5px; border-radius:5px; font-size:13px; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>식각 화학 조합 · OES 기준 파장</h1>
  <p class="sub" style="margin-top:6px"><a href="../index.html">← 목차</a> · 2026-10-11 (조합 보완 2026-10-15) · 별도 프로젝트 “OES Assistant”의 데이터(버전 {e(K["version"])}, 파장 {e(SP["version"])})를 읽기 전용으로 옮김</p>
  <p>막질과 공급 가스 조합 {len(items)}개마다 <b>생성될 수 있는 화학종 후보</b>와, 그중 출처가 확인된 <b>OES 기준 파장</b>을 정리했다. 원래 앱은 레시피를 넣으면 언어 모델이 후보를 추론하는 서버 프로그램이고, 여기에는 그 앱이 기준으로 쓰는 정리된 데이터만 옮겼다(모델 호출 없음). 용어는 <a href="a20_etch_knowledge_graph.html">지식 그래프</a>의 광방출 분광(OES)·Actinometry 노드와 연결된다.</p>

  <div class="card">
    <b>해석 범위</b> — 이 데이터가 말하지 않는 것
    <ul>{limits}</ul>
    <p class="note">화학종 표시: <span class="sp feed">공급 가스</span> <span class="sp">추론 후보</span> <span class="sp rep">문헌 보고</span> <span class="sp w">기준 파장 있음</span> <span class="sp w2">보완 위치 있음</span> · 전체 {sum(ev.values())}개 중 추론 {ev["chemical_inference"]}, 공급 가스 {ev["provided_feed"]}, 문헌 보고 {ev["reported_in_reference"]}.</p>
  </div>

  <h2 id="spectra">OES 기준 파장 ({len(SP["species"])}종 {len(VER)}선)</h2>
  <p>원자선·이온선은 NIST 원소별 강한 선 표(공기 중 Å → nm, ÷10), 분자 위치는 논문 1편의 진단 파장이다. <b>2026-10-11에 {len(VER)}개 값을 모두 원문 표와 기계적으로 대조해 {n_ok}개 일치</b>를 확인했다(⚠ 표시는 불일치).</p>
  <div class="tbl"><table>
    <thead><tr><th>화학종</th><th>종류</th><th>파장 (nm)</th><th>매질</th><th>출처</th></tr></thead>
    <tbody>{spectra_tbl}</tbody>
  </table></div>
  <p class="note">원자선은 그 원자(여기 상태)의 방출이고 모분자 전체를 특정하지 않는다. 기준 목록에 없다고 발광이 없다는 뜻은 아니다. 가까운 선은 분광기 분해능에 따라 겹칠 수 있다(예: CF₂ 251.9 nm와 Si 251.92 nm).</p>

{supp_html}{bx_html}
  <h2 id="combos">막질 × 기체 조합 ({len(items)}개)</h2>
  {f'<p>OES Assistant 원본 {n_base}개에 이 사이트에서 따로 조사한 <b>보완 조합 {len(items) - n_base}개</b>(ID <code>EX-</code>, 2026-10-15)를 더했다. 보완 조합은 막질·기체·핵심 결과를 출처 1편과 한 문장으로 묶어 독립 검증 에이전트가 원문과 대조했다(조합별 “출처 검증” 표시). 화학종 후보 중 출처가 직접 측정한 것만 <span class="sp rep">문헌 보고</span>이고, 나머지는 공급 가스와 막 원소로부터의 추론이다.</p>' if EX else ''}
  <p class="note"><b>관련 OES 파장</b> 열: 조합의 화학종 후보마다 이 페이지에 근거가 있는 위치를 모았다. <span class="wv v">보라</span>=위 기준 파장(원문 대조 완료), <span class="wv s">청록</span>=보완 원자선(NIST 강한 선 상위 4개)·분자 방출 위치(독립 검증), <span class="wv r">초록</span>=그 조합의 출처가 직접 측정한 값. 값에 마우스를 올리면 종류가 보인다. “기준 없음”은 이 페이지에 근거 있는 발광 위치가 없다는 뜻이며 발광하지 않는다는 뜻은 아니다. 원자선은 그 원자의 방출일 뿐 어느 모분자에서 왔는지는 알려 주지 않는다.</p>
  <div class="bar">
    <input id="q" type="search" placeholder="막질·기체·화학종 검색 (예: SiO2, HBr, CF2)">
    <select id="fam"><option value="">모든 막질 계열</option>{"".join(f'<option>{e(f)}</option>' for f in fams)}</select>
    <span class="note" id="cnt"></span>
  </div>
  <div class="tbl"><table>
    <thead><tr><th>ID</th><th>막질</th><th>기체 · 방식</th><th>화학종 후보</th><th>관련 OES 파장 (nm)</th><th>근거</th></tr></thead>
    <tbody id="rows"></tbody>
  </table></div>

  <h2 id="verify">검증</h2>
  <ul>
    <li><b>기준 파장</b>: {len(VER)}개 전부 원문 표·논문과 대조 → {n_ok}개 일치.</li>
    <li><b>조합의 출처</b>: 출처마다 1개씩 뽑은 표본 {len(CV)}개를 독립 검증 에이전트(웹 원문만 보고 작성 과정은 모름)가 원문과 대조했다{": " + ", ".join(f"{VERD.get(k, (k,))[0]} {n}" for k, n in cv_count.items()) if CV else " (진행 중)"}. 검증 대상은 “출처가 이 막질을 이 기체로 식각하는 예를 제시한다”까지이며, 화학종 후보(대부분 추론)는 검증 대상이 아니다.</li>
    {f'<li><b>보완 조합</b>({len(items) - n_base}개): 조합마다 출처의 핵심 결과 한 문장을 독립 검증 → ' + ", ".join(f"{DECL[k][0] if k in DECL else k} {n}" for k, n in ex_dec.items()) + '. 주장별 상태는 <a href="claims_status.html">검증 현황</a>.</li>' if EX else ''}
  </ul>
  {'<div class="tbl"><table><thead><tr><th>주장</th><th>조합</th><th>막질 · 기체</th><th>판정</th><th>검증자 메모</th></tr></thead><tbody>' + cv_rows + '</tbody></table></div>' if CV else ''}

  <h2 id="sources">출처 ({len(sources)}개)</h2>
  <div class="tbl"><table>
    <thead><tr><th>ID</th><th>출처</th><th>종류</th></tr></thead>
    <tbody>{src_rows}</tbody>
  </table></div>
</div>
<script>
const ITEMS = {json.dumps(items, ensure_ascii=False, separators=(",", ":"))};
const SRC = {json.dumps(src_js, ensure_ascii=False, separators=(",", ":"))};
const VERD = {json.dumps({k: list(v) for k, v in VERD.items()}, ensure_ascii=False)};
const esc = s => String(s).replace(/[&<>"]/g, c => ({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}})[c]);
const cls = {{provided_feed:"feed", reported_in_reference:"rep", chemical_inference:""}};
function render() {{
  const q = document.getElementById("q").value.trim().toLowerCase(), fam = document.getElementById("fam").value;
  const out = ITEMS.filter(x => (!fam || x.fam === fam) && (!q || JSON.stringify([x.id, x.film, x.gas, x.sp.map(s => s.f), x.note]).toLowerCase().includes(q)));
  document.getElementById("cnt").textContent = out.length + "개";
  document.getElementById("rows").innerHTML = out.map(x => `<tr id="${{x.id}}"><td>${{x.id}}</td><td>${{esc(x.film)}}<div class="note">${{esc(x.fam)}}</div></td>`
    + `<td>${{x.gas.map(esc).join(" + ")}}<div class="note">${{esc(x.mode)}}</div></td>`
    + `<td>${{x.sp.map(s => `<span class="sp ${{cls[s.e] || ""}}${{s.w ? " w" : ""}}${{s.w2 ? " w2" : ""}}">${{esc(s.f)}}</span>`).join("")}}${{x.note ? `<div class="note">${{esc(x.note)}}</div>` : ""}}</td>`
    + `<td class="wl">${{x.wl.map(w => `<div><b>${{esc(w[0])}}</b> ${{w[1].map(r => `<span class="wv ${{r[0]}}" title="${{esc(r[2])}}">${{esc(r[1])}}</span>`).join(" ")}}</div>`).join("")}}`
    + `${{x.nowl.length ? `<div class="note">기준 없음: ${{x.nowl.map(esc).join(", ")}}</div>` : ""}}</td>`
    + `<td>${{esc(x.basis)}}<div>${{x.src.map(s => SRC[s] ? `<a href="${{esc(SRC[s][1])}}" target="_blank" rel="noopener">${{esc(SRC[s][0])}}</a>` : esc(s)).join("<br>")}}</div>`
    + `${{x.v ? `<span class="tag ${{VERD[x.v][1]}}">표본 검증: ${{VERD[x.v][0]}}</span>` : ""}}`
    + `${{x.d ? `<span class="tag ${{x.d[1]}}">출처 검증: ${{x.d[0]}}</span>` : ""}}</td></tr>`).join("");
}}
document.getElementById("q").addEventListener("input", render);
document.getElementById("fam").addEventListener("change", render);
const u = new URLSearchParams(location.search).get("q"); if (u) document.getElementById("q").value = u;
render();
</script>
</body>
</html>
"""
sys.path.insert(0, str(ROOT / "tools"))
import paper_links  # noqa: E402  레퍼런스 논문 요약 링크
page = paper_links.link_oes(page)
(ROOT / "research/oes_etch_chemistry.html").write_text(page, encoding="utf-8")
print("ok", len(items), "combos", len(VER), "lines", n_ok, "ok", len(CV), "verified")
