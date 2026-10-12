# 작업 절차서 (runbook)

규칙은 `CLAUDE.md`, 명령과 사용법은 여기에 둔다. (2026-10-13 분리)

## 1. 자문 호출 (astra · jev)

### 호출 방법 (Codex CLI)

```bash
# 아주 중요한 판단: astra (동작 확인됨)
codex exec --skip-git-repo-check -s read-only -m gpt-6-astra -c model_reasoning_effort='"xhigh"' "<질문>" </dev/null

# 리서치: astra high (Bash run_in_background=true 로 비동기 실행, 웹 검색 사용)
codex exec --skip-git-repo-check -s read-only -m gpt-6-astra -c model_reasoning_effort='"high"' -c tools.web_search=true "<리서치 요청>" </dev/null
```

- 자문 프롬프트에 IP·토큰·계정정보 등 민감정보를 넣지 않는다.
- Codex 출력의 session id 등 식별자는 history에 옮기지 않는다.
- `</dev/null`을 꼭 붙인다 (없으면 Codex가 입력을 기다리며 멈춤).

### 현재 상태 (2026-10-05 기준)

- `gpt-6-astra` xhigh(중요 판단) / high(리서치): 호출 성공 확인.
- `gpt-6.1-sol` high: **현재 ChatGPT 계정으로는 Codex에서 지원되지 않음** ("not supported when using Codex with a ChatGPT account"). → 리서치는 `gpt-6-astra` high로 대체.
- **jev**: TypeSafe의 판단 전용 API (모델 `jev-latest`). 호출 성공 확인 (2026-10-05). 도우미: `python tools/ask_jev.py <질문.json>` — 질문 JSON은 scratchpad에 만들고, 키는 `.env`에서 자동으로 읽는다.

### jev 사용법 (TypeSafe API)

- 엔드포인트: `POST https://api.typesafe.ai/v1/systemone`
- 인증: `Authorization: Bearer $TYPESAFE_API_KEY` (키는 `.env`에만 두고, 출력·기록 금지)
- 요청: `{"model": "jev-latest", "state": "<상황 설명>", "questions": {<질문id>: {...}}}`
- 질문 유형:
  - `noul` — 예/아니오 확률(0~1): `{"type": "noul", "instructions": "..."}`
  - `choice` — 선택지 중 고르기: `{"type": "choice", "instructions": "...", "criteria": {"a": "설명", "b": "설명"}}`
  - `score` — 순서 있는 척도: `{"type": "score", "instructions": "...", "criteria": ["매우 나쁨", ..., "매우 좋음"]}`
- 응답: 판단값, 신뢰도, 선택지별 확률, 토큰 사용량.
- 판단을 구할 땐 질문과 jev의 답(판단값·신뢰도)을 기록의 "과정"에 남긴다.
- 참고: https://grow-up-by-coding.tistory.com/entry/Jev-API-%EC%A7%81%EC%A0%91-%EC%82%AC%EC%9A%A9%ED%95%B4%EB%B3%B4%EA%B8%B0-%EA%B0%80%EA%B2%A9

## 2. 리서치 검증 (semi-research)

```bash
python tools/claims.py lint ledger/<주제>.json
python tools/check_refs.py ledger/<주제>.json        # 출처 실재 (내용 검증 아님)
python tools/claims.py blind ledger/<주제>.json > blind.json   # 검증 에이전트에 이것만 넘긴다
python tools/claims.py record ledger/<주제>.json <판정.json>
python tools/claims.py gate ledger/<주제>.json
python tools/claims_export.py ledger/<주제>.json     # 공개용 상태 → kb/claims/
```

검증 에이전트가 세션에 없으면 같은 격리로 별도 실행:

```bash
claude -p --agent claim-verifier --allowedTools WebSearch WebFetch --disallowedTools Bash Read Write Edit Glob Grep NotebookEdit Agent PowerShell --output-format json < 입력.txt
```

## 3. SNU PAL 게시판 도구

```bash
python tools/snupal_crawl.py list|docs|media|stats      # → data/snupal/snupal.db (비공개)
python tools/snupal_merge.py export <export.json>        # 비공개 export
python tools/snupal_page.py prepare <export.json>        # → kb/snupal/page.json (페이지에 싣는 것만)
```

## 4. 사이트 생성 (kb/ → 결과물)

```bash
python tools/build_site.py           # 생성
python tools/build_site.py --check   # 커밋된 결과물이 원본과 같은지
python tools/check_links.py          # 내부 링크·앵커
```

| 원본 | 결과물 |
|---|---|
| `kb/pages.json`(영역·학습 경로·자료 목록) + `tools/templates/index.html` | `index.html` (검색 항목에 그래프 용어 포함) |
| `kb/graph/nodes.json`(id·이름·영문·분류·영역·설명·식각 관계·출처 키), `edges.json`(관계·근거 글), `sources.json`(출처 키 → 제목·URL), `types.json`(분류·영역 이름) + `tools/templates/a20_etch_knowledge_graph.html` | `research/a20_etch_knowledge_graph.html` |
| `kb/snupal/page.json`, `topics.json` | `research/snupal_qna_knowledge.html` |
| `kb/claims/*.json` | `research/claims_status.html` |

## 5. OES 페이지 (외부 데이터 필요)

```bash
python tools/oes_page.py <oes_assistant 폴더> <파장검증.json> [조합검증.json]   # → research/oes_etch_chemistry.html
python tools/oes_supplement_build.py <NIST 추출.json> ledger/oes_supplement.json <검증메모.json>  # → tools/oes_supplement.json
```

## 6. 이력 정리 (강제 푸시)

사용자 승인 후에만. 먼저 `git bundle create data/backup/repo_before_<날짜>.bundle --all`로 백업하고, 시험 복제본에서 `git filter-repo`를 먼저 돌려 본다. filter-repo는 `origin` 원격을 지우므로 다시 연결한다. GitHub는 예전 커밋을 해시로 한동안 보여 줄 수 있다(완전 삭제는 GitHub 지원 요청).
