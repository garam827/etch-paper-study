"""OES 지식 그래프 (#57): 흩어진 OES 원본을 노드·관계 하나로 합치고, 질의·검사·RAG 카드를 만든다.

    python tools/oes_graph.py stats    # 노드·관계 수, 원소 보존 검사, 자동 계산한 가까운 선
    python tools/oes_graph.py check    # 스키마 검사 + 시험 문항(kb/oes/graph_tests.json) — CI에서 돌린다

원본(손으로 고치는 곳):
  kb/oes/app/{etch_knowledge,spectra}.json   OES Assistant(비공개 앱) 데이터의 공개 사본
  kb/oes/verify/{wavelength_verify,combo_verify}.json   #47 검증 결과(기준 파장 원문 대조, 조합 표본 검증)
  kb/oes/combos_extra.json   보완 조합(#54) · kb/claims/oes_extra.json 그 검증 상태
  kb/oes/bands_extra.json    보완 원자선·분자 밴드(#55) · kb/claims/oes_bands.json
  tools/oes_supplement.json  보완 원자선·분자 방출·종말점·actinometry·가까운 선(#47)
  kb/oes/conditioning.json   챔버 conditioning·시즈닝·aging: 벽 상태·단계·재결합·감시 신호(#59) · kb/claims/oes_conditioning.json
결과물(build_site.py가 만든다): research/oes_knowledge_graph.html, research/oes_kg/graph.json, research/oes_kg/cards.jsonl

수치 질의(파장 ± 허용오차)는 임베딩이 아니라 숫자 비교로 결정적으로 푼다. RAG 카드는 노드 단위이고 근거(주장 ID·출처)를 함께 싣는다.
"""
import hashlib
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KB = ROOT / "kb"


def _load(p, default=None):
    f = ROOT / p
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else default


# ---------- 원소 ----------
_EL = re.compile(r"[A-Z][a-z]?")
ELEMENTS = set("H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Ti Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr Zr Mo Ru Rh Pd Ag In Sn Sb Te I Xe Hf Ta W Re Os Ir Pt Au".split())


def elements_of(formula):
    """화학식의 원소 집합 (괄호·숫자·전하·n/m 첨자는 무시)."""
    return {e for e in _EL.findall(formula) if e in ELEMENTS}


# ---------- 파장 텍스트 → 수치 ----------
_NUM = re.compile(r"(\d{3}(?:\.\d+)?)")


def parse_nm(text):
    """'385–390', '529.5 · 563.2', '≈236 (γ, 230–237 적분)' → 점 목록과 구간 목록."""
    pts, rng = [], []
    s = str(text)
    for a, b in re.findall(r"(\d{3}(?:\.\d+)?)\s*[–-]\s*(\d{3}(?:\.\d+)?)", s):
        lo, hi = float(a), float(b)
        if 150 <= lo < hi <= 1100:
            rng.append([lo, hi])
    s2 = re.sub(r"(\d{3}(?:\.\d+)?)\s*[–-]\s*(\d{3}(?:\.\d+)?)", " ", s)
    s2 = re.sub(r"\(\s*\d+\s*,\s*\d+\s*\)", " ", s2)  # (0,1) 같은 진동 표기
    for m in _NUM.findall(s2):
        v = float(m)
        if 150 <= v <= 1100:
            pts.append(v)
    return sorted(set(pts)), rng


def _src_key(title, url):
    return "s_" + hashlib.sha1((url or title).encode("utf-8")).hexdigest()[:10]


DEC_LABEL = {"adopt": "채택", "conditional": "조건부", "hold": "보류", "reject": "제외", None: "미검증"}


