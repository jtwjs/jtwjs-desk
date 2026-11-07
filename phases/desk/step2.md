# Step 2: desk-hook

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-2026-11-03/{PRD,ARCHITECTURE,ADR}.md` — 특히 ADR-002(훅 이벤트→상태 표) · ADR-003(서버 기동)·ADR-005(ntfy)
- `desk/paths.py`, `desk/atomic.py`(step 1 산출물) — 상태 파일 경로·쓰기는 이걸로만 한다
- `.claude/rules/testing.md` §0·§5(RED 단계 함정 — 이 step은 프로세스 기동을 흉내 내는 준비 코드가 많아 해당)

## 작업

`hooks/desk_hook.py` 하나(ADR-002). **`hooks/`는 `desk/`만 import한다 — `page/`·`scripts/`를 import하지 않는다**(ARCHITECTURE 경계). 서버는 import가 아니라 **서브프로세스로 띄운다**(파일 경로만 안다).

함수형 코어(순수) + 쉘(부수효과)로 가른다(`implementation-patterns.md` 패턴 1):

- **코어(순수, 단위 테스트 대상)**
  - `map_status(event_name: str, notification_type: str | None) -> str | None`: ADR-002 표 그대로 매핑. `SessionStart→"입력 대기"`, `UserPromptSubmit→"작업 중"`, `PostToolUse→"작업 중"`, `Notification`+`permission_prompt→"승인 대기"`, `Notification`+`idle_prompt→"입력 대기"`, `PreCompact→"작업 중"`, `Stop→"입력 대기"`. 그 밖(`SessionEnd` 포함)은 `None`.
  - `needs_server_check(event_name: str) -> bool`: `SessionStart`만 `True`.
  - `needs_ntfy(event_name: str, notification_type: str | None) -> bool`: `Notification`+`permission_prompt`만 `True`.
- **쉘(부수효과, 의존성은 인자로 주입 — 패턴 2)**
  - `derive_repo(cwd: str) -> str`: `git rev-parse --show-toplevel`을 `cwd`에서 실행해 basename. 실패(git 없음·레포 아님)하면 `os.path.basename(cwd)`로 폴백. 예외를 올리지 않는다.
  - `derive_branch(cwd: str) -> str`: `git rev-parse --abbrev-ref HEAD`. 실패하면 `""`.
  - `check_server_version(timeout: float = 0.3) -> bool`: `http://127.0.0.1:<port>/version`에 GET(포트는 `server.json` 또는 기본 47615 — ADR-003). 응답·버전 일치 여부에 따라 `True`/`False`. 예외(연결 거부·타임아웃)는 `False`.
  - `spawn_server() -> None`: 이 레포의 `page/server.py` 경로로 `subprocess.Popen([..], start_new_session=True)`. **파일이 아직 없어도(이 step 시점) 호출 시그니처만 맞으면 된다** — step 4가 실제 서버를 만든다. 이 함수는 호출 여부만 테스트에서 확인하면 되므로, 테스트는 이 함수 자체를 가짜로 바꿔 끼운다.
  - `send_ntfy(topic: str, repo: str, status: str) -> None`: `urllib`로 떼어 낸 자식 프로세스(`subprocess.Popen` 또는 `os.fork`+5초 상한) — 본문은 `f"{repo} · {status}"`만(브랜치·대화 내용 금지, ADR-005). 토픽은 `~/.config/jtwjs-desk/ntfy-topic` 파일이 있을 때만 읽는다(없으면 호출하지 않음 — 호출 여부는 `needs_ntfy` + 파일 존재로 `main`이 가른다).
  - `ensure_server(check_fn=check_server_version, spawn_fn=spawn_server) -> None`: `check_fn()`이 `False`면 `spawn_fn()`. 테스트가 `check_fn`·`spawn_fn`을 가짜로 주입(패턴 2 — 암묵적 입력 승격).
- **`main(argv: list[str]) -> int`**
  1. `event_name = argv[1]`, `payload = json.load(sys.stdin)` — **모두 `try/except Exception`으로 감싼다. 어떤 예외든 `desk/paths.py`의 훅 에러 로그에 한 줄 남기고 `return 0`**(ADR-002 "예외가 나도 세션을 막지 않는다").
  2. `SessionEnd`면 세션 상태 파일을 지운다(있으면 삭제, 없으면 무시) → `return 0`.
  3. `status = map_status(...)`가 `None`이면 아무것도 하지 않고 `return 0`.
  4. `repo`·`branch`를 구해 상태 딕셔너리(`repo · branch · status · lastAt=time.time()`)를 `desk/atomic.write_json_atomic`으로 세션 파일에 쓴다.
  5. `needs_server_check`면 `ensure_server()`.
  6. `needs_ntfy`면 토픽 파일이 있을 때만 `send_ntfy(topic, repo, status)`.
  7. **`stdout`·`stderr`에 절대 쓰지 않는다. 항상 `exit 0`**(CRITICAL — 모델 토큰 0, ADR-002).

- **`hooks/hooks.json`** — 이 훅을 실제로 등록하는 매니페스트(참고 패턴: `claude-harness/hooks/hooks.json`의 `${CLAUDE_PLUGIN_ROOT}` 사용법). 이벤트별로 `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/desk_hook.py" <이벤트명>`을 등록한다: `SessionStart`·`UserPromptSubmit`·`PostToolUse`(matcher 없음=전체 도구)·`Notification`·`PreCompact`·`Stop`·`SessionEnd`. 이게 없으면 훅이 아무리 잘 만들어져도 Claude Code가 부르지 않는다.

### 🔴 CRITICAL (CLAUDE.md에서 인용 — 이 step에 직결)

- **훅은 모델 토큰을 쓰지 않는다. 상태 파일만 쓰고 끝낸다.** `additionalContext`·stdout으로 모델에 글을 넣지 않는다.
- 사람 이름·vault 원문·세션 대화 원문을 레포와 상태 파일에 넣지 않는다. `send_ntfy`의 본문도 레포·상태만.

## Acceptance Criteria

- `.claude/harness.json`의 `verify.test`(step 1이 채운 값) 통과.
- 코어 함수(`map_status`·`needs_server_check`·`needs_ntfy`) 단위 테스트, `main`은 가짜 이벤트 JSON으로 통합 테스트(ARCHITECTURE 테스트 전략): 상태 파일 내용 확인 + **stdout이 빈 문자열인지 확인** + `SessionEnd`에서 파일이 지워지는지 확인.
- `python3 -c "import json; json.load(open('hooks/hooks.json'))"`로 JSON 문법 확인(이 레포는 lint 도구가 없다).

## 검증 절차

1. 위 AC 명령 실행.
2. 아키텍처 체크리스트: `hooks/desk_hook.py`가 `page/`·`scripts/`를 import하지 않는가(grep으로 확인). 모든 예외 경로에서 `exit 0`인가. `ensure_server`·`send_ntfy`가 주입 가능한 시그니처인가.
3. 결과를 `phases/desk/index.json` step 2에 기록(completed/error/blocked).

## 금지사항

- hook 우회(`--no-verify`) · 자동 생성물 직접 수정 · 요청 범위 밖 수정 · 테스트 파일 수정(구현 커밋에서) 금지.
- `page/`·`scripts/`를 import하지 않는다(경계 위반). `desk/`의 함수를 복제해서 다시 구현하지 않는다.
