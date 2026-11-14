# Step 1: board-core

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-kanban-2026-11-14/{PRD,ARCHITECTURE,ADR}.md` — PRD 「수용 조건」 표가 이 step의 테스트 입력이다. ARCHITECTURE 「엔드포인트」·「상태 규약」·「경계」가 계약이다. ADR 값(sort 파라미터 모양 · 열 이동 방향 · 시작 요청 파일 분리)은 ADR 제목으로 찾아 읽고 이 문서에 복사하지 않는다
- `.claude/rules/testing.md` §0 · §1 · §2, `.claude/rules/non-obvious-patterns.md` 전체(항상 로드되는 함정 목록)
- `desk/routine.py` · `desk/trends.py` — 순수 함수 + 얇은 파일 함수를 한 모듈에 두는 선례(이 step은 순수 함수만)
- `tests/test_desk_trends.py`(또는 `tests/test_desk_trends*.py` 중 순수 함수 테스트) — 테스트 스타일

## 작업

러너가 이 step을 테스트 먼저 → 구현으로 한 호출에서 돌린다(`tdd: true`). 테스트만 담은 커밋이 먼저 있어야 하고, 그 커밋 뒤 테스트 파일을 고치면 러너가 되돌린다. **`desk/board.py`(신규, 순수 함수만)와 `tests/test_desk_board.py`(신규)만** 만든다. 파일 읽기·쓰기·`paths`는 step 2다. 이 step의 함수는 파일을 열지 않고 `time`·`datetime`도 부르지 않는다(시각·오늘 날짜는 인자로 받는다).

계약(시그니처 수준):

- 상수: `COLUMNS = ("planned", "doing", "done")`, 링크 한도는 상수로 둔다: 이름 1~40자, URL 최대 2000자, 카드당 최대 5개(PRD 「레퍼런스 링크」 행)
- `check_title(title) -> str`: 앞뒤 공백을 뗀 제목을 돌려준다. 빈 문자열 · 공백뿐 · 문자열이 아님은 `ValueError`
- `check_link(name, url) -> tuple[str, str]`: 이름 1~40자(앞뒤 공백 제거 뒤), URL은 `http://` 또는 `https://`로 시작하고 2000자 이하. 아니면 `ValueError`. `javascript:` · `file:` · `/Users/...` 같은 로컬·vault 경로는 거절
- `check_links(links) -> list[tuple[str, str]]`: 목록 전체를 검증(6개 이상 `ValueError`). 하나라도 틀리면 예외(부분 통과 없음)
- `can_move(cur, new) -> bool`: `planned→doing`, `doing→done`만 True. 거꾸로 · 건너뛰기 · 같은 열 · 모르는 열은 False
- `elapsed_days(start_at, pr_at, today) -> int | None`: 「진행」 카드 경과 일수. 기준은 `pr_at`이 있으면 `pr_at`, 없으면 `start_at`(요청 파일의 `at`), 둘 다 없으면 None. `start_at`·`pr_at`은 epoch float, `today`는 `datetime.date`. 날짜(로컬 달력일) 차이이며 음수면 0
- `candidate_mark(card, steps) -> bool`: `card["column"] == "doing"` · `card.get("pr_at")` 없음 · `steps`(연결된 phases의 step status 목록)가 1개 이상이고 전부 `"completed"`일 때만 True. step 0개 → False
- `connection_state(card, phase_exists) -> str | None`: 열이 `doing`이고 `task`가 없으면 `"designing"`(설계 중), `task`가 있는데 `phase_exists`가 False면 `"disconnected"`(연결 끊김), 그 밖에는 None
- `progress(steps) -> dict | None`: `{"done": 완료 step 수, "total": 전체}`, step 0개면 None

## Acceptance Criteria

- `.claude/harness.json`의 `verify.test`(`python3 -m unittest discover -s tests`) 통과. `typecheck` · `lint` · `build`는 이 레포에 없다(비어 있다)
- `tests/test_desk_board.py` 단언: 빈 · 공백 제목 거절 · 앞뒤 공백 제거 · 링크 이름 0자 / 41자 거절, 40자 통과 · URL `javascript:` · `file:` · 로컬 경로 · 2001자 거절, `https://example.com/a` 통과 · 6개 거절 · 하나 틀리면 전체 거절 · 열 이동 표 전체(허용 2개, 거부 나머지) · 경과 일수: 요청 후 3일 / `pr_at`이 있으면 거기서부터 / 둘 다 없으면 None / 음수는 0 · 후보 표식: 전부 completed → True, 하나 pending → False, step 0개 → False, `pr_at` 있음 → False, 열이 `doing`이 아님 → False · 연결 상태 세 경우 · 진행도
- 엣지 5축: 빈 값 · 비정상 입력(문자열 아님 · 경계 40/41, 2000/2001) · 실패 경로(거절 예외) · 상태 전이(열 이동 표) · 동시성(해당 없음: 순수 함수)

## 검증 절차

1. AC 명령을 실제 실행한다.
2. `ARCHITECTURE.md` 「계층 배치」·「경계」와 대조한다.
3. 결과를 `phases/desk-kanban/index.json`의 이 step에 기록: 성공 → `completed` + `summary`(1~2줄) / 실패 → `error` + `error_message` / 차단 → `blocked` + `blocked_reason`.

### 🔴 CRITICAL (CLAUDE.md 그대로)

- 사람 이름 · vault 원문 · 세션 대화 원문을 레포와 상태 파일에 넣지 않는다. 픽스처는 지어낸 레포 · 카드 · `example.com` 링크다
- 훅은 모델 토큰을 쓰지 않는다 — 이 phase는 훅을 건드리지 않는다
- hook 우회 금지 (`--no-verify` 등)
- desk는 프로세스를 실행하지 않는다(서브프로세스 호출 없음) · URL을 열어 보거나 가져오지 않는다(HTTP 요청 없음). 쓰는 곳은 `board/<레포>/` 아래 카드 · 요청 · 링크 파일뿐이다

## 금지사항

- hook 우회(`--no-verify`) · 자동 생성물 직접 수정 · 요청 범위 밖 수정 · **테스트 파일 수정**(구현 단계에서) 금지
- 쌓기만 하는 기록(`docs/`의 지난 설계 · ADR 본문 · `phases/*/`)은 고치지 않는다. 이 step이 맡지 않은 파일은 고치지 않는다