def build():
    K = _load("kb/oes/app/etch_knowledge.json")
    SP = _load("kb/oes/app/spectra.json")
    VER = _load("kb/oes/verify/wavelength_verify.json", [])
    CV = _load("kb/oes/verify/combo_verify.json", {})
    X = _load("kb/oes/combos_extra.json", {"items": [], "films": {}, "sources": {}, "modes": {}})
    BX = _load("kb/oes/bands_extra.json", {"atomic": {}, "mol": []})
    SUP = _load("tools/oes_supplement.json", {"atomic": {}, "mol": [], "epd": [], "act": [], "ovl": []})
    XS = {c["id"]: c for c in (_load("kb/claims/oes_extra.json", {"claims": []}) or {"claims": []})["claims"]}
    BS = {c["id"]: c for c in (_load("kb/claims/oes_bands.json", {"claims": []}) or {"claims": []})["claims"]}

    nodes, edges = {}, []

    def node(nid, typ, label, **a):
        if nid not in nodes:
            nodes[nid] = {"id": nid, "type": typ, "label": label, **a}
        else:
            for k, v in a.items():
                nodes[nid].setdefault(k, v)
        return nid

    def edge(s, t, rel, **a):
        edges.append({"s": s, "t": t, "rel": rel, **a})

    def src_node(key, title, url, kind=""):
        return node("src:" + key, "source", title, url=url, kind=kind)

    def element_links(nid, els):
        for e_ in sorted(els):
            node("el:" + e_, "element", e_)
            edge(nid, "el:" + e_, "has_element")

    modes = {**K["modes"], **X.get("modes", {})}
    combo_verdict = {v["combo"]: v["verdict"] for v in CV.values()}

    # 출처
    for k, v in {**K["sources"], **SP["sources"], **X.get("sources", {})}.items():
        src_node(k, v["title"], v["url"], v.get("kind", ""))

    def species(f):
        nid = "sp:" + f
        if nid not in nodes:
            node(nid, "species", f)
            element_links(nid, elements_of(f))
        return nid

    def gas(g):
        nid = "gas:" + g
        if nid not in nodes:
            node(nid, "gas", g)
            element_links(nid, elements_of(g))
        return nid

    def film(fid, name, family, els, aliases=()):
        nid = "film:" + fid
        if nid not in nodes:
            node(nid, "film", name, family=family, aliases=list(aliases))
            element_links(nid, els)
        return nid

    EVMAP = {"provided_feed": "feed", "chemical_inference": "inferred", "reported_in_reference": "reported"}
    # 1) 원본 조합 67개
    for x in K["items"]:
        c = node("combo:" + x["id"], "combo", x["id"], film_name=x["film"]["name"], gases=x["gases"], mode=x["mode_label"],
                 basis=x["basis"], note=x.get("note", ""), origin="OES Assistant", sample_verdict=combo_verdict.get(x["id"]))
        f = film(x["film_id"], x["film"]["name"], x["family_label"], x["film"]["elements"], x["film"].get("aliases", []))
        edge(c, f, "etches")
        for g in x["gases"]:
            edge(c, gas(g), "feeds")
        for s in x["species"]:
            edge(c, species(s["formula"]), "may_produce", evidence=EVMAP[s["evidence"]], origin=",".join(s.get("origins", [])))
        for k in x["sources"]:
            edge(c, "src:" + k, "cites")

    # 2) 보완 조합(#54)
    for x in X.get("items", []):
        fx = X["films"][x["film"]]
        fid = fx.get("same_as", "x_" + x["film"])
        cl = XS.get(x.get("claim", "OE" + x["id"][3:]), {})
        d = cl.get("decision")
        if d in ("hold", "reject"):
            continue
        c = node("combo:" + x["id"], "combo", x["id"], film_name=fx["name"], gases=x["gases"], mode=modes.get(x["mode"], x["mode"]),
                 basis="보완 조사(2026-10-15)", note=x.get("note", ""), origin="이 사이트 보완(#54)", claim=cl.get("id"), decision=d)
        f = film(fid, fx["name"], fx["family_label"], fx["elements"])
        edge(c, f, "etches")
        for g in x["gases"]:
            edge(c, gas(g), "feeds")
        ev = {"feed": "feed", "rep": "reported", "": "inferred"}
        for s, k in x["sp"]:
            edge(c, species(s), "may_produce", evidence=ev[k])
        for k in x["src"]:
            edge(c, "src:" + k, "cites")
        if cl.get("id"):
            node("claim:" + cl["id"], "claim", cl["id"], statement=cl["statement"], decision=d, conditions=cl.get("conditions", ""))
            edge("claim:" + cl["id"], c, "supports")
        for sp_, txt in x.get("wl", {}).items():
            pts, rng = parse_nm(txt)
            em = node(f"em:{sp_}:{x['id']}", "emission", f"{sp_} {txt}", species=sp_, text=txt, points=pts, ranges=rng,
                      tier="combo", decision=d, note=f"{x['id']} 출처가 측정")
            edge(species(sp_), em, "emits")
            for k in x["src"]:
                edge(em, "src:" + k, "cites")

    # 3) 기준 파장(원문 대조 40선)
    ok = {(v[0], v[1]): v[3] for v in VER}
    for name, s in SP["species"].items():
        em = node(f"em:{name}:ref", "emission", f"{name} 기준 파장", species=name, kind=s["kind"], medium=s["medium"],
                  points=sorted(s["wavelengths_nm"]), ranges=[], tier="ref",
                  verified=all(ok.get((name, w), False) for w in s["wavelengths_nm"]))
        edge(species(name), em, "emits")
        edge(em, "src:" + s["source_id"], "cites")

    # 4) 보완 원자선 (NIST 강한 선)
    for A in (SUP.get("atomic", {}), BX.get("atomic", {})):
        for name, v in A.items():
            key = _src_key("NIST", v["url"])
            src_node(key, f"NIST · Strong Lines of {name}", v["url"], "database")
            em = node(f"em:{name}:nist", "emission", f"{name} NIST 강한 선", species=name, kind="atomic_line", spectrum=v["spectrum"],
                      points=sorted(l["nm"] for l in v["lines"]), ranges=[], tier="supp", medium="air")
            edge(species(name), em, "emits")
            edge(em, "src:" + key, "cites")

    # 5) 분자 방출 위치
    def cite_rows(nid, rows):
        for title, url in rows:
            key = _src_key(title, url)
            src_node(key, title, url)
            edge(nid, "src:" + key, "cites")

    for m in SUP.get("mol", []):
        pts, rng = parse_nm(m["nm"])
        em = node(f"em:{m['sp']}:{m['id']}", "emission", f"{m['sp']} {m['nm']}", species=m["sp"], kind="molecular_band", text=m["nm"],
                  transition=m.get("tr", ""), cond=m.get("cond", ""), points=pts, ranges=rng, tier="supp", claim=m["id"], decision=m["decision"])
        edge(species(m["sp"]), em, "emits")
        cite_rows(em, m["src"])
    for m in BX.get("mol", []):
        pts, rng = parse_nm(m["nm"])
        em = node(f"em:{m['sp']}:{m['id']}", "emission", f"{m['sp']} {m['nm']}", species=m["sp"], kind="molecular_band", text=m["nm"],
                  transition=m.get("tr", ""), cond=m.get("cond", ""), points=pts, ranges=rng, tier="supp", claim=m["id"], decision=m["decision"])
        edge(species(m["sp"]), em, "emits")
        cite_rows(em, [[m["title"], m["url"]]])

    # 6) 용도: 종말점·actinometry·가까운 선
    sp_names = sorted({n["label"] for n in nodes.values() if n["type"] == "species"}, key=lambda s: (-len(s), s))

    def mentioned(text):
        found, t = [], " " + re.sub(r"[₀-₉]", lambda c: str("₀₁₂₃₄₅₆₇₈₉".index(c.group())), text) + " "
        for s in sp_names:
            if re.search(r"(?<![A-Za-z])" + re.escape(s) + r"(?![a-z0-9+])", t):
                found.append(s)
                t = t.replace(s, " ")
        return found

    for typ, rows, lab in (("epd", SUP.get("epd", []), lambda r: f"{r['film']} · {r['sig']}"),
                           ("actinometry", SUP.get("act", []), lambda r: f"{r['t']} actinometry · {r['pair']}"),
                           ("overlap", SUP.get("ovl", []), lambda r: f"가까운 선 {r['pair']} · {r['nm']}")):
        for r in rows:
            u = node(f"use:{r['id']}", "use", lab(r), use=typ, claim=r["id"], decision=r["decision"], cond=r.get("cond", ""),
                     film_text=r.get("film", ""), chem=r.get("chem", ""), signal=r.get("sig", r.get("pair", "")),
                     points=parse_nm(r.get("sig", r.get("pair", r.get("nm", ""))) + " " + r.get("nm", ""))[0])
            text = r.get("sig", "") + " " + r.get("pair", "") + " " + r.get("t", "")
            for s in mentioned(text):
                edge(u, species(s), "involves")
            cite_rows(u, r["src"])

    # 7) 보완 밴드 검증 주장 노드
    for cid, c in BS.items():
        node("claim:" + cid, "claim", cid, statement=c["statement"], decision=c["decision"], conditions=c.get("conditions", ""))
        tgt = next((n for n in nodes.values() if n["type"] == "emission" and n.get("claim") == cid), None)
        if tgt:
            edge("claim:" + cid, tgt["id"], "supports")

    # 8) 챔버 conditioning·시즈닝·aging (#59): 벽 상태 → (재결합·방출) → 화학종 → 방출선
    #    막질 축과 별개로, 벽 피막을 만들고 지우는 단계와 그 동안의 OES 신호를 잇는다.
    CO = _load("kb/oes/conditioning.json", {"facts": [], "sources": {}})
    CS = {c["id"]: c for c in (_load("kb/claims/oes_conditioning.json", {"claims": []}) or {"claims": []})["claims"]}
    for k, v in CO.get("sources", {}).items():
        src_node(k, v["title"], v["url"], v.get("kind", ""))

    def wall(w):
        return node("wall:" + w, "wall", w, kg="a20_etch_knowledge_graph.html#i_aging")

    def step(s):
        return node("step:" + s, "step", s)

    for f in CO.get("facts", []):
        cid = f["claim"]
        cl = CS.get(cid, {})
        d = cl.get("decision")
        if d in ("hold", "reject"):
            continue
        cn = node("claim:" + cid, "claim", cid, statement=cl.get("statement", ""), decision=d, conditions=cl.get("conditions", ""))
        edge(cn, "src:" + f["src"], "cites")
        touched, t = [], f["type"]
        sps = f.get("species", [])
        sps = [sps] if isinstance(sps, str) else sps
        if t in ("removes", "removes2"):
            for s in f.get("steps") or [f["step"]]:
                edge(step(s), wall(f["wall"]), "removes", claim=cid)
                touched.append("step:" + s)
            touched.append("wall:" + f["wall"])
            if f.get("also_forms_by"):
                edge(step(f["also_forms_by"]), wall(f["wall"]), "forms", claim=cid)
        elif t == "forms":
            edge(step(f["process"]), wall(f["wall"]), "forms", claim=cid)
            touched += ["step:" + f["process"], "wall:" + f["wall"]]
            for s in sps:
                edge(wall(f["wall"]), species(s), "affects", effect=f.get("effect", ""), claim=cid)
        elif t in ("affects", "source_from_wall", "risk"):
            for s in sps:
                edge(wall(f["wall"]), species(s), "affects", effect=f.get("effect", f.get("label", "")), claim=cid)
            touched.append("wall:" + f["wall"])
            if f.get("removes_by"):
                edge(step(f["removes_by"]), wall(f["wall"]), "removes", claim=cid)
            if f.get("forms_by"):
                edge(step(f["forms_by"]), wall(f["wall"]), "forms", claim=cid)
        elif t == "gamma":
            for w, val in f["values"].items():
                edge(wall(w), species(f["species"]), "affects", effect=f"재결합 계수 γ = {val}", gamma=val, claim=cid)
                touched.append("wall:" + w)
        elif t == "step_effect":
            edge(step(f["step"]), wall(f["wall"]), "treats", effect=f.get("effect", ""), claim=cid)
            touched += ["step:" + f["step"], "wall:" + f["wall"]]
            for s in sps:
                edge("step:" + f["step"], species(s), "involves", claim=cid)
        if "monitor" in f or t == "monitor":
            m = f.get("monitor", f)
            u = node("use:" + cid, "use", m["label"], use="conditioning", claim=cid, decision=d, signal=m["signal"],
                     cond=f.get("step", ""), points=parse_nm(m["signal"])[0])
            for s in m.get("species", []):
                edge(u, species(s), "involves")
            if f.get("step"):
                edge(u, step(f["step"]), "during")
            edge(u, "src:" + f["src"], "cites")
            touched.append(u)
        for key, field in (("wl", "points"), ("wl_range", "ranges")):
            for sp_, txt in f.get(key, {}).items():
                pts, rng = parse_nm(txt)
                em = node(f"em:{sp_}:{cid}", "emission", f"{sp_} {txt}", species=sp_, text=txt, points=pts, ranges=rng,
                          tier="cond", claim=cid, decision=d, note="챔버 conditioning 문헌이 사용한 위치")
                edge(species(sp_), em, "emits")
                edge(em, "src:" + f["src"], "cites")
                touched.append(em)
        for x in dict.fromkeys(touched):
            edge(cn, x, "supports")

    # 9) 자동 계산: 서로 다른 화학종의 점 파장이 0.5 nm 안 (분해능 주의, 검증 아님)
    pts = sorted((p, n["species"], n["id"]) for n in nodes.values() if n["type"] == "emission" for p in n.get("points", []))
    near = set()
    for i, (p, s, nid) in enumerate(pts):
        for q, s2, nid2 in pts[i + 1:]:
            if q - p > 0.5:
                break
            if s != s2:
                near.add((min(nid, nid2), max(nid, nid2), round(p, 1), round(q, 1)))
    for a, b, p, q in sorted(near):
        edge(a, b, "near", nm=[p, q], computed=True)

    meta = {"generated_from": "kb/oes (#57)", "counts": {}}
    for n in nodes.values():
        meta["counts"][n["type"]] = meta["counts"].get(n["type"], 0) + 1
    meta["edges"] = len(edges)
    return {"meta": meta, "nodes": sorted(nodes.values(), key=lambda n: (n["type"], n["id"])), "edges": edges}


