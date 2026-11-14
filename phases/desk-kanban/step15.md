# Step 15: board-integration-recheck

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-kanban-2026-11-14/{PRD,ARCHITECTURE}.md`, `.claude/design/brief-kanban.md`
- `.claude/rules/non-obvious-patterns.md` — 「서버 · 화면」 · 「화면 · 서버 집계」 · 「PR · 스크린샷」
- `phases/desk-kanban/step12.md` — 같은 방식의 앞선 측정(가짜 `DESK_HOME` · `DESK_CONFIG` · `repo-a`/`repo-b` · `example.com` 링크 · 서버 기동 방법). 이번에도 그 방식을 그대로 쓴다
- `page/server.py`의 서버 기동 방식(`DESK_HOME` · `DESK_CONFIG` · `DESK_PORT`), `.claude/design/canvas/project/Kanban4States.dc.html` · `Kanban5Filters.dc.html`(비교 기준)

## 작업

`kind: "measure"` — **코드를 바꾸지 않고** 가짜 데이터로 서버를 띄워 step 13·14의 수정을 화면에서 확인하고 결과만 `summary`에 남긴다. 변경 0이 정상이다(대신 summary에 실행한 명령(백틱)과 결과를 적는다). 데이터는 전부 지어낸 값, 사람 이름 · vault 경로 금지, 실제 `DESK_HOME`(Finn의 홈)은 건드리지 않는다. 브라우저는 새 탭을 쓰고 끝나면 닫는다.

1. 칸반 카드 하나를 열었을 때 패널에 **빈 노란 줄이 없는지**(변경 안내 줄이 숨어 있는지). 카드를 다른 값으로 바꾸는 상황에서는 줄이 나오는지
2. 링크 저장 칸에서 Enter를 빠르게 두 번 눌러 **링크가 하나만 생기는지**(링크 파일의 항목 수와 서버로 간 POST 수로 확인)
3. 새 카드 모달: 빈 상태에서 [추가] 비활성 + 「비어 있는 칸: 레포 · 제목」, 제목만 채우면 「레포」만, 둘 다 채우면 활성
4. 기간 팝오버: [오늘] [지난 7일] [이번 달] [지우기] 각각의 입력값과 `GET /board`의 `from`·`to` 쿼리, 건수가 맞는지(`curl`로 같은 쿼리 응답과 나란히)
5. 보관 보기: 「보관한 카드 N」(N = 응답 값)과 진행에서 보관한 카드의 「진행에서 보관」, 되살리기
6. 링크 파일을 일부러 깨뜨린 카드(예: 항목에서 `url` 삭제)에서 링크 추가·수정·삭제가 화면에 오류 문구를 보이고 **파일이 그대로인지**(해시나 내용 비교)
7. 설정에 `my..repo` 같은 이름의 가짜 레포를 넣어도 칸반이 열리고 다른 레포 카드는 보이며 「읽지 못한 카드」 줄이 나오는지
8. 완료 열에 카드를 8개 이상 두고 **전부 보이고 열 안에서 스크롤**되는지(「더 보기」 없음)
9. `python3 -m unittest discover -s tests` 전체 통과
10. 확인하지 못한 것은 통과로 적지 않고 `확인필요 — 미실행: 이유`로 적는다

summary 형식: `` `실행한 명령` 결과 `` 를 항목마다 한 줄. 끝나면 서버를 끄고 임시 폴더를 지운다.

## Acceptance Criteria

- 변경 파일 0(코드 · 테스트 · 문서 모두). `git status --short`가 비어 있다
- `summary`에 실행한 명령(백틱)과 결과가 있다
- `python3 -m unittest discover -s tests` 통과

## 검증 절차

1. 위 작업 1~9의 항목마다 명령과 결과를 summary에 적었는지 센다
2. 결과를 `phases/desk-kanban/index.json`의 이 step에 기록: 성공 → `completed` + `summary` / 실패 → `error` + `error_message`(어느 항목이 어긋났는지) / 차단 → `blocked`

### 🔴 CRITICAL (CLAUDE.md 그대로)

- 사람 이름 · vault 원문 · 세션 대화 원문을 레포와 상태 파일에 넣지 않는다. 픽스처는 지어낸 레포 · 카드 · `example.com` 링크다
- 훅은 모델 토큰을 쓰지 않는다 — 이 phase는 훅을 건드리지 않는다
- hook 우회 금지 · desk는 프로세스를 실행하지 않고 URL을 열지 않는다
