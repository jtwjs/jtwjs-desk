# Step 4: desk-server

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-2026-11-03/{PRD,ARCHITECTURE,ADR}.md` — 특히 ADR-003(서버 생애주기) · ADR-004(토큰+Origin+Host)
- `desk/paths.py`·`desk/atomic.py`·`desk/sort.py`(step 1 산출물)
- `~/dev/jtwjs/claude-harness/.claude-plugin/plugin.json`(형식 참고 — 이 레포에 없는 `name`·`version`·`author`·`description`·`keywords` 필드 구성을 그대로 본뜬다)
- `.claude/rules/testing.md` §0·§5

## 작업

### 1) `.claude-plugin/plugin.json` (이 레포에 아직 없다 — ADR-003의 버전 판정 전제)

`{"name": "jtwjs-desk", "description": "지휘 책상: 판정 대기함 + 트랙 페이지", "version": "0.1.0", "author": {"name": "jtwjs"}, "keywords": ["desk", "sdd", "track", "decision-inbox"]}` 형식(claude-harness와 같은 스키마). **버전은 `0.1.0`으로 시작** — 이후 변경은 이 step 범위 밖(릴리스 때 `release.sh` 같은 도구가 올린다, ADR-007 범위 밖).

### 2) `page/server.py` — Python 표준 라이브러리 `http.server`만 쓴다 (외부 패키지 금지)

**`page/`는 `desk/`만 import한다**(ARCHITECTURE 경계 — `hooks/`·`scripts/`를 import하지 않는다).

- `read_plugin_version() -> str`: `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json`(환경변수 없으면 이 파일 기준 상대 경로로 폴백 — 개발 중 `--plugin-dir` 없이 직접 실행할 때)의 `version`을 읽는다.
- `generate_token() -> str`: `secrets.token_hex(16)`.
- `write_server_meta(port: int, pid: int, version: str, token: str) -> None`: `desk.paths`의 `server.json`에 원자적으로 쓰고 `os.chmod(path, 0o600)`(ADR-004 "권한 0600").
- `bind_or_exit(port: int) -> socket.socket | None`: `127.0.0.1:port`에 bind 시도. `OSError`(포트 사용 중)면 **이미 떠 있는 것으로 보고 `None`을 반환**(ADR-003 "bind가 실패하면 이미 떠 있는 것으로 보고 바로 끝난다") — 호출부가 `None`이면 즉시 종료.
- 요청 핸들러(`http.server.BaseHTTPRequestHandler` 또는 `ThreadingHTTPServer`):
  - **공통**: 모든 응답에 CORS 헤더를 내지 않는다(ADR-004). `check_host(headers, port) -> bool`: `Host` 헤더가 정확히 `127.0.0.1:<port>`인지(순수 함수, 헤더 dict와 port를 인자로 받는다).
  - `GET /version` → `{"version": read_plugin_version()}`, 인증 없음(훅이 토큰을 모른 채 묻는다, ADR-003).
  - `GET /sessions` → `check_host` 통과 시 `desk.paths` 세션 디렉터리의 모든 `*.json`을 읽어 `desk.sort.sort_sessions(sessions, now=time.time())` 결과를 JSON으로. `check_host` 실패면 `403`.
  - `GET /judgments[?repo=<레포>]` → `check_host` 통과 시 inbox를 훑어 **레포별 카드 목록**(각 카드 = ask 내용 + 있으면 `pick` + 있으면 `applied`, 둘 다 없어도 카드는 보인다 — 반영된 것도 화면에 "반영됨"으로 보여야 하므로 반영 여부로 목록에서 빼지 않는다, PRD AC). `repo` 쿼리로 필터.
  - `POST /pick` → 바디 JSON(`repo · id · choice|customText · note · noteKind`). 순서대로 검사, 첫 실패에서 멈춘다:
    1. `X-Desk-Token` 헤더가 `server.json`의 토큰과 일치 — 아니면 `403`
    2. `Origin` 헤더가 정확히 `http://127.0.0.1:<port>` — 아니면 `403`
    3. `check_host` — 아니면 `403`
    4. 대상 `<repo>/<id>.json`(ask)이 없으면 `404`
    5. `<repo>/<id>.applied.json`이 **있으면 `409`**(반영된 판정은 잠긴다 — PRD `desk-repick`, ADR-004)
    6. `desk.validate.validate_pick`로 필드 검증 — 틀리면 `400` + 틀린 필드 목록
    7. 통과하면 `at=time.time()`을 더해 `<repo>/<id>.pick.json`에 원자적으로 쓴다(이미 있으면 덮어씀 — 반영 전 재선택 허용). `200`
  - `POST /shutdown` → `X-Desk-Token` 일치해야 함(아니면 `403`). 일치하면 응답 후 서버를 정지한다(ADR-003 "버전이 다르면 POST /shutdown 뒤 다시 띄운다").
  - `GET /` → `page/index.html`을 읽어, 그 안의 **리터럴 문자열 `__DESK_TOKEN__`을 실제 토큰으로 치환**해 응답한다(ADR-004 "자기가 내주는 index.html에 심는다"). **이 step은 그 자리표시자만 가진 최소 `page/index.html`을 만든다**(`<script>const DESK_TOKEN = "__DESK_TOKEN__";</script>` 한 줄 수준) — 실제 탭 UI는 step 5가 이 자리표시자를 보존한 채 채운다. 자리표시자 문자열을 바꾸면 step 5와 어긋난다.
- `serve_forever(port: int | None = None) -> None`: 포트(기본 47615, `DESK_PORT`로 재정의 — ADR-003)에 `bind_or_exit` → 실패면 `return`. 성공하면 토큰 생성 → `write_server_meta` → HTTP 서버 루프.

### 🔴 CRITICAL (CLAUDE.md에서 인용 — 이 step에 직결)

- 사람 이름·vault 원문·세션 대화 원문을 응답 JSON에 넣지 않는다 — `GET /judgments`·`GET /sessions`는 inbox·세션 파일에 있는 그대로를 돌려줄 뿐 추가 정보를 만들어내지 않는다.

## Acceptance Criteria

- `.claude/harness.json`의 `verify.test` 통과.
- 임시 포트로 서버를 띄운 통합 테스트(ARCHITECTURE 테스트 전략 "서버를 임시 포트로 띄워 GET/POST"): `GET /version`, `GET /sessions`(빈 상태 → `[]`), `POST /pick` 토큰 누락(`403`)·Origin 다름(`403`)·ask 없음(`404`)·정상(`200`)·반영된 id(`409`) 전부 확인.
- 포트 충돌 시나리오: 같은 포트로 두 번째 `bind_or_exit`를 호출하면 `None`(실제 소켓을 먼저 bind해 둔 채 테스트).

## 검증 절차

1. 위 AC 명령·시나리오 실행.
2. 아키텍처 체크리스트: `page/server.py`가 `hooks/`·`scripts/`를 import하지 않는가. 모든 응답에 CORS 헤더가 없는가(grep). `server.json` 권한이 `0600`인가.
3. 결과를 `phases/desk/index.json` step 4에 기록.

## 금지사항

- hook 우회 · 자동 생성물 직접 수정 · 요청 범위 밖 수정 · 테스트 파일 수정(구현 커밋에서) 금지.
- `hooks/`·`scripts/`를 import하지 않는다. `page/index.html`의 `__DESK_TOKEN__` 자리표시자 문자열을 다른 이름으로 바꾸지 않는다(step 5와 계약).