# ---------- 질의 (페이지 JS와 같은 규칙) ----------
class Q:
    def __init__(self, g):
        self.g = g
        self.n = {x["id"]: x for x in g["nodes"]}
        self.out, self.inn = {}, {}
        for e in g["edges"]:
            self.out.setdefault(e["s"], []).append(e)
            self.inn.setdefault(e["t"], []).append(e)

    def emissions_of(self, sp):
        return [self.n[e["t"]] for e in self.out.get("sp:" + sp, []) if e["rel"] == "emits"]

    def recipe(self, film_q, gases):
        """막질 이름(부분 일치)과 기체 집합 → 맞는 조합들과 화학종·파장."""
        fq, gs = film_q.lower(), set(gases)
        res = []
        for c in (x for x in self.g["nodes"] if x["type"] == "combo"):
            fl = next(self.n[e["t"]] for e in self.out[c["id"]] if e["rel"] == "etches")
            names = [fl["label"].lower()] + [a.lower() for a in fl.get("aliases", [])]
            if not any(fq in nm for nm in names):
                continue
            if gs and not gs <= set(c["gases"]):
                continue
            sp = [(self.n[e["t"]]["label"], e.get("evidence")) for e in self.out[c["id"]] if e["rel"] == "may_produce"]
            res.append({"combo": c["id"], "gases": c["gases"], "species": sp,
                        "emissions": {s: [m["id"] for m in self.emissions_of(s)] for s, _ in sp if self.emissions_of(s)}})
        return res

    def peak(self, nm, tol=1.0):
        """관측 피크(nm ± tol) → 방출 근거와 화학종."""
        hits = []
        for m in (x for x in self.g["nodes"] if x["type"] == "emission"):
            d = min([abs(p - nm) for p in m.get("points", [])] + [0 if lo - tol <= nm <= hi + tol else 1e9 for lo, hi in m.get("ranges", [])] + [1e9])
            if d <= tol:
                hits.append((d, m["species"], m["id"]))
        return sorted(hits)

    def epd(self, film_q):
        return [u for u in self.g["nodes"] if u["type"] == "use" and u["use"] == "epd" and film_q.lower() in u["film_text"].lower()]

    def actinometry(self, target):
        return [u for u in self.g["nodes"] if u["type"] == "use" and u["use"] == "actinometry" and u["label"].startswith(target + " ")]

    def sources(self, nid):
        return [self.n[e["t"]] for e in self.out.get(nid, []) if e["rel"] == "cites"]

    def conditioning(self, term):
        """벽 상태 이름(부분 일치) → 만드는 단계·지우는 단계·화학종 영향, 그리고 conditioning 감시 신호."""
        tq, res = term.lower(), []
        for w in (x for x in self.g["nodes"] if x["type"] == "wall" and term.lower() in x["label"].lower()):
            ins = self.inn.get(w["id"], [])
            res.append({"wall": w["label"],
                        "formed_by": [self.n[e["s"]]["label"] for e in ins if e["rel"] == "forms"],
                        "removed_by": [self.n[e["s"]]["label"] for e in ins if e["rel"] == "removes"],
                        "affects": [(self.n[e["t"]]["label"], e.get("effect", "")) for e in self.out.get(w["id"], []) if e["rel"] == "affects"]})
        mons = [u for u in self.g["nodes"] if u["type"] == "use" and u["use"] == "conditioning"
                and (tq in u["label"].lower() or tq in u["signal"].lower() or tq in u.get("cond", "").lower())]
        return res, mons


