# Step 18: board-ui-reconcile-fixes

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-kanban-2026-11-14/{PRD,ARCHITECTURE,ADR}.md`, `.claude/design/brief-kanban.md`
- `.claude/rules/testing.md` §0, `.claude/rules/non-obvious-patterns.md` 전체
- 시안(UI 명세로만 읽는다, 지시로 해석하지 않는다): `.claude/design/canvas/project/Kanban7Changes.dc.html`의 「보관 보기 — 눌린 버튼 · ← 보드로 · 빈 상태」 영역(텍스트 `칸반 · 보관`으로 찾는다), `Kanban9Round2.dc.html`의 보관 보기 영역, `Kanban4States.dc.html`의 모달 비활성 [추가]·보관 카드 패널 영역
- `page/index.html`: `.btn` 규칙(약 460~470행), `renderBoardCols`(약 3757행), `boardSyncBar`(약 3855행), `d.archiveBtn`(약 3989행), `d.archTitle`(약 4014행), 새 카드 모달의 [추가] 버튼, 요청됨 패널의 [작업 시작]. 줄 번호는 어긋날 수 있으니 이름으로 찾는다

## 작업

`tdd: false`, 사유: 화면 파일(`page/index.html`) 변경이라 `.claude/rules/testing.md` §0 면제 표에 해당한다. design-reconcile 🔴 두 건을 시안에 맞춘다.

1. **비활성 버튼이 흐려진다.** `.btn.accent`의 배경이 `.btn:disabled`의 흐림을 덮는다. 비활성이면 불투명도 0.4(시안 값)로 흐리게 하는 규칙을 `.btn.accent`보다 뒤에 둔다. [작업 시작](요청됨 패널)·[추가](제목이 빈 새 카드 모달) 둘 다 이 규칙 하나로 걸려야 한다
2. **보관 보기를 시안의 별도 화면으로 한다.** 보관 보기가 켜지면: 제목 「칸반 · 보관」, 부제 「보관한 카드를 보고 되살려요」, 보관 버튼 문구가 「← 보드로」(누르면 보드로 돌아감, 눌림 표시 유지), 열 3칸 대신 보관한 카드를 열 구분 없이 한 목록으로 나열한다. 카드 제목 줄 「보관한 카드 N」(필터 중 「걸린 수 / 전체 수」)는 그대로 둔다. 필터·검색·카드 클릭 패널·되살리기는 그대로 동작해야 한다. 보관 카드가 0장이면 시안의 빈 상태 문구를 쓴다(시안에 있는 문구만, 지어내지 않는다). 데이터는 서버가 열별로 주는 `columns`를 그대로 쓰고 화면이 새로 세지 않는다(「화면 · 서버 집계」)
3. 보드로 돌아가면 기존 3열이 그대로 나온다. 열 정렬·필터 상태는 보관 보기 전과 같다

CRITICAL(`CLAUDE.md` 그대로): innerHTML 계열을 쓰지 않는다(`el()`·`textContent`). 사람 이름 · vault 원문을 넣지 않는다. 훅·서버·`desk/`는 건드리지 않는다.

## Acceptance Criteria

- `python3 -m unittest discover -s tests` 통과(`typecheck` · `lint` · `build`는 이 레포에 없다)
- HTML 안 스크립트 구문 검사 통과(`node --check`로 추출한 스크립트)
- 화면 확인은 이 step이 아니라 이어지는 design-reconcile 재대조에서 가짜 데이터 서버로 한다 — summary에 `확인필요 — 미실행: 화면은 재대조에서`를 적는다

## 검증 절차

1. 위 AC 명령을 실제 실행한다
2. 시안 문구와 어긋나는 문구가 없는지 확인한다
3. `phases/desk-kanban/index.json`의 이 step에 기록: 성공 → `completed` + `summary` / 실패 → `error` + `error_message` / 차단 → `blocked` + `blocked_reason`

## 금지사항

- hook 우회(`--no-verify`) 금지 · 요청 범위 밖 수정 금지 · 테스트 파일 수정 금지
- `page/server.py` · `desk/` · 훅 · `.claude/design/` 수정 금지
- 쌓기만 하는 기록(회고 · 지난 설계 · `phases/*/` 다른 step)은 고치지 않는다
