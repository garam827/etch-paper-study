"""OES 보완 데이터 묶기: NIST 표에서 뽑은 원자선 + 주장 장부(gate 결과) → tools/oes_supplement.json

    python tools/oes_supplement_build.py <atomic_supp.json> ledger/oes_supplement.json <판정메모.json>

- atomic_supp.json: NIST 원소별 강한 선 표(Air)에서 200–900 nm, 상대 세기 상위 4개(1 nm 안 중복 제외)를 기계적으로 뽑은 결과.
- 장부의 주장은 gate 결과가 adopt/conditional인 것만 싣는다(hold/reject는 제외). 판정메모는 {claim_id: 검증자 메모}.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
atomic = json.load(open(sys.argv[1], encoding="utf-8"))
L = json.load(open(sys.argv[2], encoding="utf-8"))
notes = json.load(open(sys.argv[3], encoding="utf-8")) if len(sys.argv) > 3 else {}
gate = json.loads(subprocess.run([sys.executable, str(ROOT / "tools/claims.py"), "gate", sys.argv[2]],
                                 capture_output=True, text=True, encoding="utf-8").stdout)
dec = {g["claim_id"]: g["decision"] for g in gate}

TITLE = {
    "kwon2021": "Kwon et al., Materials 14, 3005 (2021)", "biehl1997": "Biehl et al., J. Chem. Phys. 107, 720 (1997)",
    "biehl1998": "Biehl et al., J. Electron Spectrosc. 97, 89 (1998)", "bruno1986": "Bruno et al., Plasma Chem. Plasma Process. 6, 109 (1986)",
    "verity": "Verity Instruments, Applications Information (장비사)", "amat6455437": "Applied Materials 특허 US6455437B1",
    "alrebdi2022": "Alrebdi et al., Polymers 14, 3686 (2022)", "shin2013": "Shin et al., JVST A 31, 031305 (2013)",
    "cruden2017": "Cruden & Brandis, NASA (2017)", "qian2016": "Qian et al., Chinese Phys. B 25, 105205 (2016)",
    "moravek2014": "Morávek et al., Phys. Scr. T161, 014056 (2014)", "gerard2019": "Gérard et al., JGR Space Phys. 124 (2019)",
    "donnelly2013": "Donnelly & Kornblit, JVST A 31, 050825 (2013)", "kim2001": "Kim et al., Mater. Sci. Eng. B 82, 159 (2001)",
    "kudrya2019": "Kudrya et al., Russ. Microelectron. 48, 37 (2019)", "ep0442488": "Applied Materials 특허 EP0442488A2",
    "layadi1999": "Layadi et al., JVST B 17, 2630 (1999)", "rudenko2007": "Rudenko et al., Russ. Microelectron. 36, 179 (2007)",
    "hpj1982": "Marcoux, Hewlett-Packard Journal 33(8) (1982)", "pie": "PIE Scientific, Photoresist Ashing (장비사)",
    "park2021": "Park et al., Materials 14, 1144 (2021)", "us5552016": "Applied Materials 특허 US5552016A",
    "us10892146": "Tokyo Electron 특허 US10892146B2", "hebner2002": "Hebner et al., Sandia SAND2002-0340 (2002)",
    "britun2024": "Britun et al., J. Appl. Phys. 136, 111101 (2024)", "hanish1999": "Hanish et al., IEEE Trans. Semicond. Manuf. (1999)",
    "nishio2022": "Nishio et al., Plasma Fusion Res. 17, 1201004 (2022)",
    "us6376262": "특허 US6376262B1 (이중 종말점 검출)", "us6242350": "TSMC 특허 US6242350B1", "us6472329": "특허 US6472329B1 (Al 식각)",
    "us4491499": "AT&T 특허 US4491499A", "us4493745": "IBM 특허 US4493745A", "us7067432": "Applied Materials 특허 US7067432B2",
    "greb2014": "Greb et al., Appl. Phys. Lett. 105, 234105 (2014)", "tsutsumi2017": "Tsutsumi et al., J. Appl. Phys. 121, 143301 (2017)",
    "kristof2016": "Krištof et al., Phys. Scr. 91, 074009 (2016)", "kuzmenko2021": "Kuzmenko & Myakon'kikh, Tech. Phys. Lett. (2021)",
}
out = {"atomic": atomic, "mol": [], "epd": [], "act": [], "ovl": [], "excluded": []}
for c in L["claims"]:
    d = dec.get(c["claim_id"], "hold")
    row = {"id": c["claim_id"], "decision": d, **c["data"], "statement": c["statement"],
           "cond": "; ".join(f"{k}: {v}" for k, v in c["scope"]["conditions"].items()),
           "src": [[TITLE.get(e["source_id"], e["source_id"]), e["url"]] for e in c["evidence"]],
           "note": notes.get(c["claim_id"], "")}
    (out[c["cat"]] if d in ("adopt", "conditional") else out["excluded"]).append(row)
json.dump(out, open(ROOT / "tools/oes_supplement.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print({k: len(v) for k, v in out.items()})