# ---------- RAG 카드 ----------
REL_KO = {"etches": "식각 대상", "feeds": "공급 가스", "may_produce": "생성 후보", "has_element": "원소", "emits": "방출",
          "cites": "출처", "supports": "근거 주장", "involves": "관련 화학종", "near": "가까운 선(자동 계산)",
          "forms": "벽 피막 형성", "removes": "벽 피막 제거", "affects": "벽이 화학종에 주는 영향", "treats": "벽 처리", "during": "단계"}
TYPE_KO = {"combo": "막질×기체 조합", "film": "막질", "gas": "공급 가스", "species": "화학종", "emission": "방출선·밴드",
           "use": "용도(종말점·actinometry·가까운 선·conditioning 감시)", "claim": "검증 주장", "source": "출처", "element": "원소",
           "wall": "챔버 벽 상태", "step": "시즈닝·세정·식각 단계"}


def cards(g):
    q = Q(g)
    out = []
    for n in g["nodes"]:
        if n["type"] == "element":
            continue
        nb = []
        for e in q.out.get(n["id"], []) + q.inn.get(n["id"], []):
            other = e["t"] if e["s"] == n["id"] else e["s"]
            if other.startswith("el:") and n["type"] != "species":
                continue
            o = q.n[other]
            tag = f"{REL_KO.get(e['rel'], e['rel'])}{'('+e['evidence']+')' if e.get('evidence') else ''}{' — '+e['effect'] if e.get('effect') else ''}"
            nb.append((tag, o["label"], other))
        props = []
        for k in ("film_name", "gases", "mode", "note", "text", "transition", "cond", "signal", "statement", "conditions", "kind", "medium"):
            if n.get(k):
                v = n[k]
                props.append(f"{k}: {' + '.join(v) if isinstance(v, list) else v}")
        if n.get("points"):
            props.append("파장(nm): " + ", ".join(f"{p:g}" for p in n["points"]))
        if n.get("ranges"):
            props.append("구간(nm): " + ", ".join(f"{a:g}–{b:g}" for a, b in n["ranges"]))
        dec = n.get("decision")
        cites = [{"title": s["label"], "url": s.get("url", "")} for s in q.sources(n["id"])]
        text = f"[{TYPE_KO[n['type']]}] {n['label']}" + (f" — 판정: {DEC_LABEL.get(dec, dec)}" if "decision" in n else "") + "\n" + \
               "\n".join(props) + "\n" + "\n".join(f"- {t}: {l}" for t, l, _ in nb[:40])
        out.append({"id": n["id"], "type": n["type"], "title": n["label"], "text": text.strip(),
                    "neighbors": [i for _, _, i in nb], "citations": cites, "decision": dec})
    return out


