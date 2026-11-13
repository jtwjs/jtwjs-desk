# Step 6: signal-correction

> `tdd: true` — 계산 함수(`desk/signal.py`)의 규칙 추가라 짝 테스트가 있다. step 1~5가 끝난 뒤 REVIEW 전에 끼운 수정 step이다(Finn 2026-11-13).

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-hypothesis-gate-2026-11-12/PRD.md` 「결정」 표의 **보정 줄** 행 · 수용 조건 표(가설 먼저 · 이유 없이 수락)
- `desk/signal.py` — `parse_ledger` · `compute_signal` · `_is_hit` · `_last_hits` · `_gate`. 이미 있는 계약(키 이름)은 바꾸지 않는다
- `tests/test_desk_signal.py` (모양 참고, **고치지 않는다**) · `tests/test_desk_server_hypothesis.py` (서버 테스트 모양 참고, 고치지 않는다) · `page/server.py`의 `build_hypothesis_signal`
- `.claude/rules/testing.md` §0 · `.claude/rules/non-obvious-patterns.md`

## 작업

**`desk/signal.py`만 고친다**(+ 테스트 파일 한 개: `tests/test_desk_signal_correction.py`).

원장에는 세 종류의 줄이 있다. 맡김 줄 · 적중 줄(`ref` + `hit` ∈ right|partial|wrong) · **보정 줄 `{ref, gate, by:"finn"}`**.

- 보정 줄 판정: `ref`가 있고 `gate` 키가 **있으며** 유효한 `hit` 값이 없는 줄. 같은 `ref`는 원장 순서상 마지막 보정이 유효하다. `gate` 값이 `null`이면 그 맡김 줄의 gate를 비우는 보정이다(유효)
- `compute_signal`은 시작에서 `ref` ↔ 원래 맡김 줄의 `ts`로 보정 값을 맡김 줄의 `gate`에 덮어쓴 **유효 gate 기준**으로 나머지를 그대로 센다: 의미 있는 줄 · 이유 없이 수락 분모(`gate`가 있는 줄만, 비면 제외) · 영역별 건수 · 연속 · 건너뜀. 새 키를 응답에 더하지 않는다
- 보정 줄은 맡김 줄로 세지 않는다(`no_ident`·`meaningful`·`skipped`·`empty`에 들지 않는다). 적중 줄 처리(`_last_hits`)는 그대로다. `ref`가 어느 맡김 줄에도 없는 보정은 조용히 무시한다
- 보정이 없는 원장의 결과는 지금과 **완전히 같다**(기존 `tests/test_desk_signal.py`가 그대로 통과해야 한다)

### 🔴 CRITICAL (CLAUDE.md 그대로)

- 응답에 원문(가설 · 이유)을 싣지 않는다. 사람 이름 · vault 원문을 코드와 테스트에 넣지 않는다(가짜 값 `repo-a` · `task-1` · `t01`만)
- 파일을 읽거나 쓰지 않는 순수 함수 구조를 유지한다
- 새 파일에서 `desk/signal.py` 밖(`page/server.py` · 화면)은 고치지 않는다

## Acceptance Criteria

- `verify.test` 통과(기존 테스트 전부)
- 테스트가 단언한다:
  - 보정으로 `gate`가 `null` → `"설계"`가 된 줄이 이유 없이 수락 분모에 들어온다
  - 보정으로 `"설계"` → `null`이 된 줄은 분모 · 의미 있는 줄에서 빠진다(다른 칸이 비었을 때)
  - 같은 `ref` 보정 두 줄 → 마지막이 유효
  - 보정 줄이 `meaningful` · `no_ident` · `skipped` · `empty`를 바꾸지 않는다(보정만 있는 원장 → `empty: true`)
  - 어느 줄에도 없는 `ref`의 보정은 무시
  - 적중 줄과 보정 줄이 섞여도 영역별 적중 건수가 그대로
  - 보정이 없는 원장은 이전과 같은 dict(키 집합 포함)
  - 서버 경로: 보정 줄이 든 가짜 원장 파일로 `build_hypothesis_signal`을 부르면 유효 gate 기준 값이 나오고, 응답 본문에 원문 칸 값(`SECRET-TEXT`)이 없다

## 검증 절차

1. AC 명령을 실제 실행한다.
2. 결과를 `phases/desk-hypothesis-gate/index.json`의 step 6에 기록(성공 `completed` + `summary` / 실패 `error` / 차단 `blocked`).

## 금지사항

- hook 우회(`--no-verify`) · 요청 범위 밖 수정 · **테스트 파일 수정**(구현 단계에서) 금지
- `desk/signal.py`와 위 테스트 파일 밖은 고치지 않는다. 기존 `tests/test_desk_signal.py` · `tests/test_desk_server_hypothesis.py`도 고치지 않는다. 쌓기만 하는 기록은 고치지 않는다
