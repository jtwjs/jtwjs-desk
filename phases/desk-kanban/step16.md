# Step 16: board-server-review2-fixes

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-kanban-2026-11-14/{PRD,ARCHITECTURE,ADR}.md`
- `.claude/rules/testing.md`, `.claude/rules/non-obvious-patterns.md` 전체 — 특히 「sdd · 응답 키 추가」: 응답에 키를 더하면 그 응답을 비교하는 기존 테스트를 grep으로 전부 찾아 **RED 커밋에서** 고친다(GREEN에서 고치면 러너가 되돌린다)
- `page/server.py` — `build_board`(약 534행) · `build_board_card`(약 560행)
- `desk/board.py` — `read_refs`(깨짐 여부를 함께 돌려준다) · `build_card_detail`
- 기존 테스트: `tests/test_desk_server_board_get.py`(상세 응답 키 집합 단언 약 344행, `my..repo` 설정 테스트 약 186행). `grep -n "pr_at.*done_at\|elapsed_days.*refs" tests/*.py`로 같은 종류를 전부 찾는다

## 작업

`tdd: true`. 서버(`page/server.py`)만 고친다. 화면은 step 17. 이 step은 리뷰 2회차 🟡2와 🟢2의 서버 몫이다.

1. **읽지 못한 레포는 `repos`에서 뺀다.** `build_board`에서 `list_cards`가 `ValueError`·`OSError`를 낸 레포는 카드 0 + 못 읽음 1건으로 세는 것은 그대로 두되, 응답의 `repos` 목록에서는 뺀다(새 카드 모달이 거절될 레포를 고르게 하지 않으려고). 응답에 새 키를 더하지 않는다. 테스트: `my..repo`가 설정에 있어도 `GET /board`는 200, 그 이름이 `repos`에 없고 다른 레포는 있다
2. **카드 상세에 `refs_broken`(bool)을 더한다.** `build_board_card`가 `read_refs`가 돌려주는 깨짐 정보를 버리지 않고, 상세 응답에 `refs_broken: true|false`를 붙인다(파일 없음은 false, 파일이 있는데 깨졌으면 true). `desk/board.py`의 `build_card_detail` 시그니처는 바꾸지 않는다. 테스트: 링크 파일이 깨진 카드의 `GET /board/card` 응답은 `refs_broken == true`이고 `refs == []`, 멀쩡하거나 없으면 false
3. 상세 응답의 키 집합을 비교하는 기존 단언(약 344행)에 `refs_broken`을 더하는 수정은 **RED 커밋에서** 한다. 같은 종류를 grep으로 전부 찾아 고친다

CRITICAL(`CLAUDE.md` 그대로): 사람 이름 · vault 원문 · 세션 대화 원문을 레포와 상태 파일에 넣지 않는다(픽스처는 지어낸 값). 훅은 모델 토큰을 쓰지 않는다 — 이 step은 훅을 건드리지 않는다. desk는 프로세스를 실행하지 않는다.

## Acceptance Criteria

- RED: 새·바뀐 테스트만 담긴 커밋이 먼저 있고 그 시점에 실패한다
- `python3 -m unittest discover -s tests` 통과(`typecheck` · `lint` · `build`는 이 레포에 없다)

## 검증 절차

1. 위 AC 명령을 실제 실행한다
2. ARCHITECTURE.md의 상세 응답 필드 설명에 `refs_broken` 한 줄을 같은 커밋에 더한다
3. `phases/desk-kanban/index.json`의 이 step에 기록: 성공 → `completed` + `summary` / 실패 → `error` + `error_message` / 차단 → `blocked` + `blocked_reason`

## 금지사항

- hook 우회(`--no-verify`) 금지 · 요청 범위 밖 수정 금지 · GREEN 단계에서 테스트 파일 수정 금지
- `valid_repo_name` · `desk/board.py`의 `_check_repo` · `page/index.html` · 훅 · `.claude/design/` 수정 금지
- 쌓기만 하는 기록(회고 · 지난 설계 · `phases/*/` 다른 step)은 고치지 않는다
