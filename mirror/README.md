# OES 지식 그래프·RAG DB와 사내 미러링

공개 OES 지식 그래프(`research/oes_kg/graph.json`)와 RAG 카드(`cards.jsonl`)를 DB에 적재하고, 기업 내 서버에 같은 DB를 **단방향으로** 복제(미러링)하는 방법입니다.

## 1. 구조

```
[공개 원본: kb/oes/ ─build→ research/oes_kg/{graph.json, cards.jsonl, manifest.json}]  ← GitHub Pages
                                         │  (HTTPS로 받기, 또는 반입 폴더로 옮기기)
                                         ▼
[사내 서버: oes_kg_mirror.py sync] → 무결성 검증(SHA-256·크기·개수) → 스테이징 적재 → 검사 → 원자적 교체
                                         ▼
             SQLite 파일 (oes_kg.sqlite)  또는  PostgreSQL 스키마 oes_kg
             사내 고유 데이터: oes_local 스키마 / local_* 테이블 (동기화가 덮어쓰지 않음)
```

- **방향**: 공개 원본에서 사내로만 흐릅니다. 사내 DB에서 밖으로 나가는 연결과 데이터는 없습니다.
- **원본**: 원본은 하나뿐이고, 사내 DB는 읽기 전용 사본입니다. 내용을 고치려면 원본(`kb/oes/`)을 고친 뒤 build해서 다시 배포합니다.
- **버전 관리**: `manifest.json`의 `version`(내용 해시)이 바뀔 때만 적재합니다. 같은 버전이면 아무것도 하지 않습니다.

## 2. DB 스키마 (schema_version 1)

| 테이블 | 내용 | 주요 열 |
|---|---|---|
| `meta` | 적재 버전, 시각, manifest | key, value |
| `node` | 노드: 조합·막질·가스·화학종·방출·용도·주장·출처·벽 상태·단계 | id, type, label, decision, props(JSON) |
| `edge` | 관계(etches, feeds, may_produce, emits, cites, supports, forms, removes, affects …) | s, t, rel, props(JSON) |
| `emission_point` | 방출 파장의 점 값(수치 질의용) | node_id, species, nm |
| `emission_range` | 방출 밴드의 구간 | node_id, species, lo, hi |
| `card` | RAG 카드: 노드당 1장, 근거·판정·인용 포함 | id, type, title, text, decision, citations, neighbors |
| `card_fts` / `card.tsv` | 전문 검색(SQLite FTS5 / PostgreSQL tsvector + GIN) | |
| `card_embedding` | (선택) 사내 승인 임베딩 모델로 계산한 벡터 | id, model, dim, vec |

- **파장 질의**: 임베딩을 쓰지 않고 `emission_point.nm`에 대한 숫자 비교로 결정적으로 풉니다.
- **임베딩**: 공개 원본에는 넣지 않습니다. 필요하면 사내에서 승인된 모델로 계산해 `card_embedding`에 저장합니다. PostgreSQL이면 pgvector의 `vector(dim)` 열을 써도 됩니다.
- **판정 사용 규칙**: `decision`이 `adopt`(채택)·`conditional`(조건부)인 근거만 답변에 쓰고, 보류·제외 판정은 원본 단계에서 이미 빠져 있습니다.

## 3. 설치·동기화

필요한 것은 Python 3.9 이상(표준 라이브러리만 사용)과 SQLite(내장)입니다. PostgreSQL을 쓰려면 `psql`이 있어야 합니다.

### A. 인터넷(사내 프록시) 되는 서버
```bash
export HTTPS_PROXY=http://<사내 프록시>    # 필요할 때만
python oes_kg_mirror.py sync --source https://<계정>.github.io/etch-paper-study/research/oes_kg/ --sqlite /srv/oes/oes_kg.sqlite
```

### B. 망 분리 서버(오프라인 반입)
```bash
# 인터넷 되는 PC에서: 받으면서 검증한 묶음 만들기
python oes_kg_mirror.py bundle --source https://<계정>.github.io/etch-paper-study/research/oes_kg/ --out ./oes_kg_bundle/
# 반입 절차로 폴더를 옮긴 뒤 사내 서버에서
python oes_kg_mirror.py sync --source /mnt/import/oes_kg_bundle/ --sqlite /srv/oes/oes_kg.sqlite
```
묶음에는 `manifest.json`, `graph.json`, `cards.jsonl`, 스크립트 자신이 들어 있습니다. 사내에서도 같은 SHA-256 검증을 다시 거칩니다.

