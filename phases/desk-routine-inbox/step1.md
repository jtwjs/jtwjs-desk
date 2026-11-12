# Step 1: routine-mailbox-parse

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-routine-inbox-2026-11-12/{PRD,ARCHITECTURE,ADR}.md` — ADR는 번호가 아직 없어 제목으로 부른다(우편함 JSON Lines 두 파일 · 자동 건너뜀 POST · 미답 배지 nav-counts 합침 · 설정 키 두 개). 기존 읽기 규약은 `docs/desk-2026-11-11/ADR.md`의 ADR-009(GET은 읽기만, 캐시·중간 저장 없음)
- `.claude/rules/testing.md` §0 · §1 · §2(엣지 5축은 축마다 "해당 없음"까지 적는다) · `.claude/rules/non-obvious-patterns.md`
- `desk/ledger.py` — 순수 함수 + 깨진 입력을 값으로 돌리는 파서 패턴(`parse_inbox`) · `desk/validate.py` — 어긴 항목 목록을 돌려주는 검증 패턴 · `tests/test_desk_ledger_learn.py` — 테스트 배치·이름 규칙

## 계약 (이 phase 전체가 같은 값을 쓴다 — 코드의 `desk/routine.py` 상수와 docstring이 정본이 된다)

- **질문 줄**(wiki가 질문함에 한 줄씩 씀): 필수 `id`(비어 있지 않은 문자열) · `date`(`YYYY-MM-DD`) · `kind`(비어 있지 않은 문자열) · `text`(비어 있지 않은 문자열). 선택 `options`(`[{"key": str, "label": str}, ...]`, 비어 있지 않은 리스트). 같은 `id`가 여러 줄이면 **마지막 줄이 이긴다**. 필수 필드가 없거나 형식이 틀린 줄은 "깨진 줄"이다
- **답 줄**(desk가 답함에 한 줄씩 씀): `id` · `status`(`"answered"` | `"skipped"`) · `value`(answered일 때만, 비어 있지 않은 문자열) · `note`(선택, 문자열) · `at`(`datetime.now().isoformat()` 문자열). 같은 `id`의 **마지막 줄이 이긴다**. 깨진 줄은 건너뛰고 개수를 센다
- **입력 모양 3가지**(서버가 문항마다 `input`으로 내려 준다. 화면은 이 값만 보고 그린다): `"choice"`(선택지 하나 고르기) · `"long"`(여러 줄 글) · `"line"`(한 줄). 판정: `options`가 있으면 `choice` → 없으면 `kind == "복습"`이면 `choice`이고 기본 선택지 `[{"key":"known","label":"알았다"},{"key":"unsure","label":"헷갈림"}]`을 서버가 채워 준다 → `kind == "설명"`이면 `long` → 그 밖(재시험·결정·원칙·모르는 종류)은 `line`. 모르는 종류도 에러가 아니다(PRD 「모르는 종류」)
- **답 검증**: 문항 `id`가 질문함에 있어야 한다. `answered`면 `value`가 비어 있지 않은 문자열이고 길이 상한 이하(상한 값은 `desk/routine.py`의 상수 하나, 4000자 — AI 가정, Finn이 쓰며 바꿀 수 있다). `choice` 입력이면 `value`는 그 문항 선택지의 `key` 중 하나. `note`는 문자열이고 같은 상한 이하
- **상태**: 문항의 마지막 답 줄이 없으면 `unanswered`, 있으면 그 `status`
- **오늘 / 지난**: 오늘은 서버 시계(`page/server.py`의 `_today()`) 기준이다. `date`가 오늘이면 오늘 문항, 오늘보다 앞이면 지난 문항. 미래 날짜 문항은 어디에도 세지 않고 보이지 않는다

## 작업

러너가 이 step을 테스트 먼저 → 구현으로 한 호출에서 돌린다. **새 파일 `desk/routine.py` + `tests/test_desk_routine.py`만** 만든다. 전부 순수 함수다(파일을 열지 않는다 — 텍스트를 받는다).

- 상수: `ANSWER_MAX_CHARS = 4000`, `REVIEW_DEFAULT_OPTIONS`(위 계약의 기본 선택지)
- `parse_questions(text: str) -> tuple[dict[str, dict], int]`: 줄마다 JSON으로 읽는다. 반환은 (`id` → 마지막 줄의 문항 dict, 깨진 줄 수). 빈 줄은 깨진 줄이 아니라 무시한다. 깨진 줄 = JSON이 아님 · 객체가 아님 · 필수 필드 누락/형식 오류 · `options`가 있는데 형식 오류. 깨진 줄이 같은 `id`의 앞 줄을 지우지 않는다(깨진 줄은 `id`를 모르면 건너뛰기만)
- `parse_answers(text: str) -> tuple[dict[str, dict], int]`: 같은 규칙으로 (`id` → 마지막 답 줄, 깨진 줄 수). 깨진 답 줄 = JSON 아님 · `status`가 두 값 밖 · `answered`인데 `value`가 비어 있음 · `id` 누락
- `input_shape(q: dict) -> str` 와 `effective_options(q: dict) -> list | None`: 계약의 판정 그대로. `choice`가 아니면 `None`
- `question_state(q: dict, answers: dict) -> str`: `"unanswered"` | `"answered"` | `"skipped"`
- `validate_answer(q: dict | None, body: dict) -> list[str]`: 계약의 「답 검증」. 어긴 필드 이름 목록(빈 리스트면 통과). 문항이 없으면 `["id"]`. 예외를 던지지 않는다
- `split_by_date(questions: dict, answers: dict, today: date) -> dict`: 반환 `{"today": [문항…], "past": [문항…]}`. `today` 목록은 `date == today`인 문항 전부(답한 것 포함), `past`는 `date < today`이면서 상태가 `answered`가 아닌 문항(건너뜀 + 아직 답 줄이 없는 것). 미래 날짜는 어디에도 없다. 각 문항 dict에 `input` · `options`(effective) · `state` · `value` · `note`를 합쳐 넣는다. 날짜 형식이 `YYYY-MM-DD`가 아닌 문항은 파서 단계에서 깨진 줄이라 여기 오지 않는다
- `group_by_kind(items: list) -> list[dict]`: `[{"kind": str, "items": [...]}, ...]`, 종류는 처음 나온 순서, 항목 순서 유지
- `unanswered_today_count(questions: dict, answers: dict, today: date) -> int`: 오늘 날짜 문항 중 상태가 `unanswered`인 수(`skipped` · `answered`는 안 센다)

### 🔴 CRITICAL (CLAUDE.md · 설계문서에서 그대로)

- 사람 이름 · vault 원문 · 세션 대화 원문을 레포와 상태 파일에 넣지 않는다. 픽스처는 지어낸 문항(`샘플 문항 A` 같은 가짜)이다
- 훅은 모델 토큰을 쓰지 않는다 — 이 phase는 훅을 건드리지 않는다
- GET은 읽기만 한다(ADR-009). 파일 쓰기는 POST 핸들러에서만 한다

## Acceptance Criteria

- `.claude/harness.json`의 `verify.test`(`python3 -m unittest discover -s tests`) 통과. `typecheck` · `lint` · `build`는 이 레포에 없다
- `tests/test_desk_routine.py` 단언: 마지막 줄이 이긴다(질문·답 둘 다) · 깨진 줄은 건너뛰고 개수만 · 필수 필드 누락 · 빈 줄 무시 · 입력 모양 판정 5경우(`options` 있음 · 복습 · 설명 · 재시험 · 모르는 종류) · 복습에 `options`가 오면 그것이 이긴다 · `validate_answer`가 choice 밖 value · 빈 value · 상한 초과 · 없는 id를 잡는다 · `split_by_date`가 미래 제외, 지난 건너뜀 포함, 지난 답함 제외 · `unanswered_today_count`가 건너뜀을 안 센다
- 엣지 5축: 빈 값(빈 텍스트 → `({}, 0)`) · 비정상 입력(깨진 줄) · 실패 경로(검증 위반) · 상태 전이(답이 늘면 상태가 바뀜) · 동시성(해당 없음 — 순수 함수)

## 검증 절차

1. AC 명령을 실제 실행한다.
2. 아키텍처 대조 — `docs/desk-routine-inbox-2026-11-12/ARCHITECTURE.md`의 결정 표(자동 건너뜀 · 미답 배지 · 엔드포인트)와 일치하는지, 의존 방향을 지켰는지.
3. `desk/routine.py`에 `open(` · `read_text` · `subprocess`가 없는지 확인(순수 함수). 이 step이 끝난 뒤 `page/` · `scripts/`를 import하지 않는지도 확인.
3. 결과를 `phases/desk-routine-inbox/index.json`의 step 1에 기록: 성공 → `status:"completed"` + `summary`(1~2줄, 다음 step이 쓸 함수 이름과 반환 키 포함) / 실패 → `status:"error"` + `error_message` / 차단 → `status:"blocked"` + `blocked_reason`.

## 금지사항

- hook 우회(`--no-verify`) · 자동 생성물 직접 수정 · 요청 범위 밖 수정 · **테스트 파일 수정**(구현 단계에서) 금지. `desk/`는 `page/` · `scripts/` · `hooks/`를 import하지 않는다(의존 방향 `page/` · `scripts/` · `hooks/` → `desk/`)
- 이 step이 맡지 않은 파일은 고치지 않는다(아래 「작업」에 적힌 파일만). 쌓기만 하는 기록(`docs/`의 지난 설계 · ADR 본문 · `phases/*/`)은 고치지 않는다
