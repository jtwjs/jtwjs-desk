# Step 10: health-send-grade-color

`tdd: true` — 서버 응답 계약(필드 전달)이라 RED 먼저.

## 배경

step 9가 `ledger.parse_score`에 `grade_color`(`green`/`amber`/`red`, 없으면 키 없음)를 더했다. 이 step은 `GET /repo-health` 응답이 그 값을 화면에 넘기게 한다. 화면(`page/index.html`)은 이미 `r.color || r.grade_color`를 읽으므로 **화면은 고치지 않는다**.

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-2026-11-12/{PRD,ARCHITECTURE,ADR}.md`, `.claude/rules/testing.md` §0
- `page/server.py` — `build_repo_health`
- `tests/test_desk_server_weekly.py` — `통합_GET_repo_health`(점수 파일을 임시 레포에 만드는 픽스처 패턴)

## 작업

`build_repo_health`의 점수 있는 행에, `parse_score` 결과에 `grade_color`가 있을 때만 `"grade_color"`를 같은 값으로 더한다.

- 없으면 행에 키를 넣지 않는다(기존 응답과 동일). `missing` 행은 바뀌지 않는다
- 테스트(`tests/test_desk_server_weekly.py`에 추가, 기존 테스트는 고치지 않는다): 점수 JSON에 `grade_color: "amber"`가 있으면 응답 행에 `"grade_color": "amber"` · 없으면 행에 `grade_color` 키 없음 · 모르는 색이면 키 없음

### 🔴 CRITICAL (`CLAUDE.md`에서 그대로)

- 사람 이름 · vault 원문 · 세션 대화 원문을 레포와 상태 파일에 넣지 않는다(픽스처도 지어낸 값만)
- 훅은 모델 토큰을 쓰지 않는다. `hooks/`를 건드리지 않는다
- 런타임은 Python 표준 라이브러리만. 외부 패키지를 들이지 않는다
- 응답 문자열은 `textContent`로만 DOM에 넣는다. `innerHTML`에 데이터를 넣지 않는다

## Acceptance Criteria

- `python3 -m unittest discover -s tests` 통과(`.claude/harness.json`의 `verify.test`; 나머지 verify 키는 비어 있음)

## 검증 절차

1. 위 AC 명령을 실제 실행한다.
2. `git status`에 `page/server.py`와 테스트 파일 외 변경이 없는지 확인한다.
3. 결과를 `phases/desk-redesign-ui/index.json`의 해당 step에 기록: 성공 → `completed` + `summary`(1~2줄) / 실패 → `error` + `error_message` / 판단 불가 → `blocked` + `blocked_reason`.

## 금지사항

- hook 우회(`--no-verify`) · 요청 범위 밖 수정 · **`desk/` · `page/index.html` · `hooks/` · `scripts/` 수정 금지**. `phases/` · `docs/` · `.claude/design/`은 고치지 않는다. 구현 step에서 테스트 파일의 기존 단언을 고치지 않는다.
- 쌓기만 하는 기록은 고치지 않는다.