### C. PostgreSQL
```bash
python oes_kg_mirror.py pg-sql --source <A 또는 B의 원본> --out load_oes_kg.sql
psql "$PGURL" -v ON_ERROR_STOP=1 -f load_oes_kg.sql
```
- **적재 순서**: 한 트랜잭션 안에서 `oes_kg_staging`에 적재합니다. 이어서 개수와 대표 질의를 검사한 뒤, 기존 `oes_kg`를 `oes_kg_prev`로 옮기고 `oes_kg_staging`을 `oes_kg`로 바꿉니다.
- **실패 시**: 검사가 실패하면 전체가 취소되어 기존 DB가 그대로 남습니다.
- **권한**: 읽기 사용자에게는 `oes_kg`에 대한 `USAGE`와 `SELECT` 권한만 주고, 적재는 별도 계정으로 합니다.
- **권한 재부여**: 스키마가 교체되므로, 교체 뒤 같은 트랜잭션 끝에 GRANT를 다시 실행하는 후처리를 붙이세요.

### 주기 실행
- Linux cron 예: `0 3 * * * python /opt/oes/oes_kg_mirror.py sync --source ... --sqlite /srv/oes/oes_kg.sqlite >> /var/log/oes_kg_mirror.log 2>&1`
- Windows 작업 스케줄러: 같은 명령을 매일 실행합니다.
- 종료 코드가 0이 아니면(무결성·검사 실패) 알림을 보내도록 감시에 연결합니다.

## 4. 검증·롤백
- **매번 하는 검사**: 파일 SHA-256과 크기, 노드·관계·카드 개수, 끊긴 관계 여부, 대표 질의 3개(CO 483.1, Ar 750.4, SiCl 282.0 nm)를 확인합니다.
- **SQLite 롤백**: 이전 파일 3개를 `versions/`에 보관합니다. 되돌리려면 원하는 파일을 `oes_kg.sqlite`로 복사합니다.
- **PostgreSQL 롤백**: 이전 스키마를 `oes_kg_prev`로 1개 보관합니다. 되돌리려면 `ALTER SCHEMA oes_kg RENAME TO oes_kg_bad; ALTER SCHEMA oes_kg_prev RENAME TO oes_kg;`를 실행합니다.
- **상태 확인**: `python oes_kg_mirror.py status --sqlite /srv/oes/oes_kg.sqlite`

## 5. 질의 예시

```bash
python oes_kg_mirror.py query --sqlite oes_kg.sqlite peak 519.8 --tol 0.5     # 관측 피크 → 후보 화학종·근거
python oes_kg_mirror.py query --sqlite oes_kg.sqlite search "SiOClx 세정 SF6"   # RAG 검색 단계(전문 검색 순위)
```

PostgreSQL SQL 예:
```sql
-- 피크 → 후보
SELECT p.species, p.nm, n.label, n.decision FROM oes_kg.emission_point p JOIN oes_kg.node n ON n.id = p.node_id
WHERE p.nm BETWEEN 519.3 AND 520.3 ORDER BY abs(p.nm - 519.8);
-- 레시피(막질·가스) → 화학종
SELECT c.label AS combo, sp.label AS species, e2.props->>'evidence' AS evidence
FROM oes_kg.edge e1 JOIN oes_kg.node c ON c.id = e1.s AND e1.rel = 'etches' AND e1.t = 'film:sin'
JOIN oes_kg.edge e2 ON e2.s = c.id AND e2.rel = 'may_produce' JOIN oes_kg.node sp ON sp.id = e2.t;
-- RAG 검색 단계: 전문 검색 + 1단계 이웃
SELECT id, title, ts_rank(tsv, q) AS score FROM oes_kg.card, plainto_tsquery('simple', 'SiOClx SF6') q
WHERE tsv @@ q ORDER BY score DESC LIMIT 8;
```

LLM을 붙일 때는 이 질의 결과(카드 text·citations·decision)를 근거로만 답하게 합니다. 파장 같은 수치는 DB 결과에 있는 값만 쓰게 하고, LLM 호출은 사내 정책이 허용한 경로로 서버 측에서만 합니다.

## 6. 보안
- 공개 원본에는 공개 문헌을 바탕으로 한 지식만 있습니다. 비밀·개인정보·사내 정보는 없습니다.
- 사내 고유 데이터(레시피, OES 궤적, 사내 사례)는 `oes_local`이나 `local_*`에만 둡니다. 공개 저장소로 되돌려 보내지 않습니다.
- 동기화 스크립트는 받기만 합니다. 자격 증명이 필요 없고, 사내 DB 접속 정보는 환경 변수(`PGURL`)로만 넘깁니다.
- 원본 스키마 버전(`schema_version`)이 바뀌면 스크립트가 적재를 거부합니다. 이때는 새 스크립트로 교체하세요.
