# Step 3: board-view-response

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-kanban-2026-11-14/{PRD,ARCHITECTURE,ADR}.md` — PRD 「수용 조건」 표가 이 step의 테스트 입력이다. ARCHITECTURE 「엔드포인트」·「상태 규약」·「경계」가 계약이다. ADR 값(sort 파라미터 모양 · 열 이동 방향 · 시작 요청 파일 분리)은 ADR 제목으로 찾아 읽고 이 문서에 복사하지 않는다
- `.claude/rules/testing.md` §0 · §1 · §2, `.claude/rules/non-obvious-patterns.md` 전체(항상 로드되는 함정 목록)
- `desk/board.py`(step 1 · 2 산출물) · `desk/config.py`(`load_config` 결과의 `repos`)
- `page/server.py`의 `list_phase_indexes`(깨진 JSON은 건너뜀) · `_today()` — 이 step은 server.py를 고치지 않고 **순수 조립 함수만** `desk/board.py`에 둔다(phases 읽기 결과는 인자로 받는다)

## 작업

러너가 이 step을 테스트 먼저 → 구현으로 한 호출에서 돌린다(`tdd: true`). 테스트만 담은 커밋이 먼저 있어야 하고, 그 커밋 뒤 테스트 파일을 고치면 러너가 되돌린다. **`desk/board.py`(응답 조립 함수 추가)와 `tests/test_desk_board_view.py`(신규)만** 고친다. 엔드포인트는 step 4.

`build_view(cards_by_repo, phases_by_repo, today, now, query) -> dict` (파일 읽기 없음 · 순수):
- 입력: 레포별 카드 목록(step 2의 `list_cards` 결과, 각 카드에 `requested_at`), 레포별 `{task: index.json dict}`, `today`(date), `query`(`repo`, `from`, `to`, `sort_planned`, `sort_doing`, `sort_done`, `q`, `archived` — 값은 이미 문자열로 파싱된 dict)
- 입력 검증(예외 `BadQuery` → 서버가 400): 모르는 `repo`, 날짜 형식(`YYYY-MM-DD`) 아님, `from` > `to`, `sort_*`가 `new`·`old` 아님. 파라미터 모양은 ADR 「sort 쿼리 모양」을 따르고 기본값도 그 ADR이 정한다
- 열 3개로 묶는다. 보관 카드는 `archived`가 아니면 빠지고, `archived`이면 보관 카드만 나온다
- 기간 필터(`from`·`to`, 한쪽만 가능, 경계 날짜 포함)는 열별 기준일로 건다: 예정 = `created_at`, 진행 = `doing_at`, 완료 = `done_at`
- `q`: 제목만 부분 일치 · 대소문자 무시, 비거나 공백뿐이면 필터 없음, 다른 필터와 AND
- 정렬: 열마다 기준일(위와 같음)로 `sort_*`에 따라. 「진행」은 `pr_at`이 있는 카드가 항상 맨 위이고 그 안과 나머지는 정렬을 따른다
- 열마다 `count`(필터 적용 뒤)와 `total`(필터 적용 전, 보관 여부 기준은 같음)을 준다. **카드 목록은 서버가 자르지 않는다**(자르면 `total`과 어긋난다 — non-obvious-patterns 「화면 · 서버 집계」)
- 카드마다: `id` · `repo` · `title` · `note` · `column` · `badge`(`"requested"` — 예정이고 요청 파일이 있을 때만, 없으면 null) · `pr_waiting`(`pr_at` 있고 `doing`) · `elapsed_days`(`doing` 카드만, step 1 함수) · `progress` · `candidate`(step 1 `candidate_mark`) · `connection`(step 1 `connection_state`) · 날짜 필드 · `task` · `archived`. `refs`는 이 응답에 넣지 않는다(상세 응답에서만)
- 최상위: `columns`(planned/doing/done 각각 `cards`·`count`·`total`) · `broken`(깨진 카드 · 요청 · 링크 파일 수 합) · `archived`(요청한 값). phases를 못 읽은 레포는 진행도 · 후보 표식만 비운다(예외로 터지지 않는다)

`build_card_detail(card, refs, phase_index, today) -> dict`: 메모 · 날짜 전부 · `refs`(id · name · url) · task가 있고 phase_index가 있으면 `steps`(번호 · 이름 · status · summary)와 `phase_summary`. task가 없거나 phases가 없으면 `steps`는 빈 목록이다.

## Acceptance Criteria

- `.claude/harness.json`의 `verify.test`(`python3 -m unittest discover -s tests`) 통과. `typecheck` · `lint` · `build`는 이 레포에 없다(비어 있다)
- `tests/test_desk_board_view.py` 단언: 열 3개 묶음 · 보관 카드가 기본에서 빠지고 `archived`에서만 나옴 · `repo` 필터 · `from`/`to` 열별 기준일(경계 포함, 한쪽만, 예정 만든 날 ≠ 진행 시작일로 갈림) · `from`>`to`/잘못된 날짜/모르는 `repo`/모르는 `sort`가 `BadQuery` · `q`가 제목에만 걸리고 메모 글자로는 안 걸림 · 공백뿐 `q`는 필터 없음 · `q`와 `repo`·기간이 AND · 열마다 `count`와 `total`이 다른 경우(필터가 일부를 뺄 때) · 카드 목록이 자르지 않음(7장 넣으면 7장 그대로) · 기본 정렬(예정·진행 오래된순, 완료 최신순)과 `sort_*` 뒤집기 · 「진행」 PR 대기 카드가 어느 정렬에서도 맨 위 · 요청 배지가 예정 카드에만 · 경과 일수 · 후보 표식 · 설계 중 · 연결 끊김 · 진행도 · phases 없음에서도 터지지 않음 · `broken` 합 · 상세에 `refs`와 step summary, task 없으면 `steps` 빔
- 엣지 5축: 빈 값(카드 0장 · 열 비어 있음) · 비정상 입력(`BadQuery` 4종) · 실패 경로(phases 없음 · 깨진 카드) · 상태 전이(보관 → 되살림 후 목록 변화) · 동시성(해당 없음: 순수 함수)

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
