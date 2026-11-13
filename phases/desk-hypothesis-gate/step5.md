# Step 5: signal-verify

> `kind: "measure"`, `tdd: false` — 바꿀 파일이 없는 확인 전용 step이다. 화면이 서버 응답을 실제로 읽는지(서버 · 파서 · 화면을 이어 붙인 곳)를 가짜 원장으로 한 번 더 지나가 본다. 구현 step(4)의 브라우저 확인과 별개로, 전체 흐름이 맞물렸는지만 본다.

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-hypothesis-gate-2026-11-12/PRD.md` 수용 조건 표(특히 읽기 전용 · 원문 없음 · 실패 격리 · 화면 연결)
- `.claude/rules/non-obvious-patterns.md` (「서버 · 화면」 — 2026-11-12 회색 배지 사고)
- `phases/desk-hypothesis-gate/step1.md` 「계약」, `step4.md` 「Acceptance Criteria」

## 작업

코드·문서·캔버스를 고치지 않는다. 아래를 순서대로 실행하고 결과를 `summary`에 남긴다.

1. 스크래치패드에 가짜 원장 JSONL을 만든다: 영역(FE · BE · infra · domain) 섞인 맡김 줄 + `ref`로 이어진 적중 줄 + 같은 `ref` 두 줄 + 깨진 줄 1개 + `task`가 null인 줄 2개 + 가설 · 이유 칸에 `SECRET-TEXT` 문자열. 사람 이름 · vault 원문은 쓰지 않는다
2. 가짜 `DESK_HOME`/`DESK_CONFIG`(`hypothesis_ledger` = 그 원장, `hypothesis_streak_threshold` = 2)로 서버를 띄우고 `` `curl -s http://127.0.0.1:<port>/hypothesis-signal` `` 응답을 받는다. 응답에 `SECRET-TEXT`가 없는지, 원장 파일의 `shasum`이 요청 전후 같은지 확인한다
3. 브라우저(Chrome 확장)에서 풀스택 탭을 열어 요약 4칸 · 영역 카드 4장 · 깨진 줄 주석(펼침) · 「가설 재요구 중」 배지의 값이 2의 응답과 같은지 **눈으로 대조**한다. 스크린샷은 가짜 데이터만 담긴 것을 스크래치패드에 저장한다. 사용자의 기존 브라우저 탭은 건드리지 않고 새 탭을 쓴다
4. 설정에서 원장 경로를 지운 서버 · 서버를 내린 상태의 화면을 한 번씩 본다
5. 확인이 끝나면 띄운 서버를 내리고 스크래치패드 픽스처를 정리한다

`summary`에 실행한 명령(백틱)과 **본 것 / 못 본 것**을 적는다. 값이 어긋난 곳이 있으면 `error`로 두고 어느 필드가 어디서 버려졌는지(서버 · 파서 · 화면) 한 줄을 남긴다. 못 본 것은 통과로 적지 않는다.

## Acceptance Criteria

- `.claude/harness.json`의 `verify.test` 통과
- `summary`에 명령(백틱) + 결과 + 본 것 / 못 본 것이 있다(러너가 measure step에 요구한다)

## 검증 절차

1. AC 명령을 실제 실행한다.
2. 결과를 `phases/desk-hypothesis-gate/index.json`의 step 5에 기록: 성공 → `completed` + `summary` / 어긋남 → `error` + `error_message` / 차단 → `blocked` + `blocked_reason`.

## 금지사항

- hook 우회(`--no-verify`) 금지
- 이 step은 코드 · 문서 · 캔버스 파일을 고치지 않는다(`phases/desk-hypothesis-gate/index.json`의 기록만). 원장 파일은 읽기만 하고 고치지 않는다
