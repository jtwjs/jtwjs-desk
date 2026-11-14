# Step 6: board-desk-cli

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-kanban-2026-11-14/{PRD,ARCHITECTURE,ADR}.md` — PRD 「수용 조건」 표가 이 step의 테스트 입력이다. ARCHITECTURE 「엔드포인트」·「상태 규약」·「경계」가 계약이다. ADR 값(sort 파라미터 모양 · 열 이동 방향 · 시작 요청 파일 분리)은 ADR 제목으로 찾아 읽고 이 문서에 복사하지 않는다
- `.claude/rules/testing.md` §0 · §1 · §2, `.claude/rules/non-obvious-patterns.md` 전체(항상 로드되는 함정 목록)
- `desk/board.py`(step 2의 `move_card` · `mark_pr` · `set_task`와 요청 파일 읽기)
- `scripts/desk.py` — argparse 서브커맨드 구성 · 기존 서브커맨드의 출력 · 종료 코드 방식
- `tests/` 중 `scripts/desk.py`를 부르는 테스트(`grep -rl "scripts/desk\|desk.py" tests/`로 찾는다) — 서브프로세스 또는 `main()` 호출 방식과 가짜 `DESK_HOME`

## 작업

러너가 이 step을 테스트 먼저 → 구현으로 한 호출에서 돌린다(`tdd: true`). 테스트만 담은 커밋이 먼저 있어야 하고, 그 커밋 뒤 테스트 파일을 고치면 러너가 되돌린다. **`scripts/desk.py`(서브커맨드 추가)와 새 테스트 파일 `tests/test_desk_board_cli.py`만** 만들거나 고친다. 이 서브커맨드는 **지휘 세션이 부르는 것**이고 desk는 부르지 않는다.

- `desk.py board requests` — 요청 파일이 있는 예정 카드를 `<레포> <id> <제목> <요청 시각>` 한 줄씩 낸다(지휘 세션이 읽는다). 레포 선택 인자 `--repo`(없으면 설정의 모든 레포). 요청이 없으면 아무것도 안 내고 종료 코드 0
- `desk.py board move <레포> <id> <planned|doing|done>` — `board.move_card`. 허용 밖 이동(거꾸로 · 건너뛰기)은 거절하고 종료 코드가 0이 아니며 카드는 그대로다
- `desk.py board pr <레포> <id>` — `board.mark_pr`. `doing`이 아니거나 이미 표시된 카드는 거절(종료 코드 ≠ 0, 파일 그대로). 되돌리는 명령은 만들지 않는다
- `desk.py board link <레포> <id> <task>` — `board.set_task`(task 기록. 이름이 `ref`와 겹치지 않게 `link`다). `phases/{task}/index.json`이 없어도 저장은 된다
- `desk.py`는 카드 내용을 검사하지 않는다(사람 이름 · 원문 금지는 화면 안내와 쓰는 사람의 규칙)
- 출력에 파일 경로 · 예외 스택을 싣지 않고 한 줄 오류만 낸다

## Acceptance Criteria

- `.claude/harness.json`의 `verify.test`(`python3 -m unittest discover -s tests`) 통과. `typecheck` · `lint` · `build`는 이 레포에 없다(비어 있다)
- `tests/test_desk_board_cli.py` 단언: `requests`가 요청 파일 있는 예정 카드만 냄 · `move planned→doing`이 `doing_at`을 적음 · `doing→done`이 `done_at`을 적음 · 거꾸로 · 건너뛰기 · 같은 열 이동은 종료 코드 ≠ 0이고 카드 파일 그대로 · `pr`이 `pr_at`을 한 번만 적고 두 번째 · 예정 카드 · 완료 카드는 거절 · `link`가 task를 저장하고 phases 없는 이름도 저장 · 이동이 끝난 카드 파일을 읽는 쪽이 항상 완전한 JSON을 본다(원자 쓰기) · 이동 뒤 `GET`용 읽기(`board.list_cards`)에 열 · 날짜가 반영됨
- 엣지 5축: 빈 값(요청 0건) · 비정상 입력(없는 카드 · 모르는 열 · 경로 탈출 id) · 실패 경로(거절 종료 코드) · 상태 전이(전 방향 표) · 동시성(서버가 쓰는 요청 파일을 이 명령이 건드리지 않음을 단언)

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
- `page/server.py` · `page/index.html`은 고치지 않는다
