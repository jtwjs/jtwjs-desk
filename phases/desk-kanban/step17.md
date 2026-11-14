# Step 17: board-ui-review2-fixes

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-kanban-2026-11-14/{PRD,ARCHITECTURE,ADR}.md`, `.claude/design/brief-kanban.md`
- `.claude/rules/testing.md` §0, `.claude/rules/non-obvious-patterns.md` 전체 — 특히 「서버 · 화면」·「화면 · 서버 집계」
- `page/index.html` — `boardPost`(약 3335행) · `BOARD_REFS_BROKEN`(약 3512행) · `saveRef`(약 3519행) · 링크 삭제 토스트(약 3495행) · 패널 링크 영역(`renderBoardLinks`, 약 3575~3620행) · 「보관한 카드 N」(`d.archTitle`, 약 3748행). 줄 번호는 어긋났을 수 있으니 이름으로 찾는다
- step 16이 끝난 서버: 링크 쓰기가 깨진 링크 파일에 409 `{"error":"refs broken"}`, 링크 5개 초과는 409 `{"error":"conflict"}`. 카드 상세 응답에 `refs_broken`(bool)이 있다

## 작업

`tdd: false`, 사유: 화면 파일(`page/index.html`) 변경이라 `.claude/rules/testing.md` §0 면제 표에 해당한다. 리뷰 2회차 🟡1과 🟢1·🟢2의 화면 몫이다.

1. **409를 두 가지로 가른다.** `boardPost`가 콜백에 응답 본문의 `error` 값도 넘긴다(본문이 없거나 JSON이 아니면 빈 값, 기존 호출부는 첫 인자만 써도 동작해야 한다). 링크 추가·수정·삭제의 409에서 `error === "refs broken"`일 때만 `BOARD_REFS_BROKEN` 문구를 쓴다. 그 외 409는 추가이면 「링크는 5개까지 붙일 수 있어요」, 수정이면 「이 링크를 바꾸지 못했어요」, 삭제 토스트는 「링크를 지우지 못했어요 · 이름」으로 쓴다
2. **깨진 링크 파일을 패널이 미리 알린다.** 카드 상세의 `refs_broken`이 true면 링크 영역에 「붙인 링크가 없어요」 대신 「링크 파일이 깨져 있어요. 홈 폴더 board/ 아래 refs 파일을 고치거나 지워 주세요」를 보이고, 링크 추가 버튼·폼은 숨긴다
3. **「보관한 카드 N」을 필터에 맞춘다.** 열 머리가 필터가 걸리면 `걸린 수 / 전체 수`를 보이는 것과 같은 규칙으로, 필터가 걸린 보관 보기 제목은 「보관한 카드 걸린 수 / 전체 수」로 한다(전체 수는 열별 `total`의 합). 필터가 없으면 지금처럼 N만

CRITICAL(`CLAUDE.md` 그대로): innerHTML 계열을 쓰지 않는다(기존처럼 `el()`·`textContent`). 사람 이름 · vault 원문을 넣지 않는다. 훅·서버·`desk/`는 건드리지 않는다.

## Acceptance Criteria

- `python3 -m unittest discover -s tests` 통과(`typecheck` · `lint` · `build`는 이 레포에 없다)
- HTML 안 스크립트 구문 검사 통과(`node --check`로 추출한 스크립트)
- 화면 확인은 이 step이 아니라 리뷰 3회차에서 가짜 데이터 서버로 한다 — summary에 `확인필요 — 미실행: 화면은 리뷰 3회차에서`를 적는다

## 검증 절차

1. 위 AC 명령을 실제 실행한다
2. `.claude/design/brief-kanban.md`·PRD에 어긋나는 문구가 없는지 확인한다(깨진 링크 문구는 PRD 「남은 것 · 확인 필요」 줄 기준)
3. `phases/desk-kanban/index.json`의 이 step에 기록: 성공 → `completed` + `summary` / 실패 → `error` + `error_message` / 차단 → `blocked` + `blocked_reason`

## 금지사항

- hook 우회(`--no-verify`) 금지 · 요청 범위 밖 수정 금지 · 테스트 파일 수정 금지
- `page/server.py` · `desk/` · 훅 · `.claude/design/` 수정 금지
- 쌓기만 하는 기록(회고 · 지난 설계 · `phases/*/` 다른 step)은 고치지 않는다