# ---------- 결과물 ----------
def render_json():
    return json.dumps(build(), ensure_ascii=False, separators=(",", ":")) + "\n"


def render_cards():
    return "".join(json.dumps(c, ensure_ascii=False, separators=(",", ":")) + "\n" for c in cards(build()))


def render_page():
    g = build()
    tpl = (ROOT / "tools/templates/oes_knowledge_graph.html").read_text(encoding="utf-8")
    c = g["meta"]["counts"]
    data = json.dumps(g, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    cds = json.dumps([{k: x[k] for k in ("id", "text", "citations")} for x in cards(g)], ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    page = tpl.replace("__GRAPH__", data).replace("__CARDS__", cds)
    for k in ("combo", "film", "gas", "species", "emission", "use", "claim", "source", "wall", "step"):
        page = page.replace(f"__N_{k.upper()}__", str(c.get(k, 0)))
    return page.replace("__N_EDGES__", str(g["meta"]["edges"]))


# ---------- 검사 ----------
def check(g, verbose=False):
    errs, warns = [], []
    ids = {n["id"] for n in g["nodes"]}
    for e in g["edges"]:
        if e["s"] not in ids or e["t"] not in ids:
            errs.append(f"끊긴 관계 {e['s']} -{e['rel']}-> {e['t']}")
    q = Q(g)
    # 원소 보존: 추론 후보의 원소는 막질·공급 가스 원소 안에 있어야 한다
    for c in (n for n in g["nodes"] if n["type"] == "combo"):
        have = set()
        for e in q.out[c["id"]]:
            if e["rel"] in ("etches", "feeds"):
                have |= {x["t"][3:] for x in q.out.get(e["t"], []) if x["rel"] == "has_element"}
        for e in q.out[c["id"]]:
            if e["rel"] == "may_produce" and e.get("evidence") == "inferred":
                els = {x["t"][3:] for x in q.out.get(e["t"], []) if x["rel"] == "has_element"}
                if not els <= have:
                    warns.append(f"원소 보존: {c['id']} {q.n[e['t']]['label']} 의 {sorted(els - have)} 가 막질·기체에 없음")
    for n in g["nodes"]:
        if n.get("url") and not re.match(r"https?://", n["url"]):
            errs.append(f"http(s)가 아닌 링크 {n['id']}: {n['url'][:40]}")  # 페이지가 그대로 href로 쓴다
        if n["type"] == "emission" and not (n.get("points") or n.get("ranges")):
            errs.append(f"파장 없는 방출 {n['id']}")
    tests = _load("kb/oes/graph_tests.json", [])
    fails = []
    for t in tests:
        k = t["q"]
        if k == "recipe":
            r = q.recipe(t["film"], t["gases"])
            sp = {s for x in r for s, _ in x["species"]}
            ok_ = bool(r) and set(t["expect_species"]) <= sp and all(s in {k2 for x in r for k2 in x["emissions"]} for s in t.get("expect_with_emission", []))
        elif k == "peak":
            sp = {s for _, s, _ in q.peak(t["nm"], t.get("tol", 1.0))}
            ok_ = set(t["expect_species"]) <= sp
        elif k == "epd":
            sig = " ".join(u["signal"] for u in q.epd(t["film"]))
            ok_ = all(s in sig for s in t["expect_in_signal"])
        elif k == "actinometry":
            pair = " ".join(u["signal"] for u in q.actinometry(t["target"]))
            ok_ = all(s in pair for s in t["expect_in_pair"])
        elif k == "conditioning":
            walls, mons = q.conditioning(t["term"])
            blob = json.dumps([walls, [m["signal"] + " " + m["label"] for m in mons]], ensure_ascii=False)
            ok_ = bool(walls or mons) and all(s in blob for s in t["expect"])
        elif k == "sources":
            ok_ = any(t["expect_url_part"] in s.get("url", "") for s in q.sources(t["node"]))
        else:
            ok_ = False
        if not ok_:
            fails.append(t["id"] + " " + t.get("ask", ""))
    return errs, warns, fails, len(tests)


if __name__ == "__main__":
    g = build()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"
    errs, warns, fails, nt = check(g)
    if cmd == "stats":
        print(json.dumps(g["meta"], ensure_ascii=False))
        print("near(자동 계산) 관계", sum(1 for e in g["edges"] if e["rel"] == "near"))
        print("원소 보존 경고", len(warns))
        for w in warns[:40]:
            print("  ", w)
    print(f"스키마 오류 {len(errs)} · 시험 문항 {nt - len(fails)}/{nt} 통과")
    for x in errs[:20] + fails:
        print("  ", x)
    if cmd == "check":
        sys.exit(1 if errs or fails else 0)
