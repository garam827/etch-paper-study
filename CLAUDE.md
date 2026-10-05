# 반도체 식각 논문 스터디 — 작업 규칙

이 프로젝트는 작업 과정 자체를 기록·공유하는 용도로도 사용한다. 아래 규칙은 **모든 작업에 항상** 적용한다.

## 1. history.html 기록 (필수)

사용자의 지시가 들어올 때마다 프로젝트 루트의 `history.html`에 항목을 하나 추가한다.

- **시간순**으로 정리한다 (오래된 항목이 위, 새 항목이 아래).
- 각 항목에는 다음을 **시간(YYYY-MM-DD HH:MM)과 함께** 기록한다.
  1. **지시 (원문)** — 사용자의 지시를 한 글자도 바꾸지 않고 그대로 옮긴다. (단, 4번 민감정보는 예외적으로 마스킹)
  2. **분석 (Claude의 정리)** — 지시를 듣고 Claude가 이해·정리한 내용.
  3. **과정** — 실제로 수행한 작업 단계를 시간과 함께 나열. 실패·재시도도 사실대로 기록한다.
  4. **결과 / 증거** — 성공 여부, 그리고 증거 스크린샷.
- 디자인은 **밝은 톤**을 유지한다. 기존 항목의 마크업 구조(`<article class="entry">`)를 그대로 복사해서 새 항목을 추가한다.
- 작업이 끝날 때 history.html을 갱신하는 것을 잊지 않는다. 기록 없이 작업을 마치지 않는다.

## 2. 증거 스크린샷 (history_img/)

- 성공한 결과의 증거는 스크린샷으로 남기고 `history_img/` 폴더에 저장한다.
- 파일명에는 날짜와 시간을 넣는다: `YYYYMMDD_HHMMSS_<짧은설명>.png`
  - 예: `20261005_183000_history_setup.png`
- history.html에서 상대경로(`history_img/파일명.png`)로 `<img>`를 넣어 이미지가 바로 보이게 한다.
- 스크린샷을 저장하기 전에 화면에 민감정보가 보이지 않는지 확인한다.

## 3. 민감정보 금지 (절대 규칙)

history.html, history_img의 스크린샷, 기타 공유용 기록에 다음이 **절대** 들어가면 안 된다.

- IP 주소 (내부/외부 모두), 호스트명·포트가 포함된 접속 주소
- API 키, 토큰, 비밀번호, 세션/쿠키 값, 개인키, 인증서
- 이메일 주소·계정 ID 등 개인 식별 정보

지시 원문이나 명령 출력에 이런 값이 있으면 `[REDACTED-IP]`, `[REDACTED-TOKEN]`처럼 마스킹하고, 마스킹했다는 사실을 기록한다. 기록 후에는 history.html을 IP/토큰 패턴으로 검사한다.

## 4. 판단 및 리서치 규칙 (astra · jev · sol)

모든 일은 자문을 받으면서 진행하고, 자문 내용과 반영 여부를 history.html의 "과정"에 기록한다.

1. **리서치가 필요할 때** → `gpt-6-astra` (reasoning effort **high**)를 **비동기(백그라운드)**로 호출한다. (원래 지정은 `gpt-6.1-sol` high였으나 계정에서 지원되지 않아 사용자 지시로 대체, 2026-10-05) 결과를 기다리는 동안 다른 작업을 진행한다.
2. **판단이 필요할 때** → **jev**에게 묻고 의견을 구한다.
3. **아주 중요한 판단** → `gpt-6-astra` (reasoning effort **xhigh**)를 호출해 자문을 받는다.

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
- 판단을 구할 땐 질문과 jev의 답(판단값·신뢰도)을 history.html "과정"에 기록한다.
- 참고: https://grow-up-by-coding.tistory.com/entry/Jev-API-%EC%A7%81%EC%A0%91-%EC%82%AC%EC%9A%A9%ED%95%B4%EB%B3%B4%EA%B8%B0-%EA%B0%80%EA%B2%A9
