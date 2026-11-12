# Step 5: routine-endpoints

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-routine-inbox-2026-11-12/{PRD,ARCHITECTURE,ADR}.md` — ADR는 번호가 아직 없어 제목으로 부른다(우편함 JSON Lines 두 파일 · 자동 건너뜀 POST · 미답 배지 nav-counts 합침 · 설정 키 두 개). 기존 읽기 규약은 `docs/desk-2026-11-11/ADR.md`의 ADR-009(GET은 읽기만, 캐시·중간 저장 없음)
- `.claude/rules/testing.md` §0 · §1 · §2(엣지 5축은 축마다 "해당 없음"까지 적는다) · `.claude/rules/non-obvious-patterns.md`
- `page/server.py` — `_handle_pick` · `_handle_review_done`(토큰 → Origin → Host 가드 `_check_post_guard`와 JSON 본문 읽기 패턴) · `do_GET` / `do_POST` 라우팅 · `config_block` · `missing_row` · `_today()` · `tests/test_desk_server_review.py`의 `_ReviewCase`(서버를 띄우는 통합 테스트 부품)

## 계약 (이 phase 전체가 같은 값을 쓴다 — 코드의 `desk/routine.py` 상수와 docstring이 정본이 된다)

- **질문 줄**(wiki가 질문함에 한 줄씩 씀): 필수 `id`(비어 있지 않은 문자열) · `date`(`YYYY-MM-DD`) · `kind`(비어 있지 않은 문자열) · `text`(비어 있지 않은 문자열). 선택 `options`(`[{"key": str, "label": str}, ...]`, 비어 있지 않은 리스트). 같은 `id`가 여러 줄이면 **마지막 줄이 이긴다**. 필수 필드가 없거나 형식이 틀린 줄은 "깨진 줄"이다
- **답 줄**(desk가 답함에 한 줄씩 씀): `id` · `status`(`"answered"` | `"skipped"`) · `value`(answered일 때만, 비어 있지 않은 문자열) · `note`(선택, 문자열) · `at`(`datetime.now().isoformat()` 문자열). 같은 `id`의 **마지막 줄이 이긴다**. 깨진 줄은 건너뛰고 개수를 센다
- **입력 모양 3가지**(서버가 문항마다 `input`으로 내려 준다. 화면은 이 값만 보고 그린다): `"choice"`(선택지 하나 고르기) · `"long"`(여러 줄 글) · `"line"`(한 줄). 판정: `options`가 있으면 `choice` → 없으면 `kind == "복습"`이면 `choice`이고 기본 선택지 `[{"key":"known","label":"알았다"},{"key":"unsure","label":"헷갈림"}]`을 서버가 채워 준다 → `kind == "설명"`이면 `long` → 그 밖(재시험·결정·원칙·모르는 종류)은 `line`. 모르는 종류도 에러가 아니다(PRD 「모르는 종류」)
- **답 검증**: 문항 `id`가 질문함에 있어야 한다. `answered`면 `value`가 비어 있지 않은 문자열이고 길이 상한 이하(상한 값은 `desk/routine.py`의 상수 하나, 4000자 — AI 가정, Finn이 쓰며 바꿀 수 있다). `choice` 입력이면 `value`는 그 문항 선택지의 `key` 중 하나. `note`는 문자열이고 같은 상한 이하
- **상태**: 문항의 마지막 답 줄이 없으면 `unanswered`, 있으면 그 `status`
- **오늘 / 지난**: 오늘은 서버 시계(`page/server.py`의 `_today()`) 기준이다. `date`가 오늘이면 오늘 문항, 오늘보다 앞이면 지난 문항. 미래 날짜 문항은 어디에도 세지 않고 보이지 않는다

## 작업

러너가 이 step을 테스트 먼저 → 구현으로 한 호출에서 돌린다. **`page/server.py`와 새 테스트 파일 `tests/test_desk_server_routine.py`만** 다룬다. step 1·3의 `desk.routine` 함수와 step 2의 설정 키를 쓴다(그 파일들은 고치지 않는다).

- **`GET /routine`**(Host 가드만, `/nav-counts`와 같은 방식): `config_block(cfg)`와 같은 방식의 설정 안내를 싣는다. 설정이 없으면(`routine_questions`가 `None`) 본문에 `{"config": ..., "date": <오늘>, "groups": [], "past": [], "broken": 0, "missing": [{"what": "질문함", "reason": "설정 없음"}]}` 모양의 이유 행을 준다(경로가 있는데 파일이 없으면 `"파일 없음"`, 읽기 실패는 `"형식 확인 필요"`). 정상이면 `{"config": ..., "date": <오늘 YYYY-MM-DD>, "groups": [{"kind", "items": [...]}], "past": [...], "broken": <질문함·답함 깨진 줄 합>, "missing": []}`. 문항 항목 키: `id · date · kind · text · input · options · state · value · note`(step 1 `split_by_date`와 `group_by_kind`가 만든 그대로). **읽기만 한다 — 파일을 쓰지 않는다(ADR-009)**
- **`POST /routine/answer`**: 토큰 → Origin → Host 가드(`_check_post_guard`) → JSON 본문(`id` · `value` · `note`) → `save_answer`. 본문이 JSON이 아니면 400 `bad json`. 위반이 있으면 400 `{"violations": [...]}`(위반 필드 이름만). 문항이 없으면 404 `question not found`. 성공이면 200 `{"ok": true}`. 설정이 없으면 400 `routine not configured`
- **`POST /routine/rollover`**: 같은 가드 → `rollover(..., today=_today(), now=datetime.now())` → 200 `{"ok": true, "skipped": <줄 수>}`. 설정이 없으면 200 `{"ok": true, "skipped": 0}`(화면이 열릴 때마다 부르므로 설정이 없다고 에러로 만들지 않는다)
- 라우팅: `do_GET`에 `/routine`, `do_POST`에 `/routine/answer` · `/routine/rollover`를 더한다. 기존 라우트는 안 바꾼다

### 🔴 보안 · 무결성

- POST는 `/pick`과 같은 가드(토큰 · Origin · Host)를 쓴다. 응답에는 파일 경로 · 예외 원문을 싣지 않는다
- 서버 쪽 시계는 `_today()` 한 곳이다(테스트가 이 함수를 바꿔 끼운다)

### 🔴 CRITICAL (CLAUDE.md · 설계문서에서 그대로)

- 사람 이름 · vault 원문 · 세션 대화 원문을 레포와 상태 파일에 넣지 않는다. 픽스처는 지어낸 문항(`샘플 문항 A` 같은 가짜)이다
- 훅은 모델 토큰을 쓰지 않는다 — 이 phase는 훅을 건드리지 않는다
- GET은 읽기만 한다(ADR-009). 파일 쓰기는 POST 핸들러에서만 한다

## Acceptance Criteria

- `.claude/harness.json`의 `verify.test`(`python3 -m unittest discover -s tests`) 통과. `typecheck` · `lint` · `build`는 이 레포에 없다
- `tests/test_desk_server_routine.py`(통합, `_ReviewCase`로 서버를 띄움) 단언: GET이 설정 없음 · 파일 없음 · 정상(종류별 묶음 · `input`/`options`/`state`) · 깨진 줄 수를 준다 · **GET을 여러 번 불러도 답함 파일이 안 바뀐다** · POST answer가 토큰 없음/Origin 다름 → 403, 깨진 JSON → 400, 위반(choice 밖 값) → 400, 없는 id → 404, 정상 → 답함에 한 줄 · 답을 고쳐 쓰면 GET의 `value`가 마지막 값 · rollover가 지난 미답 문항을 `past`에서 `skipped`로 바꾸고 두 번째 호출은 `skipped: 0` · **rollover와 answer를 스레드로 동시에 부른 뒤 답한 문항이 `answered`로 남는다** · 설정 없음에서 rollover는 200
- 엣지 5축: 빈 값(설정 없음 · 문항 0건) · 비정상 입력(가드 · 본문) · 실패 경로(파일 없음) · 상태 전이(unanswered → answered → skipped 불가: 답한 문항은 건너뜀 안 됨) · 동시성(위 단언)

## 검증 절차

1. AC 명령을 실제 실행한다.
2. 아키텍처 대조 — `docs/desk-routine-inbox-2026-11-12/ARCHITECTURE.md`의 결정 표(자동 건너뜀 · 미답 배지 · 엔드포인트)와 일치하는지, 의존 방향을 지켰는지.
3. `git diff --stat`로 `page/server.py`와 새 테스트 파일만 바뀌었는지, GET 핸들러 안에 쓰기 호출(`save_answer` · `rollover` · `append_answer`)이 없는지 확인.
3. 결과를 `phases/desk-routine-inbox/index.json`의 step 5에 기록: 성공 → `status:"completed"` + `summary`(1~2줄, 다음 step이 쓸 함수 이름과 반환 키 포함) / 실패 → `status:"error"` + `error_message` / 차단 → `status:"blocked"` + `blocked_reason`.

## 금지사항

- hook 우회(`--no-verify`) · 자동 생성물 직접 수정 · 요청 범위 밖 수정 · **테스트 파일 수정**(구현 단계에서) 금지. `desk/`는 `page/` · `scripts/` · `hooks/`를 import하지 않는다(의존 방향 `page/` · `scripts/` · `hooks/` → `desk/`)
- 이 step이 맡지 않은 파일은 고치지 않는다(아래 「작업」에 적힌 파일만). 쌓기만 하는 기록(`docs/`의 지난 설계 · ADR 본문 · `phases/*/`)은 고치지 않는다
