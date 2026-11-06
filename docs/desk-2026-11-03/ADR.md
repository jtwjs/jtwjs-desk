# ADR: 지휘 책상

## ADR-001 상태 · 판정을 JSON 파일 여러 개로

- 상태: 제안
- 맥락: 훅은 여러 세션에서 동시에 돈다. 판정은 지휘(질문 · 반영)와 페이지 서버(선택)가 같이 쓴다. 판정은 재부팅 뒤에도 남아야 한다
- 결정: 세션 상태는 `/tmp/jtwjs-desk/sessions/<session_id>.json`(훅이 덮어씀). 판정은 `~/.jtwjs-desk/inbox/<레포>/<id>.json` · `<id>.pick.json` · `<id>.applied.json`. 레포 키는 세션 cwd의 git 최상위 폴더 이름. 쓰기는 전부 임시 파일 + `os.replace`
- 결정 주체: Finn (deadhd 방식). 경로 둘로 나누기와 파일 셋으로 나누기는 AI 추천 수용
- 대안: SQLite 한 파일(동시 쓰기 잠금 대기, 훅이 느려짐) · 판정도 /tmp + ADR에서 복원(11-01 이후 bv-admin ADR 2개 vs 판정 126건이라 복원 불가)
- 결과: 잠금이 없고 파일을 열어 바로 읽는다. 대가는 목록 · 필터를 폴더 훑기로 하는 것과 파일 수 증가(정리 규칙으로 막는다)

## ADR-002 훅 하나 · 이벤트별 상태 · stdout 0

- 상태: 제안
- 맥락: 멈춤을 판정하려면 마지막 활동 시각이 필요하다. 훅이 모델 컨텍스트에 글을 넣으면 토큰 0 원칙이 깨진다
- 결정: `hooks/desk_hook.py <이벤트>` 하나를 이벤트마다 등록한다

  | 이벤트 | 상태 | 그 밖 |
  |---|---|---|
  | SessionStart | 입력 대기 | 페이지 서버 확인 · 없으면 띄움(ADR-003) |
  | UserPromptSubmit | 작업 중 | |
  | PostToolUse | 작업 중 | 마지막 시각만 갱신 |
  | Notification(permission_prompt) | 승인 대기 | ntfy 알림(ADR-005) |
  | Notification(idle_prompt) | 입력 대기 | |
  | PreCompact | 작업 중 | |
  | Stop | 입력 대기 | |
  | SessionEnd | (파일 삭제) | |

  Notification은 입력 JSON의 `notification_type`으로 가른다. 이벤트 이름 · 매처 값은 공식 문서 hooks 페이지에서 확인했다(11-06). SessionStart · UserPromptSubmit은 exit 0의 stdout이 모델 컨텍스트에 들어간다고 문서에 적혀 있어서, stdout · stderr에 아무것도 쓰지 않고 항상 exit 0. 예외가 나도 세션을 막지 않는다(오류는 `~/.jtwjs-desk/hook-errors.log`에 한 줄)
- 결정 주체: Finn (deadhd와 같은 시점). 상태 표와 stdout 0은 AI 추천 수용
- 대안: 턴 경계만(긴 턴을 멈춤과 구분 못함)
- 결과: 도구 호출마다 Python이 한 번 뜬다(부하 낮을 때 기동 0.01~0.02초, 11-03 실측 5회). 「완료」 상태는 두지 않는다. 끝난 세션은 파일이 사라진다

## ADR-003 페이지 서버: 훅이 띄우고 포트가 단일 실행을 보장

- 상태: 제안
- 맥락: 플러그인 경로는 버전마다 바뀐다(`.../<플러그인>/<버전>/`). launchd가 고정 경로를 가리키면 업데이트 때 깨진다
- 결정: 플러그인 버전은 `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json`의 `version`에서 읽는다(버전을 주는 환경 변수는 문서에 없다, 11-06 확인). SessionStart 훅이 `GET /version`으로 묻는다. 응답이 없으면 서버를 떼어 띄우고(`start_new_session`), 버전이 플러그인 버전과 다르면 `POST /shutdown`(토큰 필요) 뒤 다시 띄운다. 서버는 127.0.0.1의 고정 포트를 bind하고, bind가 실패하면 이미 떠 있는 것으로 보고 바로 끝난다. 포트는 기본 47615, `DESK_PORT`로 바꾼다. 훅의 확인 대기는 0.3초 상한
- 결정 주체: AI 추천 수용
- 대안: launchd 상시(업데이트 때 옛 경로) · 지휘 세션만 띄움(지휘가 없으면 트랙도 안 보임)
- 결과: 설치 단계가 없다. 세션 둘이 동시에 띄워도 bind에 성공한 하나만 남는다. 대가는 맥을 켜고 첫 세션 전에는 페이지가 없다는 것

