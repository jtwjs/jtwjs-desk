# Step 10: guard-test

`tdd: false` — 사유: 이 검사는 만들어지는 시점에 이미 통과하는 회귀 방지 테스트라 RED 커밋(실패하는 테스트)이 존재할 수 없다. 러너의 RED 판정과 못 같이 둔다.

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-2026-11-11/{PRD,ARCHITECTURE,ADR}.md` — PRD 수용 조건(레포 건강도 "코드에 subprocess 호출 없음") · ARCHITECTURE 「읽기 규약」 · 「테스트 전략」 금지 검사 · ADR-009
- `desk/`와 `page/server.py`(앞 step 산출물 포함) — 검사 대상
- `tests/test_desk_core.py` — 테스트 문체
- `.claude/rules/testing.md` §0

## 작업

`tests/test_desk_guard.py` 한 파일만 추가한다. 소스 문자열 grep이 아니라 **`ast`로 파싱**해서 본다(docstring · 주석의 단어에 오탐하지 않게).

- 대상: `desk/*.py`와 `page/*.py`(`hooks/`는 대상이 아니다 — 서버 기동용 `Popen`은 이미 있는 것이고 이 규칙 밖, ARCHITECTURE 「읽기 규약」)
- 단언 1: 위 파일에 `import subprocess` · `from subprocess import …` 가 없다
- 단언 2: `os.system(...)` 호출 · `Popen(...)` 호출 · `os.popen(...)` 호출이 없다
- 단언 3: `desk/*.py`와 `page/*.py`가 `hooks` · `scripts` 패키지를 import하지 않는다(ARCHITECTURE 「경계 · 의존 방향」)
- 실패 메시지에 어느 파일 · 어느 줄인지 낸다
- 이 테스트가 앞으로 새 모듈에도 자동 적용되게 파일 목록은 glob으로 만든다

### 🔴 CRITICAL

- 이 step은 테스트 파일 하나만 더한다. 소스를 고쳐 통과시키지 않는다 — 실패하면 그 사실과 위반 위치를 `blocked_reason`에 적고 멈춘다(앞 step의 결과 문제)
- 사람 이름 · vault 원문을 넣지 않는다

## Acceptance Criteria

- `verify.test` 통과(`typecheck` · `lint` · `build`는 이 레포에 없음)
- `python3 -m unittest tests.test_desk_guard`가 통과하고, 임시로 `desk/`에 `import subprocess` 한 줄을 넣으면 실패하는지 **한 번 직접 확인**한 뒤 되돌린다(`summary`에 확인 사실을 적는다. 되돌린 뒤 `git status`에 소스 변경이 없어야 한다)

## 검증 절차

1. AC 명령 실행과 위반 주입 확인.
2. `git status`에 `tests/test_desk_guard.py` 외 변경이 없음을 확인.
3. 결과를 `phases/desk-ledger-tabs/index.json` step 10에 기록.

## 금지사항

- hook 우회(`--no-verify`) · 요청 범위 밖 수정 금지. 소스 파일 · `phases/desk/` · `docs/` · `hooks/` · `scripts/`는 고치지 않는다.
