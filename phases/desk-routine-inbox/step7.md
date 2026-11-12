# Step 7: routine-integration-check

`tdd: false` / `kind: "measure"` — 사유: 바꿀 파일이 없는 실측 step. 구현 step에 섞지 않는다.

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-routine-inbox-2026-11-12/{PRD,ARCHITECTURE,ADR}.md` — ADR는 번호가 아직 없어 제목으로 부른다(우편함 JSON Lines 두 파일 · 자동 건너뜀 POST · 미답 배지 nav-counts 합침 · 설정 키 두 개). 기존 읽기 규약은 `docs/desk-2026-11-11/ADR.md`의 ADR-009(GET은 읽기만, 캐시·중간 저장 없음)
- `.claude/rules/testing.md` §0 · §1 · §2(엣지 5축은 축마다 "해당 없음"까지 적는다) · `.claude/rules/non-obvious-patterns.md`
- `.claude/rules/non-obvious-patterns.md`의 「서버 · 화면」 줄(2026-11-12 회색 배지 사고) — 이 step이 있는 이유
- `page/server.py`(`serve_forever`, 서버를 띄우는 방법) · `page/index.html`(`/routine` · `/nav-counts` 호출부) · `tests/test_desk_server_review.py`(가짜 데이터 서버를 띄우는 방법)

## 계약 (이 phase 전체가 같은 값을 쓴다 — 코드의 `desk/routine.py` 상수와 docstring이 정본이 된다)

- **질문 줄**(wiki가 질문함에 한 줄씩 씀): 필수 `id`(비어 있지 않은 문자열) · `date`(`YYYY-MM-DD`) · `kind`(비어 있지 않은 문자열) · `text`(비어 있지 않은 문자열). 선택 `options`(`[{"key": str, "label": str}, ...]`, 비어 있지 않은 리스트). 같은 `id`가 여러 줄이면 **마지막 줄이 이긴다**. 필수 필드가 없거나 형식이 틀린 줄은 "깨진 줄"이다
- **답 줄**(desk가 답함에 한 줄씩 씀): `id` · `status`(`"answered"` | `"skipped"`) · `value`(answered일 때만, 비어 있지 않은 문자열) · `note`(선택, 문자열) · `at`(`datetime.now().isoformat()` 문자열). 같은 `id`의 **마지막 줄이 이긴다**. 깨진 줄은 건너뛰고 개수를 센다
- **입력 모양 3가지**(서버가 문항마다 `input`으로 내려 준다. 화면은 이 값만 보고 그린다): `"choice"`(선택지 하나 고르기) · `"long"`(여러 줄 글) · `"line"`(한 줄). 판정: `options`가 있으면 `choice` → 없으면 `kind == "복습"`이면 `choice`이고 기본 선택지 `[{"key":"known","label":"알았다"},{"key":"unsure","label":"헷갈림"}]`을 서버가 채워 준다 → `kind == "설명"`이면 `long` → 그 밖(재시험·결정·원칙·모르는 종류)은 `line`. 모르는 종류도 에러가 아니다(PRD 「모르는 종류」)
- **답 검증**: 문항 `id`가 질문함에 있어야 한다. `answered`면 `value`가 비어 있지 않은 문자열이고 길이 상한 이하(상한 값은 `desk/routine.py`의 상수 하나, 4000자 — AI 가정, Finn이 쓰며 바꿀 수 있다). `choice` 입력이면 `value`는 그 문항 선택지의 `key` 중 하나. `note`는 문자열이고 같은 상한 이하
- **상태**: 문항의 마지막 답 줄이 없으면 `unanswered`, 있으면 그 `status`
- **오늘 / 지난**: 오늘은 서버 시계(`page/server.py`의 `_today()`) 기준이다. `date`가 오늘이면 오늘 문항, 오늘보다 앞이면 지난 문항. 미래 날짜 문항은 어디에도 세지 않고 보이지 않는다

## 작업

코드를 바꾸지 않는다. **지어낸 임시 폴더**에 가짜 데이터로 서버를 띄워 화면이 읽는 필드를 서버가 실제로 보내는지 잰다. 임시 폴더는 스크래치패드/`tempfile`에만 만들고 레포에는 아무것도 남기지 않는다.

1. 임시 폴더에 `config.json`(`routine_questions` · `routine_answers`를 임시 경로로, `DESK_HOME`·설정 위치는 환경변수로 바꿔 끼운다)과 가짜 질문함을 만든다: 오늘 날짜 문항 5개(종류 설명·복습·재시험·결정·원칙 하나씩, 결정은 `options` 포함) + 오늘 날짜의 모르는 종류(`샘플종류`) 1개 + 어제 날짜 미답 1개 + 깨진 줄 1줄. 내용은 `샘플 문항 A`처럼 지어낸 것이다
2. 서버를 띄워 `curl`로 `POST /routine/rollover` → `GET /routine` → `GET /nav-counts`를 부르고, 응답 키가 `page/index.html`이 읽는 필드(`input` · `options` · `state` · `value` · `note` · `groups` · `past` · `broken` · `missing`, `/nav-counts`의 `routine` · `errors`)와 하나도 빠지지 않고 일치하는지 대조한다(화면 JS에서 읽는 키 이름을 grep으로 뽑아 응답 키와 비교한다)
3. 어제 미답 문항이 rollover 뒤 `past`에서 `skipped`로 나오는지, `/nav-counts`의 `routine`이 오늘 미답 수(6)와 같은지 확인한다
4. 서버를 내리고 임시 폴더를 지운다. 레포의 `git status`가 깨끗한지 확인한다

브라우저에서 눈으로 보는 확인(카드 모양 · 배지)은 서브에이전트가 브라우저 도구를 못 쓸 수 있다. 못 했으면 `미확인: 브라우저 렌더`를 summary에 **그대로** 적는다 — 통과로 적지 않는다. 그 확인은 이 phase가 끝난 뒤 메인 세션이 가짜 데이터 서버로 한다.

## Acceptance Criteria

- `summary`에 실행한 명령(백틱)과 결과(키 대조 결과 · rollover 전후 상태 · 배지 숫자 · 브라우저 렌더 확인 여부)가 있다(measure 규칙)
- `git status --short`가 비어 있다(레포 변경 0)

## 검증 절차

1. 위 1~4를 실제로 실행한다.
2. 결과를 `phases/desk-routine-inbox/index.json`의 step 7에 기록: 키가 어긋났거나 rollover가 틀리면 `status:"blocked"` + `blocked_reason`에 어긋난 키 이름(원인 step 번호 포함) / 통과면 `status:"completed"` + `summary`.

## 금지사항

- hook 우회(`--no-verify`) · 자동 생성물 직접 수정 · 요청 범위 밖 수정 · **테스트 파일 수정**(구현 단계에서) 금지. `desk/`는 `page/` · `scripts/` · `hooks/`를 import하지 않는다(의존 방향 `page/` · `scripts/` · `hooks/` → `desk/`)
- 이 step이 맡지 않은 파일은 고치지 않는다(아래 「작업」에 적힌 파일만). 쌓기만 하는 기록(`docs/`의 지난 설계 · ADR 본문 · `phases/*/`)은 고치지 않는다
