# Step 2: board-files

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-kanban-2026-11-14/{PRD,ARCHITECTURE,ADR}.md` — PRD 「수용 조건」 표가 이 step의 테스트 입력이다. ARCHITECTURE 「엔드포인트」·「상태 규약」·「경계」가 계약이다. ADR 값(sort 파라미터 모양 · 열 이동 방향 · 시작 요청 파일 분리)은 ADR 제목으로 찾아 읽고 이 문서에 복사하지 않는다
- `.claude/rules/testing.md` §0 · §1 · §2, `.claude/rules/non-obvious-patterns.md` 전체(항상 로드되는 함정 목록)
- `desk/board.py`(step 1 산출물) · `desk/atomic.py`(`write_json_atomic`, 쓰기는 이것만) · `desk/paths.py`(홈 폴더 함수 스타일) · `desk/routine.py`(`read_text_or_none` 등 얇은 파일 함수 선례)
- `tests/test_desk_server_review.py`의 임시 `DESK_HOME` 만드는 방식(`_ReviewCase`) — 파일 쓰기 테스트의 틀

## 작업

러너가 이 step을 테스트 먼저 → 구현으로 한 호출에서 돌린다(`tdd: true`). 테스트만 담은 커밋이 먼저 있어야 하고, 그 커밋 뒤 테스트 파일을 고치면 러너가 되돌린다. **`desk/paths.py`(함수 하나 추가) · `desk/board.py`(파일 읽기·쓰기 함수 추가) · `tests/test_desk_board_files.py`(신규)만** 고친다. 엔드포인트는 step 4·5다.

파일 배치(ARCHITECTURE 「상태 규약」): `DESK_HOME/board/<레포>/` 아래
- `<id>.json` — 카드: `title` · `note` · `column` · `task` · `created_at` · `doing_at` · `pr_at` · `done_at` · `archived_at`(시각은 epoch float, 없으면 null)
- `<id>.request.json` — 시작 요청: `{"at": epoch}` 하나. 시작 요청 시각은 **카드가 아니라 이 파일의 `at`** 이다
- `<id>.refs.json` — 링크: `{"refs": [{"id", "name", "url"}]}`. 링크 id는 서버(이 함수)가 만든다

카드 id 형식은 `<epoch 정수 초>-<무작위 4자리 소문자 16진>`이다(시각 순으로 정렬되고 같은 초 충돌을 줄인다. 이 형식은 이 step이 정하는 값이며 `ARCHITECTURE.md` 「아직 열린 것」을 구현 뒤 갱신 대상으로 남긴다). id를 받는 모든 함수는 이 형식(정규식)과 레포 이름의 경로 탈출 문자(`/` · `..` · 빈 값)를 먼저 거절한다.

함수(시그니처 수준, `desk/board.py`):
- `paths.board_dir(repo) -> Path`: `DESK_HOME/board/<repo>` (다른 `paths` 함수와 같은 홈 해석)
- `new_card_id(now) -> str`
- `add_card(repo, title, note, now, links=()) -> dict`: 검증(`check_title` · `check_links`)을 **먼저 전부** 하고, 같은 레포에 **같은 제목의 예정 카드**가 있으면 `DuplicateTitle` 예외(409용, 파일은 늘지 않는다). 통과하면 카드(열 `planned`, `created_at=now`) 쓰고 링크가 있으면 링크 파일을 쓴다. 검증이 하나라도 실패하면 어떤 파일도 안 생긴다(검증 먼저, 쓰기 나중). 진행 · 완료 · 보관 카드나 다른 레포의 같은 제목은 통과한다
- `read_card(repo, id)`, `list_cards(repo) -> tuple[list[dict], int]`: 카드 목록(각 항목에 `id`와 요청 파일의 `at`을 `requested_at`으로 붙임)과 **깨진 파일 수**. JSON이 깨졌거나 필수 필드가 없는 카드 파일은 건너뛰고 센다. 요청 · 링크 파일이 깨졌으면 요청은 없는 것으로, 링크는 빈 목록으로 보고 별도 깨진 수에 센다(카드는 살린다)
- `delete_card(repo, id)`: 예정 카드만. 아니면 `WrongColumn`(409용). 카드 · 요청 · 링크 파일을 함께 지운다
- `archive_card(repo, id, now)`: 예정이 아닌 카드만(예정이면 `WrongColumn`), `archived_at=now`. `revive_card(repo, id)`: `archived_at`을 null로
- `request_start(repo, id, now)`: 예정 카드만, 요청 파일이 이미 있으면 `AlreadyRequested`(409용). 카드 파일은 건드리지 않는다(요청 파일만 쓴다)
- `cancel_request(repo, id)`: 예정이고 요청 파일이 있을 때만 파일을 지운다. 아니면 `WrongColumn`/`NoRequest`(409용)
- `add_ref(repo, id, name, url) -> dict` · `update_ref(repo, id, ref_id, name, url)` · `delete_ref(repo, id, ref_id)`: 검증은 `check_link`. 6번째 추가는 `TooManyLinks`(409용). 없는 카드 · 링크는 `NotFound`(404용). 보관 카드를 포함해 모든 열에서 허용한다
- 이동(지휘 세션용, step 6이 부른다): `move_card(repo, id, new_column, now)` — `can_move` 거짓이면 `ValueError`. `doing`으로 가면 `doing_at=now`, `done`이면 `done_at=now`. 요청 파일은 지우지 않는다(요청됨 배지는 열이 `doing`이 되면 화면이 안 그린다). `mark_pr(repo, id, now)` — `doing`이 아니거나 `pr_at`이 이미 있으면 `ValueError`. `set_task(repo, id, task)` — task 이름 문자열 저장만 한다(`phases/{task}/index.json`이 없어도 저장, 이름은 경로 탈출 문자만 거른다). 세 함수 모두 카드 파일 한 개만 읽고 `write_json_atomic`로 다시 쓴다
- 모든 쓰기는 `desk/atomic.py`의 `write_json_atomic`만 쓴다. `Path.write_text` 직접 쓰기 금지

## Acceptance Criteria

- `.claude/harness.json`의 `verify.test`(`python3 -m unittest discover -s tests`) 통과. `typecheck` · `lint` · `build`는 이 레포에 없다(비어 있다)
- `tests/test_desk_board_files.py` 단언(임시 `DESK_HOME`, 지어낸 레포): 추가 → 파일 · 열 `planned` · `created_at` · 제목 빔 거절 · 같은 레포 같은 예정 제목 거절(파일 수 그대로) · 진행 카드나 다른 레포의 같은 제목은 통과 · 링크가 섞인 추가에서 링크 하나가 틀리면 카드 파일도 없음 · 삭제는 예정만, 요청 · 링크 파일도 사라짐 · 진행 카드 삭제는 거절하고 파일 그대로 · 보관 · 되살리기 · 시작 요청 파일 정확히 하나, 두 번째는 거절, 카드 파일 내용 안 바뀜 · 취소는 요청 파일만 지움, 요청 없으면 거절 · 링크 5개까지, 6번째 거절, 수정은 개수 그대로, 삭제는 그 링크만 · 깨진 카드 파일은 건너뛰고 깨진 수가 센다 · 깨진 링크 파일은 빈 목록 · 이동 순서(planned→doing→done만, 날짜 기록) · `mark_pr` 두 번째 거절 · `set_task`는 phases 없는 이름도 저장 · 경로 탈출 id · 레포 이름 거절 · 쓰기 도중 읽는 쪽이 반쯤 쓴 파일을 못 보는 것(`write_json_atomic` 사용 확인으로 갈음)
- 엣지 5축: 빈 값(카드 0장 · 링크 0개) · 비정상 입력(깨진 JSON · 경로 탈출) · 실패 경로(없는 카드 · 409 계열) · 상태 전이(열 이동 · 보관 · 요청 · 취소) · 동시성(서버와 `desk.py`가 같은 파일을 안 쓰도록 요청 · 링크를 별도 파일로 나눈 것을 단언)

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
