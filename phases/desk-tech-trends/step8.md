# Step 8: trends-verify

> `kind: "measure"` — 코드 변경 없이 실제 서버 + 브라우저로 처음부터 끝까지 지나가 보고, 본 것과 못 본 것을 `summary`에 남긴다. 구현 step에 섞지 않는다.

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-tech-trends-2026-11-12/PRD.md`(수용 조건 1~18) · `.claude/rules/non-obvious-patterns.md`(「서버 · 화면」)
- `phases/desk-tech-trends/step4.md` 「계약」(응답 필드) · `phases/desk-routine-inbox/step7.md`(앞 phase의 측정 step 모양)
- `page/server.py` · `page/index.html` · `.claude/design/canvas/project/Trends{1Today,2Unread,3States,4Bookmarks}.dc.html`

## 작업

이 step은 **파일을 고치지 않는다**(임시 가짜 데이터는 스크래치패드 아래에만 만들고 레포에 커밋하지 않는다).

1. 스크래치패드에 가짜 동향 파일(오늘 3건 + 지난 날 안 읽은 글 몇 건 + 1년 안에 흩어진 지난 글 + 깨진 줄 1개 + 제목에 `<script>` · 링크 `javascript:` 글 1건)과 빈 읽음 · 북마크 파일을 만들고, `DESK_HOME`/`DESK_CONFIG`를 그쪽으로 돌려 서버를 띄운다
2. `curl`로 `GET /trends` · `GET /nav-counts`를 보고 필드가 계약대로 오는지 확인한다(`summary`에 `curl` 명령과 확인한 키)
3. 브라우저(Claude in Chrome)로 「오늘」 · 「안 읽은 글」 · 「북마크」를 연다: 링크 클릭 → 읽음 · 잔디 칸 증가 · 배지 감소, 북마크 켬/끔, 칩 필터, `<script>` 글이 코드로 실행되지 않고 `javascript:` 링크가 안 열리는지, `trends_marks` / `trends_reads` / `trends_items` 각각을 비운 설정에서 이유 · 비활성이 뜨는지, 읽음 파일 경로를 디렉터리로 바꿔 쓰기 실패가 한 줄 에러로 뜨고 링크는 열리는지
4. 지난 날 글을 읽었을 때 오늘이 아니라 그 글의 날짜 칸이 오르는지 잔디 툴팁으로 확인한다
5. `python3 -m unittest discover -s tests`를 돌려 전체 통과를 확인한다
6. 뒷정리: 띄운 서버와 임시 파일을 내린다

## Acceptance Criteria

- `summary`에 실행한 명령(백틱)과 결과가 있다: 예 `` `python3 -m unittest discover -s tests` 통과 n개 ``, `` `curl -s http://127.0.0.1:<포트>/trends` `` 키 확인
- PRD 수용 조건 18개마다 `확인함(어떻게)` / `못 봄(이유)` 중 하나를 적는다. 못 본 것을 통과로 적지 않는다
- 새로 발견한 비명백한 함정이 있으면 한 줄 적는다(`.claude/rules/non-obvious-patterns.md` 반영은 REFLECT에서)
- 레포 파일 변경 0(`git status --short`가 비어 있거나 이 phase 산출물만)

## 검증 절차

1. 위 작업 1~6을 실제로 한다.
2. 결과를 `phases/desk-tech-trends/index.json`의 step 8에 기록: 성공 → `completed` + `summary`(백틱 명령 + 결과 + 수용 조건별 확인함/못 봄) / 실패 → `error` + `error_message` / 차단 → `blocked` + `blocked_reason`.

## 금지사항

- hook 우회(`--no-verify`) · 코드 · 설계 문서 수정 금지(이 step은 측정 전용)
- 사람 이름 · vault 원문 · 세션 대화 원문을 임시 데이터에 쓰지 않는다. 가짜 글과 `example.com`만 쓴다
