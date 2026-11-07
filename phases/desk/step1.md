# Step 1: desk-core

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-2026-11-03/{PRD,ARCHITECTURE,ADR}.md`
- `.claude/harness.json` (`verify` 절 — 지금 `test`가 빈 문자열이다. 이 step이 처음 채운다)
- `.claude/rules/testing.md` (BDD 3계층 · 엣지 5축 · colocation 원칙)
- 참고용 유사 패턴 없음(이 레포 첫 코드). `desk/`는 아래 step들이 전부 import하는 공용 모듈이므로 다른 패턴을 베끼지 말고 이 파일의 시그니처를 그대로 따른다.

## 작업

`desk/` 패키지(Python 표준 라이브러리만, 외부 패키지 금지 — ADR-007 전제인 "외부 패키지 없음"은 PRD 범위 결정)를 만든다. 전부 **순수 함수** 또는 **원자적 파일 쓰기 하나**로 한정한다 — 입출력 대기(네트워크·잠금)는 절대 넣지 않는다.

- `desk/paths.py`
  - 세션 상태 디렉터리: `DESK_RUN` 환경변수(없으면 `/tmp/jtwjs-desk`) 아래 `sessions/`
  - 판정 inbox: `DESK_HOME` 환경변수(없으면 `~/.jtwjs-desk`) 아래 `inbox/<repo>/`
  - 서버 메타: `DESK_HOME` 아래 `server.json`
  - 훅 에러 로그: `DESK_HOME` 아래 `hook-errors.log`
  - ntfy 토픽 파일: `~/.config/jtwjs-desk/ntfy-topic` (이것만 `DESK_HOME`과 무관 — ADR-005)
  - 환경변수를 인자가 아닌 모듈 레벨에서 읽지 않는다. 함수 인자로 받거나, 호출 시점에 `os.environ.get`으로 읽어 테스트가 임시 폴더로 바꿔 끼울 수 있게 한다(ARCHITECTURE 테스트 전략 — "파일 경로는 환경 변수로 바꿀 수 있게").
- `desk/atomic.py`
  - `write_json_atomic(path: Path, obj: dict) -> None`: 같은 디렉터리에 임시 파일을 쓰고 `os.replace`로 교체(ADR-001 "쓰기는 전부 임시 파일 + os.replace"). 디렉터리가 없으면 만든다.
- `desk/validate.py` — ADR-006의 질문·선택 형식을 그대로 스키마로 삼는다.
  - `validate_ask(data: dict) -> list[str]`: 질문 형식(`id · order · issue · area · question · why · options[{key,label,recommended}] · see[] · aiDecided[{key,label}] · premiseOpen`) 검증. 어긴 필드 이름 목록을 반환(빈 리스트면 통과) — 예외를 던지지 않는다(실패를 값으로, `implementation-patterns.md` 패턴 6).
  - `validate_pick(data: dict) -> list[str]`: 선택 형식(`at · choice|"custom" · customText · note · noteKind(reason|scope|new) · aiRejected[key]`) 검증. 같은 반환 규칙.
- `desk/sort.py`
  - `is_idle(status: str, last_at: float, now: float) -> bool`: `status == "작업 중" and now - last_at > 600`(10분, ADR-002 "신호 없음은 저장하지 않고 GET 때마다 계산"). `now`를 인자로 받는다(`implementation-patterns.md` 패턴 2 — 암묵적 입력 승격. `Date.now()`를 함수 안에서 읽지 않는다).
  - `effective_status(status: str, last_at: float, now: float) -> str`: `is_idle`이 참이면 `"신호 없음"`, 아니면 `status` 그대로.
  - `sort_key(effective_status: str) -> int`: 정렬 순서 `승인 대기(0) > 신호 없음(1) > 입력 대기(2) > 작업 중(3) > 완료(4)`를 매핑. 모르는 값은 가장 뒤로 보낸다(5).
  - `sort_sessions(sessions: list[dict], now: float) -> list[dict]`: 각 세션에 `effective_status`를 적용해 `sort_key` 오름차순으로 정렬한 새 리스트를 반환(원본 불변 — 패턴 4 카피-온-라이트, `sorted()` 사용).

### 🔴 CRITICAL (CLAUDE.md에서 인용)

- 사람 이름·vault 원문·세션 대화 원문을 상태/판정 데이터 모델에 넣지 않는다. 이 step이 만드는 필드 목록(`question`·`why`·`options` 등)은 전부 역할·라벨 수준이고, 사람 이름이나 원문을 담는 필드를 추가하지 않는다.
- 훅은 모델 토큰을 쓰지 않는다 — 이 step은 훅 자체가 아니지만, `desk/` 함수는 전부 stdout에 아무것도 쓰지 않는다(다음 step이 이 규칙을 지키려면 이 모듈이 조용해야 한다).

## Acceptance Criteria

- `python3 -m unittest discover -s tests` 통과. **이 step 시작 시점엔 테스트가 0개라 exit 5다** — 이 step이 `tests/test_desk_core.py`(최소)를 추가하고 나서 `.claude/harness.json`의 `verify.test`를 `"python3 -m unittest discover -s tests"`로 채운다(지금 빈 문자열인 이유: `harness.json` 주석 "sdd 첫 step 이 첫 테스트와 함께 채운다"). 채운 뒤 같은 명령이 통과해야 한다.
- `verify.lint`·`verify.typecheck`·`verify.build`는 비어 있다 — 채우지 않는다(외부 패키지 없음, 린터 없음. PRD 범위 결정).

## 검증 절차

1. 위 AC 명령을 실제 실행한다(테스트 추가 전 exit 5 확인 → 추가 후 통과 확인).
2. 아키텍처 체크리스트 대조: `desk/` 파일들이 서로 import 관계가 없고(각자 독립), 네트워크·서브프로세스·잠금을 쓰지 않는가(ARCHITECTURE "입출력 대기 안 함"). `is_idle`·`effective_status`·`sort_sessions`가 `now`를 인자로 받는가(모듈 안에서 `time.time()`을 직접 부르지 않는가).
3. 결과를 `phases/desk/index.json`의 step 1에 기록: 성공 → `status:"completed"` + `summary`(1~2줄), 실패 → `status:"error"` + `error_message`, 판단 불가 → `status:"blocked"` + `blocked_reason`.

## 금지사항

- hook 우회(`--no-verify`) · 자동 생성물 직접 수정 · `.claude/rules/`가 금지한 의존 방향 위반 · 요청 범위 밖 수정 · 테스트 파일 수정(이 step은 RED 테스트를 쓰는 step이므로, 테스트를 쓴 뒤 구현 커밋에서 그 테스트 파일을 다시 고치지 않는다) 금지.
- 쌓기만 하는 기록(`_brain/wiki/log/` · 옛 `log.md` · 회고 · `docs/`의 지난 설계 · ADR 본문 · `phases/*/`)은 이 step과 무관하니 건드리지 않는다.
