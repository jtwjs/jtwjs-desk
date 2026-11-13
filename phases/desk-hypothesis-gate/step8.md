# Step 8: signal-repo-param

> `tdd: true`: `page/server.py`의 응답 계약이 바뀐다. step 7의 `desk/signal.py` 함수(`repos_of` · `filter_rows`)를 쓴다.

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-hypothesis-gate-2026-11-12/PRD.md` 「결정」 표의 **레포별 보기** 행 · 수용 조건 표(읽기 전용 · 원문 없음 · 레포별 보기)
- `page/server.py`의 `build_hypothesis_signal` · `/hypothesis-signal` 라우트(`parsed.path == "/hypothesis-signal"`). 쿼리 읽는 다른 라우트가 있으면 그 방식을 따른다
- `desk/signal.py` (step 7 결과: `repos_of` · `filter_rows`)
- `tests/test_desk_server_hypothesis.py` (서버 테스트 모양 참고. 단 아래 「RED 커밋에 넣는다」의 한 줄만 고친다)
- `.claude/rules/testing.md` §0 · `.claude/rules/non-obvious-patterns.md` 「서버 · 화면」

## 작업

**`page/server.py`만 고친다**(+ 새 테스트 파일 `tests/test_desk_server_hypothesis_repo.py`).

**RED 커밋에 넣는다(🔴 GREEN에서 고치면 러너가 되돌리고 실패시킨다):** 기존 `tests/test_desk_server_hypothesis.py`의 `test_정상_원장이면_compute_signal과_같은_값에_missing_null이다`는 응답에서 `missing`만 빼고 `compute_signal` 결과와 같다고 단언해서, 새 응답 키 `repos`와 부딪힌다. 새 응답 계약 기준으로 `missing`과 `repos` 둘 다 빼고 비교하도록 그 단언 한 줄만 바꾼다. 이 수정은 새 테스트 파일과 **같은 test 커밋(RED)** 에 넣는다. 그 뒤 테스트 파일은 안 건드린다.

- `build_hypothesis_signal(cfg, repo=None)`: 파싱한 뒤 `repos = signal.repos_of(rows)`, 거른 줄로 `compute_signal`을 부르고 응답에 `"repos": repos`를 더한다. `repos`는 **거르기 전** 전체 줄에서 뽑는다(칩 선택지가 고른 레포 하나로 줄지 않게). `missing` 응답(설정 없음 · 파일 없음 · 형식 확인 필요)에는 `repos`를 더하지 않는다
- 라우트는 쿼리 `repo=`를 읽어 `build_hypothesis_signal`에 넘긴다. 쿼리가 없거나 빈 문자열이면 `None`(전체). 값은 문자열로만 쓰고 파일 경로로 쓰지 않는다
- 응답은 늘 200, 실패는 기존 `{"missing": "형식 확인 필요"}` 처리 그대로. 원장은 읽기만 한다
- 기존 호출(`build_hypothesis_signal(cfg)`)과 기존 응답 키는 그대로 유지한다

### 🔴 CRITICAL (CLAUDE.md 그대로)

- 응답에 원문(가설 · 이유)을 싣지 않는다. 사람 이름 · vault 원문을 코드와 테스트에 넣지 않는다(가짜 값만)
- 훅은 건드리지 않는다. 원장 · 입력 쓰기 엔드포인트를 만들지 않는다
- `page/server.py`와 위 테스트 파일 밖은 고치지 않는다(`desk/signal.py`도 이 step에서는 고치지 않는다)

## Acceptance Criteria

- `verify.test` 통과(기존 테스트 전부)
- 테스트가 단언한다(가짜 원장 파일 + `build_hypothesis_signal`, 라우트는 서버를 띄워 한 번):
  - `repo` 없음 → 기존과 같은 값 + `repos`가 레포 이름 목록
  - `repo="repo-a"` → a 줄만으로 센 값. 원장 파일 전체를 읽는 것은 같고 파일 내용은 바이트까지 안 바뀐다
  - 모르는 레포 이름 → 전체와 같은 값
  - `missing` 응답에는 `repos`가 없다
  - 응답 본문에 `SECRET-TEXT`가 없다
  - 서버를 띄워 `GET /hypothesis-signal?repo=repo-a`가 200이고 위와 같은 본문

## 검증 절차

1. AC 명령을 실제 실행한다.
2. 결과를 `phases/desk-hypothesis-gate/index.json`의 step 8에 기록.

## 금지사항

- hook 우회(`--no-verify`) · 요청 범위 밖 수정 · **테스트 파일 수정**(구현 단계에서) 금지
- `page/server.py`와 위 테스트 파일 밖은 고치지 않는다. 기존 테스트는 위 한 단언만 RED 커밋에서 고친다. 쌓기만 하는 기록은 고치지 않는다
