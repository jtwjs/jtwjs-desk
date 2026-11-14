# Step 11: board-card-detail-request-merge

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-kanban-2026-11-14/{PRD,ARCHITECTURE,ADR}.md` — ARCHITECTURE 「엔드포인트」의 `GET /board/card` 응답 계약이 기준이다
- `.claude/rules/testing.md` §0 · §1 · §2, `.claude/rules/non-obvious-patterns.md` 전체(특히 「sdd · 응답 키 추가」 · 「서버 · 화면」)
- `desk/board.py` — `read_card` · `list_cards` · `_read_request` · `build_card_detail`
- `page/server.py` — `build_board_card`
- `tests/test_desk_server_board_get.py`의 `통합_GET_board_card` · `tests/test_desk_board_view.py`의 상세 응답 테스트

## 배경 (step 11 첫 측정에서 나온 어긋남)

`GET /board`(목록)는 `list_cards`가 요청 파일의 `at`을 합쳐 `requested_at`을 주는데, `GET /board/card`(상세)는 `read_card`를 그대로 써서 `requested_at`이 항상 null이고 `elapsed_days`도 null이다. 화면의 세부 패널은 이 값으로 「요청」 줄 · [요청 취소] · [작업 시작] 표시를 정하므로, 요청됨 카드 패널에서 「요청」이 없음으로 나오고 [요청 취소]에 닿을 수 없다. `POST /board/cancel` 자체는 정상이다.

## 작업

러너가 이 step을 테스트 먼저 → 구현으로 한 호출에서 돌린다(`tdd: true`). 테스트만 담은 커밋이 먼저 있어야 하고, 그 커밋 뒤 테스트 파일을 고치면 러너가 되돌린다. 만들거나 고치는 파일은 **`page/server.py`의 `build_board_card`, (필요하면) `desk/board.py`, 테스트 파일**뿐이다.

- 상세 응답이 요청 파일의 시각을 `requested_at`으로 주고, 요청 시각이 있는 예정·진행 카드의 `elapsed_days`가 목록(`GET /board`)과 같은 값이 된다. 요청 파일이 없으면 둘 다 null. 요청 파일이 깨졌으면 목록과 같은 방식으로 다룬다(`list_cards`의 `request_broken` 처리를 확인하고 그대로 따른다)
- 요청 시각을 합치는 일은 `board` 모듈 안에서 한 곳으로 한다. 서버가 `board._read_request`(비공개)를 직접 부르지 않는다. 기존 `read_card`는 이동·삭제 등 쓰기 경로도 쓰므로 반환 모양을 바꾸지 않는다(새 공개 함수를 더하거나 `build_board_card` 쪽에서 합치는 공개 함수를 쓴다)
- 응답에 새 키를 더하지 않는다(`requested_at` · `elapsed_days`는 이미 `build_card_detail`의 키다). 그래서 응답 키 집합을 비교하는 기존 테스트가 깨지지 않는다 — 시작 전 `grep -rn "board/card" tests/`로 상세 응답을 비교하는 기존 테스트를 확인하고, 수정이 필요하면 **RED 커밋에 넣는다**(GREEN에서 고치면 러너가 되돌린다)
- `/nav-counts` · 화면(`page/index.html`)은 고치지 않는다. 화면은 이미 이 값을 읽는다

## Acceptance Criteria

- `.claude/harness.json`의 `verify.test`(`python3 -m unittest discover -s tests`) 통과. `typecheck` · `lint` · `build`는 이 레포에 없다(비어 있다)
- 새 테스트 단언: 요청 파일이 있는 예정 카드의 상세 응답 `requested_at`이 요청 시각과 같다 · 같은 카드의 `elapsed_days`가 목록 응답과 같다 · 요청이 없는 카드는 둘 다 null · 요청 파일이 깨진 카드는 목록과 같은 결과다 · 진행 카드(요청 뒤 시작)의 `elapsed_days`가 목록과 같다 · 응답에 파일 경로가 안 실린다
- 엣지 5축: 빈 값(요청 없음) · 비정상 입력(깨진 요청 파일) · 실패 경로(없는 카드 404 그대로) · 상태 전이(예정→진행 뒤 값) · 동시성(읽기만 하고 요청 파일을 바꾸지 않음을 단언)

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
- `page/index.html` · `/nav-counts`는 고치지 않는다