## ADR-004 저장 요청 보호: 페이지 토큰 + Origin + Host

- 상태: 제안
- 맥락: 127.0.0.1 서버에도 브라우저에 열린 다른 사이트가 요청을 보낼 수 있다(CSRF · DNS 리바인딩)
- 결정: 서버는 뜰 때 무작위 토큰을 만들어 `~/.jtwjs-desk/server.json`(권한 0600: 포트 · pid · 버전 · 토큰)에 쓰고, 자기가 내주는 `index.html`에 심는다. POST는 ① `X-Desk-Token` 일치 ② `Origin`이 `http://127.0.0.1:<포트>` ③ `Host`가 `127.0.0.1:<포트>` 셋 다 맞을 때만 받는다. GET도 ③을 본다. CORS 헤더는 내지 않는다
- 결정 주체: AI 추천 수용
- 대안: 보호 없음(다른 탭이 판정을 저장할 수 있음) · 비밀번호 입력(혼자 쓰는 도구에 매번 입력)
- 결과: 다른 사이트는 토큰을 읽을 수 없어 저장하지 못한다. 서버를 다시 띄우면 열린 탭은 새로고침해야 한다

## ADR-005 ntfy 알림은 따로 떼어, 레포 · 상태만

- 상태: 제안
- 맥락: ntfy.sh는 공개 서버라 토픽을 아는 누구나 본문을 읽을 수 있다. 훅은 네트워크를 기다리면 안 된다
- 결정: 토픽은 `~/.config/jtwjs-desk/ntfy-topic` 파일(없으면 알림 없음). routine 토픽과 따로 둔다. 본문은 `<레포> · <브랜치> · 승인 대기`만. 전송은 떼어 낸 자식 프로세스가 `urllib`로 5초 상한
- 결정 주체: AI 추천 수용 (PRD 남은 ⚠️ ntfy 토픽)
- 대안: routine 토픽 같이 쓰기(루틴 알림과 섞임)
- 결과: 대화 내용은 밖으로 나가지 않는다. 대가는 토픽 파일을 손으로 한 번 만드는 것

## ADR-006 지휘는 desk 스크립트로만 판정을 오간다

- 상태: 제안
- 맥락: MCP로 아티팩트 db를 읽으면 126건이 100건씩 두 번 컨텍스트에 들어왔다. 판정 형식이 바뀌면 지휘 절차도 같이 바뀌어야 한다
- 결정: `scripts/desk.py`
  - `ask <레포> <파일|->`: 형식 검증 후 질문 파일 생성(createdAt 자동, 같은 id면 거절)
  - `picks --new [--repo <레포>] [--since <시각>]`: 반영 파일이 없는 선택만 한 줄 JSON으로. 다시 고른 선택은 `at`이 바뀌어 `--since`에 다시 걸린다. 반영 파일이 있는 판정에 대한 저장 요청은 서버가 409로 거절한다(PRD desk-repick)
  - `applied <레포> <id> [--issue <URL>] [--follow-up <#N>...]`
  - `prune [--days N]`: 반영 뒤 N일 지난 판정 삭제(기본값은 PLAN에서)

  질문 형식(옛 대기함 schema v2에서 아티팩트 전용 칸을 뺀 것): `id · order · issue · area · question · why · options[{key,label,recommended}] · see[] · aiDecided[{key,label}] · premiseOpen`. 선택 형식: `at · choice|"custom" · customText · note · noteKind(reason|scope|new) · aiRejected[key]`
- 결정 주체: AI 추천 수용
- 대안: 지휘가 파일을 직접 Read · Write(형식 검증이 없고 전체를 읽음)
- 결과: 지휘가 읽는 것은 새 선택뿐이다. 판정 절차는 `skills/decision-inbox/SKILL.md`에 두고, 하네스 지휘 스킬은 후속에서 이 스킬을 가리키는 한 줄만 갖는다

## ADR-007 설치는 jtwjs-plugins 마켓플레이스

- 상태: 제안
- 맥락: 마켓플레이스 `jtwjs-plugins`의 정본은 claude-harness 레포의 `.claude-plugin/marketplace.json`이다(11-06 확인, `source: ./` 하나)
- 결정: 개발 중에는 `claude --plugin-dir /Users/fastview/fastview/jtwjs-desk`로 붙여 본다. 릴리스 때 marketplace.json에 `jtwjs-desk`(GitHub 소스) 항목을 하네스 PR로 더한다
- 결정 주체: AI 추천 수용
- 대안: 이 레포에 마켓플레이스를 하나 더(마켓플레이스 둘을 관리)
- 결과: 설치 방식은 하네스와 같다. 대가는 릴리스 때 하네스 레포에 한 줄 PR이 생기는 것
