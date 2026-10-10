# 주장 장부 스키마 (v1)

파일: `ledger/<주제>.json` — `{"schema_version": "1", "topic": "...", "claims": [...], "sources": [...]}`
예시 전체: `tools/tests/regression_ledger.json`

## claims[]

| 필드 | 필수 | 설명 |
|---|---|---|
| claim_id | ✓ | 장부 안에서 유일 (C001…) |
| revision | | 고칠 때마다 +1 (해시는 도구가 계산) |
| author_run | ✓ | 작성 실행 ID. 검증자의 verifier_run과 달라야 검증이 유효 |
| statement | ✓ | 조건을 포함한 **한 문장 한 사실** |
| risk | ✓ | low / medium / high (결론을 좌우하면 high) |
| as_of | ✓ | 기준일 YYYY-MM-DD |
| scope | | device, node_label(이름일 뿐), conditions{}, assumptions[] |
| quantity | | metric, raw(원문 표기), value, unit, baseline, uncertainty, derivation |
| event | | type(announcement/sample/risk_production/volume_production/shipment/paper_presented/analysis_published…), date, precision(year/month/day), planned_or_actual |
| evidence[] | ✓ | 아래 |
| decision | | **gate만 기록** — 작성자가 adopt를 쓰면 lint 오류 |

## evidence[]

| 필드 | 설명 |
|---|---|
| source_id | sources[]의 id |
| doi / url | 둘 중 하나 이상 |
| tier | T1–T5 (policy.md) |
| document_type | journal_paper, conference_paper, textbook, thesis, press_release, company_presentation, analyst_report, news, patent, forum |
| evidence_kind | experiment, theory, simulation, review, company_claim, direct_analysis, estimate |
| origin_group | 같은 원근거면 같은 값 (보도자료 재인용 묶기) |
| access_level | full_text / abstract_only / metadata_only / secondary(재인용·요약만) |
| locator | 원문 위치 (쪽·절·그림·표·문단) — full_text면 필요 |
| relation | supports / partially_supports / refutes / unrelated / unassessed |
| published_at, accessed_at | 날짜 분리 |

## 검증 보고 (claim-verifier 출력 → `claims.py record`)

```json
{"verifier_run": "V-20261009-1", "verdicts": [
  {"claim_id": "C001", "content_hash": "<blind 입력의 값 그대로>", "verdict": "supported|partially_supported|refuted|conflicting|insufficient",
   "verifier_run": "V-20261009-1", "evidence_checked": [{"url": "...", "access_level": "full_text", "locator": "...", "relation": "supports"}],
   "independent_origins": ["<검증자가 확인한 독립 계보>"], "required_conditions": "부분 지지일 때 문장에 넣어야 할 조건", "reason": "한두 문장"}]}
```

`ledger/<주제>.verify.jsonl`에 추가만 된다. content_hash가 현재 주장과 다르면 기록이 거부된다.
