# Step 9: score-parse-grade-color

`tdd: true` — 점수 파일에서 무엇을 읽느냐는 도메인 판정(파서 계약)이라 RED 먼저.

## 배경 (대화 기록 없이 읽을 수 있게)

레포 건강도 화면의 등급 배지는 색 이름(`green`/`amber`/`red`)을 받아 의미색으로 칠한다(`page/index.html`의 `GRADE_TONE`). 그런데 서버가 `total` · `grade`만 내려서 배지가 항상 회색이다(실제 브라우저에서 확인함). 채점 도구(`ai-readiness-cartography`)는 점수 JSON에 이미 `grade_color`(`green`/`amber`/`red`)를 쓴다. 새 매핑 규칙을 만들지 않고 그 값을 그대로 전달한다. 이 step은 파서(`desk/`)만, 서버 전달은 step 10이 한다.

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-2026-11-12/{PRD,ARCHITECTURE,ADR}.md`, `.claude/rules/testing.md` §0
- `desk/ledger.py` — `parse_score`, `find_score_file`
- `tests/test_desk_ledger_signals.py`의 `TestParseScore` — 기존 단언 패턴(현재 `{"total": 72, "grade": "B"}` 그대로 단언)

## 작업

`desk/ledger.py`의 `parse_score(text)`가 `grade_color`도 읽는다.

- 값이 문자열이고 소문자로 바꾼 값이 `green` · `amber` · `red` 중 하나일 때만 결과 dict에 `"grade_color": <소문자 값>`을 넣는다
- 키가 없거나, 문자열이 아니거나, 위 셋 밖의 값이면 **키 자체를 넣지 않는다**(기존 `{"total", "grade"}` 결과와 동일). 예외를 던지지 않는다
- `total` · `grade`가 없으면 기존처럼 `None`. 파일을 열지 않는 순수 함수라는 성질을 유지한다
- 테스트(`tests/test_desk_ledger_signals.py`에 추가, 기존 테스트는 고치지 않는다): 세 색 각각 통과 · 대문자 `GREEN`은 소문자로 · 모르는 색(`blue`)은 키 없음 · 숫자 등 비문자열은 키 없음 · 키 없음이면 기존 결과 그대로

### 🔴 CRITICAL (`CLAUDE.md`에서 그대로)

- 사람 이름 · vault 원문 · 세션 대화 원문을 레포와 상태 파일에 넣지 않는다(테스트 픽스처도 지어낸 값만)
- 훅은 모델 토큰을 쓰지 않는다. `hooks/`를 건드리지 않는다
- 런타임은 Python 표준 라이브러리만. 외부 패키지를 들이지 않는다

## Acceptance Criteria

- `python3 -m unittest discover -s tests` 통과(`.claude/harness.json`의 `verify.test`; `typecheck` · `lint` · `build`는 이 레포에 없음)

## 검증 절차

1. 위 AC 명령을 실제 실행한다.
2. `git status`에 `desk/ledger.py`와 테스트 파일 외 변경이 없는지 확인한다.
3. 결과를 `phases/desk-redesign-ui/index.json`의 해당 step에 기록: 성공 → `completed` + `summary`(1~2줄) / 실패 → `error` + `error_message` / 판단 불가 → `blocked` + `blocked_reason`.

## 금지사항

- hook 우회(`--no-verify`) · 요청 범위 밖 수정 · **`page/` · `hooks/` · `scripts/` 수정 금지**. `phases/` · `docs/` · `.claude/design/`은 고치지 않는다. 구현 step에서 테스트 파일의 기존 단언을 고치지 않는다.
- 쌓기만 하는 기록은 고치지 않는다.
