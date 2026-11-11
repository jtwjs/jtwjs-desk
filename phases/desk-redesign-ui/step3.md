# Step 3: font-route

`tdd: true` — 허용 이름만 열고 나머지는 404인 경계는 보안 판정이라 RED 먼저.

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-2026-11-12/{PRD,ARCHITECTURE,ADR}.md`, `.claude/rules/testing.md` §0
- `page/server.py` — `do_GET`, `_send_html`/`_send_json` 형태, `check_host`, `_INDEX_HTML_PATH`
- `tests/test_desk_server.py` — `_ServerTestCase`, `_get_raw_host`
- `page/fonts/PretendardVariable.woff2`(step 2 산출물)

## 작업

`GET /fonts/PretendardVariable.woff2` 하나만 연다(ADR-016).

- 응답 `Content-Type: font/woff2`, 본문은 `page/fonts/PretendardVariable.woff2` 바이트, `check_host` 통과 필요(403)
- 허용은 **정확히 그 이름 하나**. `/fonts/` 아래 다른 이름 · `..` · 인코딩된 슬래시 · 디렉터리 요청은 404. 파일 경로를 요청 문자열로 조립하지 않는다(고정 경로 상수 하나만 읽는다)
- 파일이 없으면 404(조용히 500 아님)
- 캐시: `Cache-Control: max-age` 같은 새 정책을 만들지 않는다(기본 유지)
- 테스트 `tests/test_desk_server_font.py`: 200 + woff2 헤더 + 바이트 일치 · 다른 이름 404 · `..` 조작 404 · Host 다르면 403 · 파일 없으면 404(`patch`로 경로 상수 교체)

### 🔴 CRITICAL (`CLAUDE.md`에서 그대로)

- 사람 이름 · vault 원문 · 세션 대화 원문을 레포와 상태 파일에 넣지 않는다(화면 견본 문구도 일반 문구만)
- 훅은 모델 토큰을 쓰지 않는다. 이 phase는 `hooks/`를 건드리지 않는다
- 런타임은 Python 표준 라이브러리만. 외부 패키지를 들이지 않는다
- 응답 문자열은 `textContent`로만 DOM에 넣는다(저장형 XSS). `innerHTML`에 데이터를 넣지 않는다

## Acceptance Criteria

- `python3 -m unittest discover -s tests` 통과(`.claude/harness.json`의 `verify.test`; `typecheck` · `lint` · `build`는 이 레포에 없음)
- `python3 -m unittest tests.test_desk_server_font` 통과

## 검증 절차

1. 위 AC 명령을 실제 실행한다.
2. ARCHITECTURE 「변경 범위」 밖 파일을 만지지 않았는지 `git status`로 확인한다.
3. 결과를 `phases/desk-redesign-ui/index.json`의 해당 step에 기록: 성공 → `completed` + `summary`(1~2줄) / 실패 → `error` + `error_message` / 판단 불가 → `blocked` + `blocked_reason`.

## 금지사항

- hook 우회(`--no-verify`) · 요청 범위 밖 수정 · `desk/` · `hooks/` · `scripts/` 수정 금지. `phases/` · `docs/` · `.claude/design/`은 고치지 않는다.
- 쌓기만 하는 기록은 고치지 않는다.
