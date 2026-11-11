# Step 1: nav-counts-endpoint

`tdd: true` — 건수 판정(pick 없는 판정 수, 복습 대기 수)은 도메인 판정이라 RED 먼저.

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-2026-11-12/{PRD,ARCHITECTURE,ADR}.md`, `.claude/rules/testing.md` §0
- `page/server.py` — `list_judgments`(레포별 카드, `pick` 키 유무), `build_review`(`items` = 아직 done 아닌 것), `config.load_config()`를 쓰는 `/review` 핸들러, `check_host`, `do_GET`의 기존 라우트 형태
- `tests/test_desk_server.py`(`_ServerTestCase`) · `tests/test_desk_server_review.py` — 픽스처(임시 폴더의 지어낸 레포) 패턴

## 작업

`page/server.py`에 `GET /nav-counts`를 더한다. 응답 `{"judge": N, "review": N}`(정수).

- `judge` = `list_judgments()` 중 `"pick"` 키가 **없는** 카드 수. 반영(applied)된 카드는 pick이 있으므로 센다면 이미 제외된다
- `review` = 설정이 있으면 `len(build_review(cfg)["items"])`, `cfg["source"] == "none"`이면 0
- `check_host`를 기존 GET과 같은 방식으로 통과시킨다(실패 403). 아무것도 쓰지 않는다. 새 도메인 모듈을 만들지 않고 얇은 함수 하나(`count_nav(cfg)` 정도)로 둔다
- 테스트: `tests/test_desk_server_navcounts.py` — 빈 상태(0, 0) · pick 있는 카드는 제외 · 설정 없음이면 review 0 · 복습 항목 중 done 처리된 것은 제외 · Host가 다르면 403 · 레포 경로 없음이어도 200

### 🔴 CRITICAL (`CLAUDE.md`에서 그대로)

- 사람 이름 · vault 원문 · 세션 대화 원문을 레포와 상태 파일에 넣지 않는다(화면 견본 문구도 일반 문구만)
- 훅은 모델 토큰을 쓰지 않는다. 이 phase는 `hooks/`를 건드리지 않는다
- 런타임은 Python 표준 라이브러리만. 외부 패키지를 들이지 않는다
- 응답 문자열은 `textContent`로만 DOM에 넣는다(저장형 XSS). `innerHTML`에 데이터를 넣지 않는다

## Acceptance Criteria

- `python3 -m unittest discover -s tests` 통과(`.claude/harness.json`의 `verify.test`; `typecheck` · `lint` · `build`는 이 레포에 없음)
- `python3 -m unittest tests.test_desk_server_navcounts` 통과

## 검증 절차

1. 위 AC 명령을 실제 실행한다.
2. ARCHITECTURE 「변경 범위」 밖 파일을 만지지 않았는지 `git status`로 확인한다.
3. 결과를 `phases/desk-redesign-ui/index.json`의 해당 step에 기록: 성공 → `completed` + `summary`(1~2줄) / 실패 → `error` + `error_message` / 판단 불가 → `blocked` + `blocked_reason`.

## 금지사항

- hook 우회(`--no-verify`) · 요청 범위 밖 수정 · `desk/` · `hooks/` · `scripts/` 수정 금지. `phases/` · `docs/` · `.claude/design/`은 고치지 않는다.
- 쌓기만 하는 기록은 고치지 않는다.
