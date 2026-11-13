# Step 7: signal-repo-rows

> `tdd: true`: `desk/signal.py` 순수 함수 추가라 짝 테스트가 있다. Finn 결정(2026-11-13, 레포별 보기 선택지 A)으로 REVIEW 전에 끼운 step이다.

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-hypothesis-gate-2026-11-12/PRD.md` 「결정」 표의 **레포별 보기** 행 · 수용 조건 표의 **레포별 보기** 행
- `docs/desk-hypothesis-gate-2026-11-12/ARCHITECTURE.md` 「레포별 보기」 행
- `desk/signal.py` 전체(`parse_ledger` · `_is_hit` · `_is_correction` · `_apply_corrections` · `compute_signal`). 이미 있는 계약(키 이름 · 함수 시그니처)은 바꾸지 않는다
- `tests/test_desk_signal.py` · `tests/test_desk_signal_correction.py` (모양 참고, **고치지 않는다**)
- `.claude/rules/testing.md` §0 · `.claude/rules/non-obvious-patterns.md`

## 작업

**`desk/signal.py`만 고친다**(+ 테스트 파일 한 개: `tests/test_desk_signal_repo.py`). 새 함수 둘, 둘 다 파일을 읽거나 쓰지 않는 순수 함수다.

- `repos_of(rows: list) -> list`: **맡김 줄**(`ref` 키가 없는 줄)의 `repo`를 원장 순서대로 중복 없이 모은 이름 목록. `repo`가 없거나 비었거나 문자열이 아니면 「(알수없음)」 한 묶음으로 센다(목록에서는 맨 뒤 한 번만)
- `filter_rows(rows: list, repo) -> list`: `repo`가 `None`이거나 `repos_of(rows)`에 없으면 `rows` 그대로(같은 내용). 있으면 그 레포의 맡김 줄만 남기고, **적중 줄 · 보정 줄은 `ref`가 남은 맡김 줄의 `ts`와 같을 때만** 남긴다(적중·보정 줄에는 `repo`가 없다). 원래 순서를 유지한다
- 맡김 줄의 레포 판정은 `_text(row.get("repo"))`가 비면 「(알수없음)」이다. 이 상수는 한 곳에만 둔다
- `compute_signal`은 **바꾸지 않는다**(거른 목록을 그대로 받는다). 응답 키도 더하지 않는다(`repos`는 step 8이 서버 응답에 싣는다)

### 🔴 CRITICAL (CLAUDE.md 그대로)

- 응답 · 반환값에 원문(가설 · 이유)을 싣지 않는다. 사람 이름 · vault 원문을 코드와 테스트에 넣지 않는다(가짜 값 `repo-a` · `repo-b` · `task-1` · `t01`만)
- 파일을 읽거나 쓰지 않는 순수 함수 구조를 유지한다
- `desk/signal.py`와 위 테스트 파일 밖은 고치지 않는다

## Acceptance Criteria

- `verify.test` 통과(기존 테스트 전부)
- 테스트가 단언한다:
  - `repos_of`: a, b, a, 빈 repo 줄 → `["repo-a", "repo-b", "(알수없음)"]`. 적중·보정 줄은 목록에 들지 않는다
  - `filter_rows(rows, "repo-a")`: a 맡김 줄만 + 그 `ts`를 `ref`로 가진 적중·보정 줄만 남는다. b의 적중 줄은 빠진다
  - 거른 목록을 `compute_signal`에 넣은 값이 a 줄만 가진 원장을 직접 넣은 값과 같다(가설 먼저 · 이유 없이 수락 · 영역별 · 연속 · 건너뜀)
  - `filter_rows(rows, None)` · 없는 이름 → 입력과 같은 결과
  - 「(알수없음)」으로 거르면 `repo`가 빈 줄(+ 그 줄의 적중·보정 줄)만 남는다
  - 반환값에 가짜 원문(`SECRET-TEXT`)이 든 칸은 줄 dict 그대로일 뿐 새로 더해지지 않는다(기존 줄 dict를 변형하지 않는다)

## 검증 절차

1. AC 명령을 실제 실행한다.
2. 결과를 `phases/desk-hypothesis-gate/index.json`의 step 7에 기록(성공 `completed` + `summary` / 실패 `error` / 차단 `blocked`).

## 금지사항

- hook 우회(`--no-verify`) · 요청 범위 밖 수정 · **테스트 파일 수정**(구현 단계에서) 금지
- `desk/signal.py`와 위 테스트 파일 밖은 고치지 않는다. 기존 `tests/test_desk_signal*.py`도 고치지 않는다. 쌓기만 하는 기록은 고치지 않는다
