# Step 11: board-integration-check

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-kanban-2026-11-14/PRD.md` 「수용 조건」 표(특히 「화면 연결」 · 「메뉴 배지 없음」) · `docs/desk-kanban-2026-11-14/ARCHITECTURE.md`
- `.claude/rules/non-obvious-patterns.md` — 「서버 · 화면」 · 「화면 · 서버 집계」 · 「PR · 스크린샷」
- `page/server.py`의 서버 기동 방식(`DESK_HOME` · `DESK_CONFIG` 환경 변수, 포트 인자는 파일에서 확인) · `tests/test_desk_redesign_integration.py`

## 작업

`kind: "measure"` — **코드를 바꾸지 않고** 가짜 데이터로 서버를 띄워 확인하고 결과만 `summary`에 남긴다. 파일을 고치지 않으므로 변경 0이 정상이다(대신 `summary`에 실행한 명령(백틱)과 결과를 적는다).

1. 스크래치패드(작업 디렉터리 밖 임시 폴더)에 가짜 `DESK_HOME` · `DESK_CONFIG` · 지어낸 레포 2개(`repo-a` · `repo-b`, 각각 `phases/demo/index.json` 포함: 일부 step만 completed인 것 / 전부 completed인 것)를 만들고 카드 파일을 `scripts/desk.py board ...`와 `POST /board/add`(토큰은 서버가 내는 값, 페이지 소스에서 읽음)로 채운다. 데이터는 전부 지어낸 값(제목 · 링크 `https://example.com/...`). 사람 이름 · vault 경로 금지
2. 서버를 띄우고 브라우저(`claude-in-chrome` 도구 또는 `curl`)로 다음을 **응답 값과 화면 값을 나란히 대조**한다: 열 3개와 건수(`count` / `total`) · 요청됨 배지 · 경과 일수 · 진행도 막대 · 후보 표식 · 설계 중 · 연결 끊김 · PR 대기 표시(「진행」 맨 위) · 보관 보기와 되살리기 · 제목 검색과 필터 요약 줄 · 열별 정렬 토글 · 세부 패널(step summary · 링크 텍스트, URL 비노출, 새 탭 · `noopener noreferrer`) · 링크 추가 · 수정 · 5번째 뒤 안내 · 링크 삭제 5초 되돌리기(되돌리면 서버에 안 감) · 카드 삭제 5초 되돌리기 · 같은 제목 409 모달 문구 · 요청 취소
3. 다른 화면(리뷰 · 3역량 등)의 레포 셀렉트가 고른 레포만 보이게 하는지 한 곳 이상 확인한다
4. `GET /nav-counts` 응답 키가 이 phase 이전과 같은지 확인한다(`{"judge","review","routine","trends",...}` 기존 집합 그대로, `board` 키 없음)
5. `python3 -m unittest discover -s tests` 전체 통과를 summary에 적는다
6. 확인하지 못한 것은 통과로 적지 않고 `확인필요 — 미실행: 이유`로 적는다

summary 형식: `` `실행한 명령` 결과 `` 를 항목마다 한 줄. 기록한 뒤 서버를 끄고 임시 폴더를 지운다. 실제 `DESK_HOME`(Finn의 홈)은 건드리지 않는다.

## Acceptance Criteria

- 변경 파일 0(코드 · 테스트 · 문서 모두). `git status --short`가 비어 있다
- `summary`에 실행한 명령(백틱)과 결과가 있다
- `python3 -m unittest discover -s tests` 통과(`typecheck` · `lint` · `build`는 이 레포에 없다)

## 검증 절차

1. 위 작업 2~5의 항목마다 명령과 결과를 summary에 적었는지 센다.
2. 결과를 `phases/desk-kanban/index.json`의 이 step에 기록: 성공 → `completed` + `summary` / 실패 → `error` + `error_message`(어느 항목이 응답과 화면이 달랐는지) / 차단 → `blocked`.

### 🔴 CRITICAL (CLAUDE.md 그대로)

- 사람 이름 · vault 원문 · 세션 대화 원문을 레포와 상태 파일에 넣지 않는다. 픽스처는 지어낸 레포 · 카드 · `example.com` 링크다
- 훅은 모델 토큰을 쓰지 않는다 — 이 phase는 훅을 건드리지 않는다
- hook 우회 금지 (`--no-verify` 등)
- desk는 프로세스를 실행하지 않는다(서브프로세스 호출 없음) · URL을 열어 보거나 가져오지 않는다(HTTP 요청 없음). 쓰는 곳은 `board/<레포>/` 아래 카드 · 요청 · 링크 파일뿐이다

## 금지사항

- hook 우회(`--no-verify`) · 자동 생성물 직접 수정 · 요청 범위 밖 수정 · **테스트 파일 수정**(구현 단계에서) 금지
- 쌓기만 하는 기록(`docs/`의 지난 설계 · ADR 본문 · `phases/*/`)은 고치지 않는다. 이 step이 맡지 않은 파일은 고치지 않는다
- 이 step은 어떤 파일도 고치지 않는다. 어긋남을 찾으면 고치지 말고 `error`로 보고한다(고치는 일은 수정 step으로 따로 만든다)
