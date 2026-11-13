# Step 3: signal-get

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-hypothesis-gate-2026-11-12/{PRD,ARCHITECTURE,ADR}.md` — ARCHITECTURE 「신호 엔드포인트」 · 「원장 없음·깨짐 표시」 · 「쓰기」, PRD 수용 조건의 없음·깨짐 표시 · 읽기 전용 · 원문 없음 · 실패 격리
- `.claude/rules/testing.md` §0 · `.claude/rules/non-obvious-patterns.md` (「서버 · 화면」 · 「sdd · nav-counts」)
- `page/server.py` — `missing_row`, `build_trends`(설정 없음 · 파일 없음 · 형식 확인 필요 이유를 만드는 방식), `GET /trends` 라우팅
- `desk/signal.py` — step 1이 만든 `parse_ledger` · `compute_signal`과 응답 계약. **계약의 dict 키는 이 파일의 docstring · `phases/desk-hypothesis-gate/step1.md` 「계약」이 정본이다**
- `desk/config.py` — step 2가 더한 `hypothesis_ledger` · `hypothesis_streak_threshold` 키
- `tests/test_desk_server_trends.py` — 서버 테스트 모양 참고

## 작업

**`page/server.py`에 읽기 엔드포인트 하나만 더한다**(`GET /hypothesis-signal`). 테스트는 `tests/test_desk_server_hypothesis.py`.

- `build_hypothesis_signal(cfg) -> dict`(순수 함수로 두고 라우트는 얇게): 
  - `cfg["hypothesis_ledger"]`가 `None` → `{"missing": "설정 없음"}`
  - 경로가 있는데 파일이 없음 → `{"missing": "파일 없음"}` (디렉터리·경로 자체가 없을 때도 같다)
  - 읽기 · 디코딩 실패 → `{"missing": "형식 확인 필요"}`
  - 그 밖에는 `parse_ledger` → `compute_signal(rows, broken, cfg["hypothesis_streak_threshold"])`의 dict에 `"missing": null`을 더해 돌려준다. 맡김 줄 0건이어도 `missing`은 null이고 `empty: true`(이유 행과 구별)
- 응답은 **항상 HTTP 200 JSON**이고 `Content-Type`은 기존 `/trends`와 같다. 예외는 라우트에서 잡아 `{"missing": "형식 확인 필요"}`로 바꾼다(500을 내지 않는다)
- 이 엔드포인트는 **원장을 열기만 한다**: `open(..., "r")` 외 쓰기 · 이름 변경 · 삭제 없음. POST · PUT 등 쓰기 메서드를 이 경로에 만들지 않는다
- `/nav-counts`는 건드리지 않는다(이 기능은 메뉴 배지가 없다)

### 🔴 CRITICAL (CLAUDE.md 그대로)

- 응답에 가설 · 이유 원문을 싣지 않는다 — `compute_signal`의 dict 키만 그대로 싣는다(원장 줄을 통째로 에코하지 않는다)
- 훅은 이 step과 무관하다(훅에 모델 토큰을 쓰지 않는다는 규칙은 그대로)
- 테스트의 가짜 원장은 `repo-a` · `task-1` 같은 가짜 값만 쓴다. 사람 이름 · vault 원문 금지
- 서버 응답 필드를 화면이 읽는지는 step 4~5가 브라우저로 확인한다(비명백 패턴 「서버 · 화면」) — 이 step에서 키 이름을 바꾸지 않는다

## Acceptance Criteria

- `verify.test` 통과
- 테스트가 단언한다: 설정 없음 · 파일 없음 · 형식 확인 필요(읽을 수 없는 바이트) 각각 `missing` 문구 · 정상 원장 → `areas` · `hyp_first` · `streak` 등이 `compute_signal`과 같음 · 깨진 줄 1개 → `broken`에 줄 번호 · 맡김 줄 0건 → `missing` null + `empty` true · **읽기 전용**(요청 전후 원장 파일의 바이트(해시)가 같음) · **원문 없음**(원장에 `"hyp": "SECRET-TEXT"` 줄을 넣고 응답 본문에 그 문자열이 없음) · **실패 격리**(신호가 `missing`이어도 `GET` 풀스택 카드 응답은 기존과 같은 모양으로 성공)

## 검증 절차

1. AC 명령을 실제 실행한다.
2. 라우트 표에 쓰기 메서드가 이 경로에 없는지 `grep -n "hypothesis" page/server.py`로 확인한다.
3. 결과를 `phases/desk-hypothesis-gate/index.json`의 step 3에 기록(성공 `completed` + `summary` / 실패 `error` / 차단 `blocked`).

## 금지사항

- hook 우회(`--no-verify`) · 요청 범위 밖 수정 · **테스트 파일 수정**(구현 단계에서) 금지
- `page/server.py`와 위 테스트 파일 밖은 고치지 않는다(`desk/signal.py` · `desk/config.py`는 앞 step이 끝낸 것 — 계약이 어긋나면 고치지 말고 `blocked`로 보고한다). 쌓기만 하는 기록은 고치지 않는다
- 기존 `/trends` · `/nav-counts` · 풀스택 라우트의 응답을 바꾸지 않는다
