# Step 13: board-server-hardening

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-kanban-2026-11-14/{PRD,ARCHITECTURE,ADR}.md` (PRD 「남은 것 · 확인 필요」의 「깨진 링크 파일」 줄이 이 step의 결정이다)
- `.claude/rules/testing.md`, `.claude/rules/non-obvious-patterns.md` 전체 — 특히 「sdd · 응답 키 추가」·「sdd · nav-counts」: 기존 단언을 고쳐야 하면 **RED 커밋에 넣는다**(GREEN에서 테스트 파일을 고치면 러너가 되돌린다)
- `desk/board.py` — `read_refs` · `add_ref` · `update_ref` · `delete_ref` · 예외 클래스들 · `list_cards`
- `page/server.py` — `valid_repo_name` · `build_board` · `_handle_board_post`의 예외 → HTTP 매핑
- 기존 테스트: `tests/test_desk_board_files.py`(깨진 링크 파일에 add_ref하면 덮어쓰는 동작을 의도로 고정한 테스트, 약 477행. `grep -n "refs_broken\|read_refs" tests/*.py`로 같은 종류를 전부 찾는다), `tests/test_desk_server_board_get.py`, `tests/test_desk_server_board_post.py`

## 작업

`tdd: true`. 서버 쪽(`desk/board.py`, `page/server.py`)만 고친다. 화면은 step 14.

1. **깨진 링크 파일은 쓰기를 거절한다.** 링크 파일이 있는데 깨졌다(`read_refs`가 깨짐으로 돌려주는 경우)면 `add_ref` · `update_ref` · `delete_ref`는 파일을 쓰지 않고 새 예외 `RefsBroken`을 낸다. 파일이 아예 없는 것은 깨짐이 아니다(그대로 새로 만든다). `POST /board/ref/*` 세 경로는 `RefsBroken`을 **409**(`{"error": "refs broken"}`)로 낸다. 응답에 새 키를 더하지 않는다. 거절됐을 때 링크 파일 내용이 한 바이트도 안 바뀐 것을 테스트로 고정한다
2. **레포 하나가 칸반 전체를 죽이지 않는다.** `build_board`가 레포별로 `board.list_cards(name)`을 부를 때 `ValueError`·`OSError`가 나면 그 레포는 카드 0개 + 못 읽음 1건(`list_cards`가 돌려주는 모양과 같게, 코드로 모양을 확인한다)으로 취급하고 나머지 레포는 정상으로 돌려준다. 재현: 설정에 `valid_repo_name`은 통과하지만 `board._check_repo`는 거절하는 이름(`my..repo`)의 레포가 있어도 `GET /board`가 200이다. `valid_repo_name`·`_check_repo` 자체는 바꾸지 않는다(다른 화면이 쓴다)
3. 기존 테스트 중 1번과 충돌하는 단언(깨진 파일 위에 쓰면 덮어쓴다는 것)은 **RED 커밋에서** 새 동작(예외 + 파일 무변경)으로 고친다

CRITICAL(`CLAUDE.md` 그대로): 사람 이름 · vault 원문 · 세션 대화 원문을 레포와 상태 파일에 넣지 않는다(픽스처는 지어낸 값). 훅은 모델 토큰을 쓰지 않는다 — 이 step은 훅을 건드리지 않는다. desk는 프로세스를 실행하지 않고 URL을 열지 않는다. 쓰기는 기존 `write_json_atomic`을 쓴다.

## Acceptance Criteria

- RED: 새·바뀐 테스트만 담긴 커밋이 먼저 있고 그 시점에 실패한다
- `python3 -m unittest discover -s tests` 통과(`typecheck` · `lint` · `build`는 이 레포에 없다)
- 테스트가 확인하는 것: 깨진 파일에 add/update/delete가 각각 `RefsBroken`과 파일 무변경, 3경로 409, 파일 없음은 정상 추가, `my..repo` 설정에서 `GET /board` 200과 다른 레포 정상 + 못 읽음 건수

## 검증 절차

1. 위 AC 명령을 실제 실행한다
2. ARCHITECTURE 「엔드포인트」·「상태 규약」의 링크 파일 설명과 어긋나지 않는지 확인하고, 깨짐 때 쓰기를 거절한다는 한 줄을 ARCHITECTURE.md 링크 파일 설명 옆에 더한다(문서 한 줄은 같은 커밋에)
3. `phases/desk-kanban/index.json`의 이 step에 기록: 성공 → `completed` + `summary` / 실패 → `error` + `error_message` / 차단 → `blocked` + `blocked_reason`

## 금지사항

- hook 우회(`--no-verify`) 금지 · 요청 범위 밖 수정 금지 · GREEN 단계에서 테스트 파일 수정 금지
- `valid_repo_name` · `_check_repo` · `page/index.html` · 훅 · `.claude/design/` 수정 금지
- 쌓기만 하는 기록(회고 · 지난 설계 · `phases/*/` 다른 step)은 고치지 않는다
