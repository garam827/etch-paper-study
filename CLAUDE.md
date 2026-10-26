# 반도체 식각 논문 스터디 — 작업 규칙

이 프로젝트는 작업 과정 자체를 기록·공유하는 용도로도 사용한다. 아래 규칙은 **모든 작업에 항상** 적용한다.

## 1. 작업 기록 (필수)

사용자의 지시가 들어올 때마다 기록에 항목을 하나 추가한다. 기록은 **프로젝트 단계별 페이지**로 나뉘어 있다.

### 구조

- `history.html` — 기록 첫 화면. "최근 항목" 3개와 단계 카드(단계명, 항목 범위·개수, 기간, 요약, 항목 목록)만 둔다. 항목 본문은 넣지 않는다.
- `history/phase-N.html` — N단계의 항목 본문. 위아래에 단계 이동(이전/다음, 단계 번호)이 있다.
- 현재 단계 (2026-10-26 기준):
  1. 기록·자문 체계 구축 (#1–#8)
  2. A20 식각 리서치 (#9–#12)
  3. 공유·배포·보안 (#13–#15)
  4. 학습 콘텐츠: 가이드·3D·질의응답 (#16–#20)
  5. 기록 체계 개선 (#21)
  6. 용어·개념 학습 (#22–#24)
  7. 패터닝 기술 리서치 (#25–#30)
  8. 플라즈마 식각 기초 문헌 학습 (#31–#38)
  9. 리서치 검증 체계 구축 (#39–)
  10. OES 식각 화학 데이터 병합 (#46–#47, #54–#55)
  11. 사이트 구조 재정비 (#48–#51)
  12. 패키징·본딩 리서치 (#52)
  13. 공정 제어(APC) 리서치 (#53)
  14. OES 지식 구조화 (#56–#58)
  15. 챔버 conditioning·aging OES (#59)
  16. RMG(대체 금속 게이트) 공정 리서치 (#60)
  17. 식각 공정 기초 보충 (#61–)
  - (비공개) SNU PAL 질의응답 지식화 (#40–#45) — 공개 단계 목록에 없음, `data/history_private/snupal_history.html`

### 새 항목 추가 방법

1. 항목 번호는 전체에서 이어지는 번호(#22, #23 …)를 쓴다.
2. 지금 하고 있는 단계의 `history/phase-N.html` 맨 아래(마지막 `</article>` 뒤)에 추가한다. 마크업은 기존 항목(`<article class="entry" id="eNN">`)을 그대로 복사한다.
3. 단계 페이지는 `history/` 폴더 안에 있으므로 경로 앞에 `../`를 붙인다: 이미지 `../history_img/…`, 링크 `../research/…`, `../viz/…`.
4. `history.html`의 "최근 항목"(최신 3개)과 해당 단계 카드(항목 범위·개수·기간·목록)를 함께 고친다.
5. **새 성격의 작업이 시작되면 새 단계**를 만든다: `phase-(N+1).html`을 만들고, 모든 단계 페이지의 단계 이동 줄과 `history.html` 단계 카드에 추가한다. 단계를 나눌지 애매하면 jev에게 묻는다.
6. 한 단계 페이지가 **10개 항목을 넘으면** 같은 단계의 다음 쪽(`phase-N-2.html`)으로 나눈다.

### 항목 내용

- **시간순**으로 정리한다 (오래된 항목이 위, 새 항목이 아래).
- 각 항목에는 다음을 **시간(YYYY-MM-DD HH:MM)과 함께** 기록한다.
  1. **지시 (원문)** — 사용자의 지시를 한 글자도 바꾸지 않고 그대로 옮긴다. (단, 민감정보는 예외적으로 마스킹)
  2. **분석 (Claude의 정리)** — 지시를 듣고 Claude가 이해·정리한 내용.
  3. **과정** — 실제로 수행한 작업 단계를 시간과 함께 나열. 실패·재시도도 사실대로 기록한다.
  4. **결과 / 증거** — 성공 여부, 그리고 증거 스크린샷.
- 디자인은 **밝은 톤**을 유지한다.
- 사용자가 "(history 기록 x)"처럼 기록하지 말라고 한 지시는 기록하지 않는다.
- **SNU PAL 질의응답 데이터셋 관련 작업은 공개 기록(history.html·history/·history_img/)에 싣지 않는다** (2026-10-11 사용자 지시). 같은 형식으로 `data/history_private/snupal_history.html`(스크린샷은 `data/history_private/history_img/`)에 기록한다. 공개 단계 이동 줄·첫 화면에도 넣지 않는다.
- 작업이 끝날 때 기록을 갱신하는 것을 잊지 않는다. 기록 없이 작업을 마치지 않는다.

## 2. 증거 스크린샷 (history_img/)

- 성공한 결과의 증거는 스크린샷으로 남기고 `history_img/` 폴더에 저장한다.
- 파일명에는 날짜와 시간을 넣는다: `YYYYMMDD_HHMMSS_<짧은설명>.png`
  - 예: `20261005_183000_history_setup.png`
- 단계 페이지에서 `<img loading="lazy" decoding="async" src="../history_img/파일명.png">`로 넣어 이미지가 바로 보이게 한다(지연 로딩: 한 단계 페이지에 이미지가 수 MB라서).
- 스크린샷을 저장하기 전에 화면에 민감정보가 보이지 않는지 확인한다.

## 3. 민감정보 금지 (절대 규칙)

history.html·history/ 단계 페이지, history_img의 스크린샷, 기타 공유용 기록에 다음이 **절대** 들어가면 안 된다.

- IP 주소 (내부/외부 모두), 호스트명·포트가 포함된 접속 주소
- API 키, 토큰, 비밀번호, 세션/쿠키 값, 개인키, 인증서
- 이메일 주소·계정 ID 등 개인 식별 정보

지시 원문이나 명령 출력에 이런 값이 있으면 `[REDACTED-IP]`, `[REDACTED-TOKEN]`처럼 마스킹하고, 마스킹했다는 사실을 기록한다. 기록 후에는 history.html과 history/ 단계 페이지를 IP/토큰 패턴으로 검사한다.

## 4. 판단 및 리서치 규칙 (astra · jev · sol)

모든 일은 자문을 받으면서 진행하고, 자문 내용과 반영 여부를 기록(현재 단계 페이지)의 "과정"에 기록한다.

1. **리서치가 필요할 때** → `gpt-6-astra` (reasoning effort **high**)를 **비동기(백그라운드)**로 호출한다. (원래 지정은 `gpt-6.1-sol` high였으나 계정에서 지원되지 않아 사용자 지시로 대체, 2026-10-05) 결과를 기다리는 동안 다른 작업을 진행한다.
2. **판단이 필요할 때** → **jev**에게 묻고 의견을 구한다.
3. **아주 중요한 판단** → `gpt-6-astra` (reasoning effort **xhigh**)를 호출해 자문을 받는다.

호출 명령, 모델 지원 상태, jev API 사용법은 `docs/runbook.md` §1에 있다. 자문 프롬프트에 IP·토큰·계정정보를 넣지 않고, Codex 출력의 session id 같은 식별자는 기록에 옮기지 않는다.

### 리서치 검증 체계 (2026-10-09, #39)

새 사실을 보고서·용어집·그래프에 넣거나 기존 내용을 검증할 때는 `semi-research` 스킬 절차를 따른다 (`.claude/skills/semi-research/` — SKILL.md, policy.md 출처 등급·함정 체크리스트, schema.md 장부 형식).

- 주장 장부 `ledger/<주제>.json` (비공개). `python tools/claims.py lint|blind|record|gate|summary`.
- 채택은 `claims.py gate`만 결정한다. 작성자(Claude)가 자기 주장을 채택으로 올리지 않는다. 주장을 고치면 이전 검증은 자동 무효. 공개 페이지에 주장별 상태를 보이려면 `python tools/claims_export.py ledger/<주제>.json` → `kb/claims/` → build (검증 현황 페이지 `research/claims_status.html`).
- 검증은 `claim-verifier` 에이전트(웹 도구만, 로컬 파일 접근 없음)에 `claims.py blind` 출력만 넘긴다. 에이전트가 세션에 아직 안 올라왔으면 별도 실행으로 같은 격리를 건다:
  (명령은 `docs/runbook.md` §2)
- 수집은 `paper-scout` 에이전트(중립 질문만) + `python tools/lit_search.py`. 출처 실재는 `python tools/check_refs.py` (DOI가 있다고 내용이 맞는 것은 아님).
- jev는 범위·우선순위 같은 이산 판단에 쓰고, **증거 충돌의 종결에는 쓰지 않는다** (충돌은 보류로 두고 조건·정의·시점 차이를 조사).
- 체계를 고치면 `tools/tests/regression_ledger.json`(지난 실제 오류 6개 + 정상 2개)로 다시 확인한다.

### 외부 자료 수집 (2026-10-09, #40)

- 수집 전 robots.txt·이용 조건 확인, 요청 사이 1초 이상 쉰다.
- 원문 전체·작성자 이름은 `data/`(비공개, .gitignore)에만 둔다. 공개 결과물에는 **재서술한 지식·용어 + 원문 링크**만 싣고, 원문을 15단어 넘게 옮기지 않는다.
- SNU PAL 게시판(도구는 `docs/runbook.md` §3): 공개 페이지는 주제별 해설(`kb/snupal/topics.json`)과 용어 사전만 싣는다(글별 요약·목록 금지, 2026-10-13 결정).
- 본문 속 그림·첨부(옛 주소 pal.snu.ac.kr)는 원래 사이트에서도 이미 볼 수 없고 인터넷 아카이브에도 없다(2026-10-11 확인, `media` 표에 상태 기록). 텍스트 보관본(`data/snupal/`)이 유일한 사본이다.
- 백업(2026-10-11): `data/backup/snupal_archive_YYYYMMDD*.zip`(README·JSONL·SHA-256 포함, 10MB 미만 조각) → 사용자 구글 드라이브 `snupal_archive` 폴더(비공유). 보관본이 바뀌면 새 날짜로 다시 만들어 올린다.

## 5. 공유 사이트 (GitHub Pages)

- 공유는 GitHub Pages로 한다. 저장소: `etch-paper-study` (공개), main 브랜치 루트가 그대로 사이트가 된다.
- 첫 화면 `index.html`(목차·학습 경로·검색)은 **생성 파일**이다. 새 결과물은 `kb/pages.json`에 항목(영역·태그·날짜)을 추가하고, 필요하면 학습 경로에도 넣은 뒤 build 한다. 결과물 페이지에는 `← 목차` 링크를 넣는다.
- 작업이 끝나면 기록(현재 단계 페이지 + history.html 첫 화면) 갱신 → 커밋 → `git push`로 사이트를 업데이트한다. 푸시 전 `python tools/build_site.py --check`와 `python tools/check_links.py`가 통과해야 하고(GitHub Actions `site-check`도 같은 검사), 푸시 후 Pages 빌드 완료와 실제 페이지(200)를 확인한다.
- 절대 커밋 금지: `.env`(API 키). `.gitignore`로 막혀 있지만, 커밋 전에 올라갈 파일에 키·IP·계정정보가 없는지 매번 검사한다.
- **원본과 결과물 (2026-10-13)**: 목차·지식 그래프·질의응답·검증 현황·논문 요약 페이지는 `kb/`가 원본이다. 결과물 HTML을 직접 고치지 말고 `kb/`(또는 `tools/templates/`)를 고친 뒤 `python tools/build_site.py`로 만든다. 커밋 전 `python tools/build_site.py --check`가 통과해야 한다.
  - 파일 구성은 `docs/runbook.md` §4. 노드 id는 "한 개념 = 한 id"로 쓰고 바꾸지 않는다(링크 `#앵커`가 걸려 있음).
  - 구조 이관과 내용 수정은 따로 커밋한다.
- **레퍼런스 논문 요약 (2026-10-13, #51)**: 결과물에 논문을 새로 인용하면 `kb/papers/papers.json`에 요약(재서술, 근거 범위 표시)을 추가하고, 핵심 문장을 `ledger/papers_summary.json`으로 검증(gate) → `claims_export.py` → build 한다. 손으로 쓰는 페이지는 `python tools/paper_links.py apply <페이지>`로 "요약" 링크를 붙인다(그래프·OES는 생성 도구가 자동). 푸시 전 `python tools/paper_links.py check`(CI에도 있음).
- **OES 데이터·지식 그래프 (2026-10-15, #57)**: OES 페이지와 OES 지식 그래프(`research/oes_knowledge_graph.html`, `research/oes_kg/{graph.json,cards.jsonl}`)도 build가 만든다. 원본은 `kb/oes/`(앱 데이터 공개 사본 `app/`·검증 `verify/`·보완 조합 `combos_extra.json`·보완 밴드 `bands_extra.json`·챔버 conditioning·시즈닝·aging(벽 상태·단계·재결합·감시 신호, 장부 `ledger/oes_conditioning.json`) `conditioning.json`·시험 문항 `graph_tests.json`)와 `tools/oes_supplement.json`. 앱 데이터는 보안 검토(메일·IP·경로·키·내부 주소 없음, 빈 공정 조건 제외) 뒤 공개 사본으로 넣었고, 원래 앱 데이터는 고치지 않는다. 앱 데이터가 바뀌면 같은 검토를 거쳐 사본을 갱신한다. 푸시 전 `python tools/oes_graph.py check`(스키마·원소 보존·링크 형식·시험 문항, CI에도 있음). 근거 검색은 정적 사이트라 언어 모델 생성 없이 검색 단계까지만 둔다(API 키를 클라이언트에 두지 않는다). 원래 앱 저장소의 복사본(`merge_src/`)은 커밋하지 않는다(.env 등 비밀 포함).
- **OES 지식 그래프 DB·사내 미러 (2026-10-16)**: build가 `research/oes_kg/manifest.json`(버전=내용 해시, 파일 SHA-256·크기·개수, 대표 질의)을 함께 만든다. 생성 파일은 LF로 쓴다(해시가 로컬·저장소·Pages에서 같아야 함). 사내 서버는 `mirror/oes_kg_mirror.py`(표준 라이브러리만)로 단방향 동기화한다: SQLite 파일 또는 PostgreSQL(`pg-sql` → psql, 스테이징 적재·검사 뒤 스키마 교체, `oes_kg_prev` 1개 보관). 오프라인은 `bundle`. 사내 고유 데이터는 `oes_local`에만 두고 공개 저장소로 되돌리지 않는다. 사용법은 `mirror/README.md`. CI `mirror` 작업이 SQLite·PostgreSQL 적재를 시험한다. 스키마를 바꾸면 `SCHEMA_VERSION`과 manifest의 `schema_version`을 함께 올린다.
- 원본 리서치(`research/*_raw.md`)와 실행 로그(`research/*_log.txt`)는 공개하지 않는다 (로컬 보관).
- 사이트 주소에는 GitHub 계정명이 들어가므로, history에는 `<계정>.github.io/etch-paper-study/`처럼 가려서 적는다.

### 개인 메일 주소 보호 (필수)

- 이 저장소의 커밋 메일은 **GitHub no-reply 주소**(`<id>+<계정>@users.noreply.github.com`)만 쓴다. 저장소 로컬 설정(`git config --local user.email`)에 지정되어 있다.
- 커밋 전에 `git config user.email`이 no-reply 주소인지 확인한다. 개인 메일(Gmail 등)이 커밋 작성자·커미터로 들어가면 안 된다.
- 푸시 전에 `git log --format='%ae %ce'`로 개인 메일이 없는지 확인한다.
- history.html, CLAUDE.md, 산출물, 스크린샷, 명령 출력 기록 어디에도 개인 메일 주소를 적지 않는다. 언급이 필요하면 `abc***@example.com`처럼 가려서 쓴다 (실제 주소의 일부도 쓰지 않는다).
- 이미 올라간 기록을 고치는 강제 푸시는 반드시 사용자 승인을 받은 뒤 진행한다.
