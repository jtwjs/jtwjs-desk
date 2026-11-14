# Step 5: board-post-endpoints

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-kanban-2026-11-14/{PRD,ARCHITECTURE,ADR}.md` — PRD 「수용 조건」 표가 이 step의 테스트 입력이다. ARCHITECTURE 「엔드포인트」·「상태 규약」·「경계」가 계약이다. ADR 값(sort 파라미터 모양 · 열 이동 방향 · 시작 요청 파일 분리)은 ADR 제목으로 찾아 읽고 이 문서에 복사하지 않는다
- `.claude/rules/testing.md` §0 · §1 · §2, `.claude/rules/non-obvious-patterns.md` 전체(항상 로드되는 함정 목록)
- `desk/board.py`(step 1~3 산출물, 쓰기 함수와 예외 종류)
- `page/server.py` — `do_POST` 라우팅 체인 · `_check_post_guard`(토큰 · Origin · Host) · 요청 본문 JSON 읽는 방식 · `valid_repo_name`
- `tests/test_desk_server_trends_post.py` · `tests/test_desk_server_review.py`(`_ReviewCase`) — POST 가드 · 파일 쓰기 서버 테스트 스타일(토큰 없으면 403, Origin · Host 어긋남)

## 작업

러너가 이 step을 테스트 먼저 → 구현으로 한 호출에서 돌린다(`tdd: true`). 테스트만 담은 커밋이 먼저 있어야 하고, 그 커밋 뒤 테스트 파일을 고치면 러너가 되돌린다. **`page/server.py`(POST 라우트)와 새 테스트 파일 `tests/test_desk_server_board_post.py`만** 만든다/고친다.

엔드포인트(ARCHITECTURE 「엔드포인트」 표가 계약, 본문은 JSON):
- `POST /board/add` `{repo, title, note, links?: [{name, url}]}` → 200 `{id}`. 검증 실패(빈 제목 · 모르는 레포 · 링크 오류) 400 · 같은 레포 같은 예정 제목 409(`{"error": "duplicate"}`) · 링크 검증이 먼저고 카드는 안 만든다
- `POST /board/delete` `{repo, id}` → 예정만, 아니면 409 · 없으면 404
- `POST /board/archive` · `POST /board/revive` `{repo, id}`
- `POST /board/start` `{repo, id}` → 예정 카드만, 요청 파일이 이미 있으면 409
- `POST /board/cancel` `{repo, id}` → 예정이고 요청 파일이 있을 때만, 아니면 409
- `POST /board/ref/add` `{repo, id, name, url}` · `/board/ref/update` `{repo, id, ref_id, name, url}` · `/board/ref/delete` `{repo, id, ref_id}` → 검증 400 · 6번째 추가 409 · 없는 카드 · 링크 404
- 모든 POST는 기존 `_check_post_guard`를 **그대로** 거친다(토큰이 없으면 403, Origin · Host 규칙 포함). 새 가드를 만들지 않는다
- 오류 응답에 예외 메시지 · 파일 경로를 싣지 않는다(`{"error": 짧은 코드}`)
- 서버는 `now`를 `time.time()`으로, 날짜는 기존 `_today()`로 얻는다. `board` 함수는 인자로 받는다(테스트가 시각을 고정할 수 있게)
- 이 step도 `/nav-counts`를 건드리지 않는다

## Acceptance Criteria

- `.claude/harness.json`의 `verify.test`(`python3 -m unittest discover -s tests`) 통과. `typecheck` · `lint` · `build`는 이 레포에 없다(비어 있다)
- `tests/test_desk_server_board_post.py` 단언: 엔드포인트마다 토큰이 없으면 403이고 파일 그대로 · 정상 add 뒤 `GET /board`(step 4)에 카드가 보임 · 빈 제목 400 · 모르는 레포 400 · 중복 제목 409 · 링크 6번째 · `javascript:` URL · 이름 41자 · URL 2001자 거절 · add 중 링크가 틀리면 카드 파일도 안 생김 · delete는 예정만 · start 두 번째 409, 요청 파일 하나 · cancel 뒤 배지 사라짐, 요청 없으면 409 · archive/revive 왕복 · ref add/update/delete 왕복과 수정은 개수 그대로 · 보관 카드의 링크 수정 허용 · `/nav-counts` 키 집합 그대로
- 엣지 5축: 빈 값 · 비정상 입력(깨진 본문 · 경로 탈출) · 실패 경로(404 · 409) · 상태 전이(add → start → cancel) · 동시성(요청 파일이 이미 있을 때 두 번째 start 거절)

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
- `page/index.html` · `scripts/desk.py`는 고치지 않는다(각각 step 6 · 7 이후)
