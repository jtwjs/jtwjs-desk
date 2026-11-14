# Step 4: board-get-endpoints

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-kanban-2026-11-14/{PRD,ARCHITECTURE,ADR}.md` — PRD 「수용 조건」 표가 이 step의 테스트 입력이다. ARCHITECTURE 「엔드포인트」·「상태 규약」·「경계」가 계약이다. ADR 값(sort 파라미터 모양 · 열 이동 방향 · 시작 요청 파일 분리)은 ADR 제목으로 찾아 읽고 이 문서에 복사하지 않는다
- `.claude/rules/testing.md` §0 · §1 · §2, `.claude/rules/non-obvious-patterns.md` 전체(항상 로드되는 함정 목록)
- `desk/board.py`(step 1~3 산출물) · `desk/config.py` · `desk/paths.py`
- `page/server.py` — `do_GET` 라우팅(`/trends` · `/routine` · `/review` 분기 모양) · `valid_repo_name` · `list_phase_indexes` · `_today()` · `config_block`
- `tests/test_desk_server_trends.py`(없으면 `tests/test_desk_server_routine.py`) · `tests/test_desk_server_navcounts_routine.py` — 가짜 `DESK_HOME` · `DESK_CONFIG` 서버 테스트 스타일. 테스트 공통 부품은 `tests/test_desk_server.py`(`base`)

## 작업

러너가 이 step을 테스트 먼저 → 구현으로 한 호출에서 돌린다(`tdd: true`). 테스트만 담은 커밋이 먼저 있어야 하고, 그 커밋 뒤 테스트 파일을 고치면 러너가 되돌린다. **`page/server.py`(GET 라우트 둘 · 읽기 어댑터)와 새 테스트 파일 `tests/test_desk_server_board_get.py`만** 만든다/고친다. 쓰기(POST)는 step 5다.

- `GET /board`: 쿼리 파라미터 `archived` · `repo` · `from` · `to` · `sort_planned` · `sort_doing` · `sort_done` · `q`를 받아 설정의 `repos`(레포 이름 = `Path(root).name`) 각각의 카드를 `list_cards`로 읽고, 각 레포의 `list_phase_indexes(repo_root)`를 `{task: index}`로 만들어 `board.build_view`에 넘긴다. `BadQuery` → 400(`{"error": "..."}`, 예외 메시지 · 파일 경로는 싣지 않는다). 응답 최상위에 `config: config_block(cfg)`와 `repos`(필터 셀렉트용 레포 이름 목록)를 더한다. GET은 **파일을 바꾸지 않는다**
- `GET /board/card?repo=&id=`: `valid_repo_name`과 id 형식을 먼저 거른다(경로 탈출 → 400). 없는 카드 404. 카드 파일 · 링크 파일 · 해당 phase `index.json`을 읽어 `board.build_card_detail` 결과를 돌려준다
- 설정이 없거나 레포가 0개면 `columns`가 비어 있고 200이다(`config`에 안내가 담긴다). 서버는 죽지 않는다
- **`/nav-counts`는 건드리지 않는다.** `tests/test_desk_redesign_integration.py` 36행의 키 집합 단언은 그대로이고 이 phase에서 바뀌지 않는다. 새 엔드포인트라 기존 응답을 비교하는 테스트도 바뀌지 않는다(응답에 키를 더하는 step이 아니다)

## Acceptance Criteria

- `.claude/harness.json`의 `verify.test`(`python3 -m unittest discover -s tests`) 통과. `typecheck` · `lint` · `build`는 이 레포에 없다(비어 있다)
- `tests/test_desk_server_board_get.py` 단언(가짜 설정 · 홈 · 레포 폴더): 카드 3장이 열별로 오고 `badge` · `elapsed_days` · `progress`가 값과 함께 옴(화면이 읽는 필드가 서버 응답에 실제로 있는지 — non-obvious-patterns 「서버 · 화면」) · 필터 · 정렬 · `q` 쿼리가 먹음 · 400 4종 · `/board/card`가 `refs`와 step summary를 줌 · 없는 카드 404 · 경로 탈출 400 · 설정 없음 200 · 레포 0개 200 · GET 전후 `DESK_HOME/board`가 그대로 · 응답 JSON에 가짜 경로 문자열이 없음 · `/nav-counts` 응답 키 집합이 바뀌지 않음(기존 테스트가 이미 있으니 그대로 통과하는지만)
- 엣지 5축: 빈 값 · 비정상 입력 · 실패 경로(설정 없음 · phases 없음) · 상태 전이(보관 후 `archived=1`) · 동시성(해당 없음: 읽기 전용)

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
- `page/index.html`은 고치지 않는다(화면은 step 7 이후)
