"""비공개 주장 장부 → 공개용 검증 현황 (kb/claims/<이름>.json)

    python tools/claims_export.py ledger/retro_core.json

장부(ledger/)는 비공개라 그대로 올리지 않는다. 공개용에는 주장 문장, gate 결정과 이유, 검증 판정·필요 조건·메모,
검증자가 확인한 출처 URL, 검토일만 옮긴다. 그 뒤 python tools/build_site.py 로 research/claims_status.html 을 만든다.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
led = Path(sys.argv[1])
L = json.loads(led.read_text(encoding="utf-8"))
gate = {g["claim_id"]: g for g in json.loads(subprocess.run(
    [sys.executable, str(ROOT / "tools/claims.py"), "gate", str(led)], capture_output=True, text=True, encoding="utf-8").stdout)}
last = {}
for line in led.with_suffix(".verify.jsonl").read_text(encoding="utf-8").splitlines():
    v = json.loads(line)
    last[v["claim_id"]] = v  # 같은 주장에 여러 판정이 있으면 마지막 것

rows = []
for c in L["claims"]:
    g, v = gate[c["claim_id"]], last.get(c["claim_id"], {})
    run = v.get("verifier_run", "")
    reviewed = f"{run[2:6]}-{run[6:8]}-{run[8:10]}" if run.startswith("V-") else c["as_of"]
    rows.append({"id": c["claim_id"], "page": c.get("page"), "statement": c["statement"], "risk": c["risk"],
                 "decision": g["decision"], "reason": g["reason"], "verdict": v.get("verdict"),
                 "conditions": v.get("required_conditions", ""), "note": v.get("notes", ""), "reviewed": reviewed,
                 "checked": [e["url"] for e in v.get("evidence_checked", []) if e.get("relation") in ("supports", "partially_supports")]})
out = ROOT / "kb" / "claims" / (led.stem + ".json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({"topic": L["topic"], "claims": rows}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(out.relative_to(ROOT), len(rows))
