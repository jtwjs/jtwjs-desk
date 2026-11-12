# Step 5: trends-post

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-tech-trends-2026-11-12/{PRD,ARCHITECTURE,ADR}.md` — PRD 수용 조건 2 · 3 · 4 · 9 · 11 · 12 · 15 · 18, ADR 「읽음은 멱등 POST」 · 「북마크는 별도 이벤트 파일」
- `.claude/rules/testing.md` §0 · §1 · §2 · `.claude/rules/non-obvious-patterns.md`
- `desk/trends.py`(`record_read` · `record_mark` 반환 값 `"ok"` | `"duplicate"` | `"same"` | `"unknown_id"`, `OSError`는 올라온다) · `desk/config.py`
- `page/server.py` — `do_POST` 라우팅 · `_check_post_guard`(토큰 → Origin → Host) · `_read_json_body` · `_handle_routine_answer`(검증 순서와 응답 코드 패턴) · `_handle_pick`
- `tests/test_desk_server_routine.py` — POST 테스트 스타일(토큰 · Origin 헤더 포함)

## 계약

- `POST /trends/read` 본문 `{"id": str}`, `POST /trends/mark` 본문 `{"id": str, "on": bool}`
- 순서: `_check_post_guard` → JSON 파싱(실패 400 `bad json`) → 설정 읽기 → 본문 검증 → 기록
  - 본문이 dict가 아니거나 `id`가 비어 있지 않은 문자열이 아니거나(`/mark`는 `on`이 bool이 아닐 때도) → 400 `{"error": ...}`
  - 필요한 설정이 None(`/read`는 `trends_items`와 `trends_reads`, `/mark`는 `trends_items`와 `trends_marks`) → 400 `{"error": "not configured"}`
  - `record_*`가 `"unknown_id"` → 400 `{"error": "unknown id"}`
  - `"ok"` → 200 `{"ok": true, "changed": true}` · `"duplicate"` / `"same"` → 200 `{"ok": true, "changed": false}`(멱등)
  - `OSError` → 500 `{"error": "write failed"}`(경로 · 예외 메시지를 싣지 않는다)
- 읽음 실패와 북마크 실패는 서로의 상태를 바꾸지 않는다(파일이 따로라 구조상 보장 — 테스트로 단언)

## 작업

러너가 이 step을 테스트 먼저 → 구현으로 한 호출에서 돌린다. **`page/server.py`(두 핸들러와 `do_POST` 라우트 추가)와 새 테스트 파일 `tests/test_desk_server_trends_post.py`만** 만든다/고친다. `now`는 `datetime.now()`를 핸들러에서 넘긴다.

### 🔴 CRITICAL

- 사람 이름 · vault 원문 · 세션 대화 원문을 레포와 상태 파일에 넣지 않는다. 픽스처는 가짜 글이다
- 토큰 헤더 · Origin · Host 가드는 기존 `_check_post_guard` 그대로 쓴다(새로 만들지 않는다). 가드 실패는 403이고 파일이 안 바뀐다
- GET 핸들러는 건드리지 않는다. 쓰기는 이 POST 핸들러에서만 한다(ADR-009)

## Acceptance Criteria

- `.claude/harness.json`의 `verify.test` 통과. `typecheck` · `lint` · `build`는 이 레포에 없다
- `tests/test_desk_server_trends_post.py` 단언: 읽음 POST 성공 시 200 · 읽음 파일에 `{id, at}` 한 줄 · 이어지는 `GET /trends`에서 그 글 `read`가 true · 같은 id를 두 번 보내면 줄이 1개이고 둘 다 200 · 동향에 없는 id는 400이고 파일이 안 바뀐다 · 토큰 없음/틀림은 403 · `trends_reads`가 비면 400 · `trends_marks`가 비면 `/mark`가 400 · 쓸 수 없는 읽음 경로(파일 자리에 디렉터리)에서 500이고 이어지는 GET에서 그 글이 안 읽음으로 남는다 · 북마크 켬 → `GET /trends`의 `bookmarked` true와 북마크 목록 · 같은 켬 재전송은 `changed:false` · 끔 · 북마크 쓰기 실패(500)가 읽음 상태를 안 바꾼다 · 북마크를 켜도 읽음 파일이 안 바뀐다 · `on`이 bool이 아니면 400 · 깨진 JSON은 400
- 엣지 5축: 빈 값(빈 id) · 비정상 입력(타입 오류 · 없는 id) · 실패 경로(500) · 상태 전이(안 읽음 → 읽음 · 북마크 켬/끔) · 동시성(같은 id 동시 POST 두 건 → 줄 1개, 스레드 + `Barrier`, sleep 의존 금지)

## 검증 절차

1. AC 명령을 실제 실행한다.
2. `ARCHITECTURE.md` 구조 그림 · 쓰기 엔드포인트 · 북마크 행과 대조.
3. 결과를 `phases/desk-tech-trends/index.json`의 step 5에 기록: 성공 → `completed` + `summary`(1~2줄, 엔드포인트와 응답 모양 포함) / 실패 → `error` + `error_message` / 차단 → `blocked` + `blocked_reason`.

## 금지사항

- hook 우회(`--no-verify`) · 자동 생성물 직접 수정 · 요청 범위 밖 수정 · **테스트 파일 수정**(구현 단계에서) 금지
- 이 step이 맡지 않은 파일은 고치지 않는다(`desk/` · `page/index.html` 포함). 쌓기만 하는 기록(`docs/`의 지난 설계 · ADR 본문 · `phases/*/`)은 고치지 않는다
