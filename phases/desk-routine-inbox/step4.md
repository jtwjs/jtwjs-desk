# Step 4: count-nav-routine

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-routine-inbox-2026-11-12/{PRD,ARCHITECTURE,ADR}.md` — ADR는 번호가 아직 없어 제목으로 부른다(우편함 JSON Lines 두 파일 · 자동 건너뜀 POST · 미답 배지 nav-counts 합침 · 설정 키 두 개). 기존 읽기 규약은 `docs/desk-2026-11-11/ADR.md`의 ADR-009(GET은 읽기만, 캐시·중간 저장 없음)
- `.claude/rules/testing.md` §0 · §1 · §2(엣지 5축은 축마다 "해당 없음"까지 적는다) · `.claude/rules/non-obvious-patterns.md`
- `page/server.py` — `count_nav`(약 445행) · `config_block` · `build_review` · `do_GET`의 `/nav-counts` 분기 · `tests/test_desk_server_navcounts.py` — 기존 배지 테스트와 `_ReviewCase` 사용법(`tests/test_desk_server_review.py`)

## 계약 (이 phase 전체가 같은 값을 쓴다 — 코드의 `desk/routine.py` 상수와 docstring이 정본이 된다)

- **질문 줄**(wiki가 질문함에 한 줄씩 씀): 필수 `id`(비어 있지 않은 문자열) · `date`(`YYYY-MM-DD`) · `kind`(비어 있지 않은 문자열) · `text`(비어 있지 않은 문자열). 선택 `options`(`[{"key": str, "label": str}, ...]`, 비어 있지 않은 리스트). 같은 `id`가 여러 줄이면 **마지막 줄이 이긴다**. 필수 필드가 없거나 형식이 틀린 줄은 "깨진 줄"이다
- **답 줄**(desk가 답함에 한 줄씩 씀): `id` · `status`(`"answered"` | `"skipped"`) · `value`(answered일 때만, 비어 있지 않은 문자열) · `note`(선택, 문자열) · `at`(`datetime.now().isoformat()` 문자열). 같은 `id`의 **마지막 줄이 이긴다**. 깨진 줄은 건너뛰고 개수를 센다
- **입력 모양 3가지**(서버가 문항마다 `input`으로 내려 준다. 화면은 이 값만 보고 그린다): `"choice"`(선택지 하나 고르기) · `"long"`(여러 줄 글) · `"line"`(한 줄). 판정: `options`가 있으면 `choice` → 없으면 `kind == "복습"`이면 `choice`이고 기본 선택지 `[{"key":"known","label":"알았다"},{"key":"unsure","label":"헷갈림"}]`을 서버가 채워 준다 → `kind == "설명"`이면 `long` → 그 밖(재시험·결정·원칙·모르는 종류)은 `line`. 모르는 종류도 에러가 아니다(PRD 「모르는 종류」)
- **답 검증**: 문항 `id`가 질문함에 있어야 한다. `answered`면 `value`가 비어 있지 않은 문자열이고 길이 상한 이하(상한 값은 `desk/routine.py`의 상수 하나, 4000자 — AI 가정, Finn이 쓰며 바꿀 수 있다). `choice` 입력이면 `value`는 그 문항 선택지의 `key` 중 하나. `note`는 문자열이고 같은 상한 이하
- **상태**: 문항의 마지막 답 줄이 없으면 `unanswered`, 있으면 그 `status`
- **오늘 / 지난**: 오늘은 서버 시계(`page/server.py`의 `_today()`) 기준이다. `date`가 오늘이면 오늘 문항, 오늘보다 앞이면 지난 문항. 미래 날짜 문항은 어디에도 세지 않고 보이지 않는다

## 작업

러너가 이 step을 테스트 먼저 → 구현으로 한 호출에서 돌린다. **`page/server.py`의 `count_nav`와 새 테스트 파일 `tests/test_desk_server_navcounts_routine.py`만** 다룬다(기존 navcounts 테스트는 수정하지 않는다).

- `count_nav(cfg)`의 반환에 `routine`(정수 | `None`)을 더한다: `desk.routine.unanswered_today_count`를 질문함·답함(설정 `routine_questions` · `routine_answers`)을 `read_text_or_none`으로 읽어 센다. 설정이 없거나(`None`) 질문함이 없으면 `0`
- **항목별 격리**: `judge` · `review` · `routine` 각각을 따로 `try/except Exception`으로 감싼다. 한 항목이 예외를 내면 그 항목 값은 `None`이 되고 `routine_error` 식의 이유 키 하나(`{"judge": ..., "review": ..., "routine": None, "errors": {"routine": "<예외 이름 한 줄>"}}`처럼 `errors` 객체)를 붙인다. 예외 메시지 원문 · 경로는 싣지 않는다(`type(exc).__name__`만). 이유 키는 오류가 없으면 `errors`가 빈 객체이거나 아예 없다 — 하나로 정하고 그 모양을 테스트가 고정한다
- 기존 `judge` · `review` 값과 동작은 그대로다. `/nav-counts`는 여전히 읽기 전용이다(ADR-009)

### 🔴 CRITICAL (CLAUDE.md · 설계문서에서 그대로)

- 사람 이름 · vault 원문 · 세션 대화 원문을 레포와 상태 파일에 넣지 않는다. 픽스처는 지어낸 문항(`샘플 문항 A` 같은 가짜)이다
- 훅은 모델 토큰을 쓰지 않는다 — 이 phase는 훅을 건드리지 않는다
- GET은 읽기만 한다(ADR-009). 파일 쓰기는 POST 핸들러에서만 한다

## Acceptance Criteria

- `.claude/harness.json`의 `verify.test`(`python3 -m unittest discover -s tests`) 통과. `typecheck` · `lint` · `build`는 이 레포에 없다
- 새 테스트 단언: 설정이 없으면 `routine == 0` · 오늘 미답 문항 수를 센다(건너뜀·답함·지난 날짜·미래 날짜 제외) · 질문함이 깨져도 `judge` · `review`는 숫자가 나오고 `routine`만 `None` + 이유 · `judge`를 읽는 쪽이 예외를 내도(`unittest.mock.patch`로 `list_judgments`가 예외) `review` · `routine`은 나온다 · 기존 `/nav-counts` 테스트가 그대로 통과한다
- 엣지 5축: 빈 값 · 비정상 입력(깨진 질문함) · 실패 경로(항목 하나 예외) · 상태 전이(답하면 줄어듦) · 동시성(해당 없음 — 읽기 전용)

## 검증 절차

1. AC 명령을 실제 실행한다.
2. 아키텍처 대조 — `docs/desk-routine-inbox-2026-11-12/ARCHITECTURE.md`의 결정 표(자동 건너뜀 · 미답 배지 · 엔드포인트)와 일치하는지, 의존 방향을 지켰는지.
3. `git diff --stat`로 `page/server.py`와 새 테스트 파일만 바뀌었는지 확인.
3. 결과를 `phases/desk-routine-inbox/index.json`의 step 4에 기록: 성공 → `status:"completed"` + `summary`(1~2줄, 다음 step이 쓸 함수 이름과 반환 키 포함) / 실패 → `status:"error"` + `error_message` / 차단 → `status:"blocked"` + `blocked_reason`.

## 금지사항

- hook 우회(`--no-verify`) · 자동 생성물 직접 수정 · 요청 범위 밖 수정 · **테스트 파일 수정**(구현 단계에서) 금지. `desk/`는 `page/` · `scripts/` · `hooks/`를 import하지 않는다(의존 방향 `page/` · `scripts/` · `hooks/` → `desk/`)
- 이 step이 맡지 않은 파일은 고치지 않는다(아래 「작업」에 적힌 파일만). 쌓기만 하는 기록(`docs/`의 지난 설계 · ADR 본문 · `phases/*/`)은 고치지 않는다
