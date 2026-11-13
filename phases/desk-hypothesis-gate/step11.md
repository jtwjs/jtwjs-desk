# Step 11: signal-diff-table

> `tdd: true`: `desk/signal.py` 순수 함수 추가 + 서버 응답 키 추가라 짝 테스트가 있다. Finn 결정(2026-11-13): 난이도 × 상태 건수 표(PRD 「난이도 칸」 행의 표시 모양).

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-hypothesis-gate-2026-11-12/PRD.md` 「결정」 표의 **난이도 칸 `diff`** 행
- `desk/signal.py` 전체(`compute_signal` · `_apply_corrections` · `_last_hits` · `_meaningful` · `_flag`). 기존 함수 시그니처 · `compute_signal` 응답 키는 **바꾸지 않는다**
- `page/server.py`의 `build_hypothesis_signal`
- `tests/test_desk_signal_repo.py` · `tests/test_desk_server_hypothesis_repo.py` (모양 참고, **고치지 않는다**)
- `tests/test_desk_server_hypothesis.py`: 응답을 `compute_signal` 값과 비교하는 줄 하나가 있다(`missing`·`repos`를 빼고 비교). 여기에 `diff`도 뺀다
- `.claude/rules/testing.md` §0 · `.claude/rules/non-obvious-patterns.md` 「sdd · nav-counts」

## 작업

**`desk/signal.py` · `page/server.py`만 고친다**(+ 새 테스트 파일 둘: `tests/test_desk_signal_diff.py`, `tests/test_desk_server_hypothesis_diff.py`).

- 🔴 **기존 테스트 한 줄 수정은 RED 커밋에 넣는다.** `tests/test_desk_server_hypothesis.py`의 비교 줄에서 `diff`도 제외한다. GREEN 단계에서 고치면 러너가 테스트 파일 변경을 되돌리고 실패시킨다
- `desk/signal.py`에 순수 함수 `diff_table(rows: list) -> dict` 추가. 파일을 읽거나 쓰지 않는다. `compute_signal`은 바꾸지 않는다(기존 키 집합 단언이 깨진다)
  - 반환: 키 `easy` · `mid` · `hard` · `none`, 각 값은 `{"right": n, "partial": n, "wrong": n, "pending": n}`. 키는 항상 넷 다 있다(0도 채운다)
  - 대상: 보정을 덮어쓴 맡김 줄 중 **의미 있는 줄**(`compute_signal`의 `meaningful`과 같은 기준)
  - 난이도: 줄의 `diff`가 `easy`·`mid`·`hard` 문자열이면 그 값, 칸이 없거나 `null`이거나 그 밖의 값이면 `none`
  - 상태: `_last_hits`의 마지막 적중 값이 있으면 `right`·`partial`·`wrong`, 없고 `hyp`가 `true`면 `pending`, 둘 다 아니면 어느 칸에도 세지 않는다(영역 카드와 같은 규칙)
- `page/server.py` `build_hypothesis_signal`: 응답에 `"diff": diff_table(거른 rows)`를 더한다. 거르기(레포)는 이미 적용된 rows를 쓴다. `missing` 응답에는 `diff`가 없다. 응답에 원문 칸 값을 싣지 않는다

### 🔴 CRITICAL (CLAUDE.md 그대로)

- 응답에 원문(가설 · 이유)을 싣지 않는다. 사람 이름 · vault 원문을 코드와 테스트에 넣지 않는다(가짜 값 `repo-a` · `task-1` · `t01` · `SECRET-TEXT`만)
- 파일을 읽거나 쓰지 않는 순수 함수 구조를 유지한다. desk는 원장을 쓰지 않는다
- `desk/signal.py` · `page/server.py`와 위 테스트 파일 밖은 고치지 않는다

## Acceptance Criteria

- `verify.test` 통과(기존 테스트 전부)
- 테스트가 단언한다:
  - 쉬움·보통·어려움 줄이 섞인 가짜 원장 → 칸마다 예상 건수
  - `diff` 칸 없음 / `null` / `"x"`(집합 밖) → 전부 `none`
  - 보정 줄로 gate가 비어 의미 없는 줄이 되면 표에서 빠진다
  - 같은 `ref` 적중 줄 둘 → 마지막 값만 센다. 적중 줄 없고 `hyp`만 있으면 `pending`
  - 의미 없는 줄(gate·hyp·rec 전부 비었음)은 어느 칸에도 안 든다
  - 서버: 응답에 `diff`가 있고 값이 `diff_table`과 같다. `?repo=repo-a`로 부르면 a 줄만 센다. 응답 본문에 `SECRET-TEXT` 없음. 원장 없음(`missing`) 응답에는 `diff` 키가 없다
  - 빈 원장 → 네 키 모두 0

## 검증 절차

1. AC 명령을 실제 실행한다.
2. 결과를 `phases/desk-hypothesis-gate/index.json`의 step 11에 기록(성공 `completed` + `summary` / 실패 `error` / 차단 `blocked`).

## 금지사항

- hook 우회(`--no-verify`) · 요청 범위 밖 수정 · **테스트 파일 수정**(구현 단계에서) 금지
- 위 파일 밖은 고치지 않는다. 쌓기만 하는 기록은 고치지 않는다
