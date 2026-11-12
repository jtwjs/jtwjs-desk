# Step 3: routine-mailbox-write

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-routine-inbox-2026-11-12/{PRD,ARCHITECTURE,ADR}.md` — ADR는 번호가 아직 없어 제목으로 부른다(우편함 JSON Lines 두 파일 · 자동 건너뜀 POST · 미답 배지 nav-counts 합침 · 설정 키 두 개). 기존 읽기 규약은 `docs/desk-2026-11-11/ADR.md`의 ADR-009(GET은 읽기만, 캐시·중간 저장 없음)
- `.claude/rules/testing.md` §0 · §1 · §2(엣지 5축은 축마다 "해당 없음"까지 적는다) · `.claude/rules/non-obvious-patterns.md`
- `desk/routine.py` — step 1 산출물. **같은 파일에 함수를 더한다**(step 1의 함수는 고치지 않는다) · `desk/atomic.py` — 임시 파일 + `os.replace` 쓰기 규약(이 step의 쓰기는 JSON Lines **덧붙이기**라 `write_json_atomic`을 쓰지 않는다. ADR 「우편함 JSON Lines」가 줄 덧붙이기를 정했다)

## 계약 (이 phase 전체가 같은 값을 쓴다 — 코드의 `desk/routine.py` 상수와 docstring이 정본이 된다)

- **질문 줄**(wiki가 질문함에 한 줄씩 씀): 필수 `id`(비어 있지 않은 문자열) · `date`(`YYYY-MM-DD`) · `kind`(비어 있지 않은 문자열) · `text`(비어 있지 않은 문자열). 선택 `options`(`[{"key": str, "label": str}, ...]`, 비어 있지 않은 리스트). 같은 `id`가 여러 줄이면 **마지막 줄이 이긴다**. 필수 필드가 없거나 형식이 틀린 줄은 "깨진 줄"이다
- **답 줄**(desk가 답함에 한 줄씩 씀): `id` · `status`(`"answered"` | `"skipped"`) · `value`(answered일 때만, 비어 있지 않은 문자열) · `note`(선택, 문자열) · `at`(`datetime.now().isoformat()` 문자열). 같은 `id`의 **마지막 줄이 이긴다**. 깨진 줄은 건너뛰고 개수를 센다
- **입력 모양 3가지**(서버가 문항마다 `input`으로 내려 준다. 화면은 이 값만 보고 그린다): `"choice"`(선택지 하나 고르기) · `"long"`(여러 줄 글) · `"line"`(한 줄). 판정: `options`가 있으면 `choice` → 없으면 `kind == "복습"`이면 `choice`이고 기본 선택지 `[{"key":"known","label":"알았다"},{"key":"unsure","label":"헷갈림"}]`을 서버가 채워 준다 → `kind == "설명"`이면 `long` → 그 밖(재시험·결정·원칙·모르는 종류)은 `line`. 모르는 종류도 에러가 아니다(PRD 「모르는 종류」)
- **답 검증**: 문항 `id`가 질문함에 있어야 한다. `answered`면 `value`가 비어 있지 않은 문자열이고 길이 상한 이하(상한 값은 `desk/routine.py`의 상수 하나, 4000자 — AI 가정, Finn이 쓰며 바꿀 수 있다). `choice` 입력이면 `value`는 그 문항 선택지의 `key` 중 하나. `note`는 문자열이고 같은 상한 이하
- **상태**: 문항의 마지막 답 줄이 없으면 `unanswered`, 있으면 그 `status`
- **오늘 / 지난**: 오늘은 서버 시계(`page/server.py`의 `_today()`) 기준이다. `date`가 오늘이면 오늘 문항, 오늘보다 앞이면 지난 문항. 미래 날짜 문항은 어디에도 세지 않고 보이지 않는다

## 작업

러너가 이 step을 테스트 먼저 → 구현으로 한 호출에서 돌린다. **`desk/routine.py`(step 1 파일에 추가)와 새 테스트 파일 `tests/test_desk_routine_write.py`만** 만든다. 이 step은 파일을 읽고 쓰는 얇은 껍질이다(순수 함수는 step 1에 있다).

- 모듈 수준 락 하나(`threading.Lock`). **답함에 쓰는 모든 경로가 이 락을 잡는다** — 서버가 `ThreadingHTTPServer`라 요청이 겹칠 수 있다(ARCHITECTURE 「자동 건너뜀」 행)
- `read_text_or_none(path: Path | None) -> str | None`: 파일이 없거나 못 읽으면 `None`(예외 없음)
- `append_answer(answers_path: Path, line: dict) -> None`: 락 안에서 JSON 한 줄(`ensure_ascii=False`) + `\n`을 **한 번의 `write`**로 덧붙인다(`"a"` 모드, `encoding="utf-8"`). 디렉터리가 없으면 만든다. 파일 끝이 개행으로 끝나지 않으면(앞 쓰기가 깨졌으면) 개행부터 쓴다
- `save_answer(questions_path: Path, answers_path: Path, body: dict, now: datetime) -> list[str]`: 락 안에서 질문함·답함을 읽고 `validate_answer`로 검증, 통과하면 `{"id", "status":"answered", "value", "note"(있을 때만), "at": now.isoformat()}`를 덧붙인다. 위반이 있으면 쓰지 않고 위반 목록을 돌려준다(통과면 빈 리스트)
- `rollover(questions_path: Path, answers_path: Path, today: date, now: datetime) -> int`: 락 안에서 **질문함과 답함을 이 시점에 다시 읽고**, 날짜가 `today`보다 앞서고 답 줄이 **하나도 없는** 문항마다 `{"id", "status":"skipped", "at": now.isoformat()}`를 덧붙인다. 덧붙인 줄 수를 돌려준다. 이미 답 줄(`answered` · `skipped`)이 있는 문항에는 쓰지 않는다 → **같은 호출을 여러 번 해도 결과가 같다(멱등)**. 답함 파일이 없으면 만든다. 질문함이 없으면 0

### 🔴 데이터 무결성 (벗어나면 안 되는 규칙)

- 마지막 줄이 이기는 규칙 때문에 **답 뒤에 건너뜀이 덧붙으면 답이 지워진다.** `rollover`는 쓰기 직전에 답함을 다시 읽는 것이 핵심이다(락 안에서 읽고 쓴다)
- 같은 파일에 쓰는 쪽은 desk뿐이다(wiki는 질문함만 쓴다). 질문함은 desk가 절대 쓰지 않는다

### 🔴 CRITICAL (CLAUDE.md · 설계문서에서 그대로)

- 사람 이름 · vault 원문 · 세션 대화 원문을 레포와 상태 파일에 넣지 않는다. 픽스처는 지어낸 문항(`샘플 문항 A` 같은 가짜)이다
- 훅은 모델 토큰을 쓰지 않는다 — 이 phase는 훅을 건드리지 않는다
- GET은 읽기만 한다(ADR-009). 파일 쓰기는 POST 핸들러에서만 한다

## Acceptance Criteria

- `.claude/harness.json`의 `verify.test`(`python3 -m unittest discover -s tests`) 통과. `typecheck` · `lint` · `build`는 이 레포에 없다
- `tests/test_desk_routine_write.py` 단언: `save_answer`가 검증 통과 시 한 줄을 덧붙이고 위반 시 파일을 안 바꾼다 · 답을 고쳐 다시 저장하면 줄이 하나 늘고 마지막 줄이 이긴다 · `rollover`가 지난 답 없는 문항에만 건너뜀을 찍고 오늘·미래·이미 답한 문항·이미 건너뜀인 문항에는 안 찍는다 · 두 번 부르면 두 번째는 0줄 · 질문함이 없으면 0 · 파일 끝 개행이 없을 때 줄이 안 붙는다 · **동시성: 스레드 여러 개가 `save_answer`와 `rollover`를 동시에 부른 뒤, 답한 문항에 건너뜀이 마지막 줄로 남은 경우가 0건이다**(스레드는 `threading.Barrier`로 동시에 출발, 결과로 단언하고 시간 sleep에 의존하지 않는다)
- 엣지 5축: 빈 값(빈 파일) · 비정상 입력(검증 위반) · 실패 경로(파일 없음 · 디렉터리 없음) · 상태 전이(unanswered → answered → 고쳐 씀, unanswered → skipped) · 동시성(위 단언)

## 검증 절차

1. AC 명령을 실제 실행한다.
2. 아키텍처 대조 — `docs/desk-routine-inbox-2026-11-12/ARCHITECTURE.md`의 결정 표(자동 건너뜀 · 미답 배지 · 엔드포인트)와 일치하는지, 의존 방향을 지켰는지.
3. `desk/routine.py`가 `page/` · `scripts/` · `hooks/`를 import하지 않는지, 답함이 아닌 파일(질문함 · 설정)에 쓰는 호출이 없는지 확인.
3. 결과를 `phases/desk-routine-inbox/index.json`의 step 3에 기록: 성공 → `status:"completed"` + `summary`(1~2줄, 다음 step이 쓸 함수 이름과 반환 키 포함) / 실패 → `status:"error"` + `error_message` / 차단 → `status:"blocked"` + `blocked_reason`.

## 금지사항

- hook 우회(`--no-verify`) · 자동 생성물 직접 수정 · 요청 범위 밖 수정 · **테스트 파일 수정**(구현 단계에서) 금지. `desk/`는 `page/` · `scripts/` · `hooks/`를 import하지 않는다(의존 방향 `page/` · `scripts/` · `hooks/` → `desk/`)
- 이 step이 맡지 않은 파일은 고치지 않는다(아래 「작업」에 적힌 파일만). 쌓기만 하는 기록(`docs/`의 지난 설계 · ADR 본문 · `phases/*/`)은 고치지 않는다
