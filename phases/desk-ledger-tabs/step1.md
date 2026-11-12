# Step 1: desk-config

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-2026-11-11/{PRD,ARCHITECTURE,ADR}.md` — 특히 ADR-008(설정 파일 · 폴백 · unregistered)
- `desk/paths.py` — 환경변수를 호출 시점에 읽는 기존 패턴을 그대로 따른다
- `tests/test_desk_core.py` — 임시 폴더 · 환경변수 교체 테스트 패턴
- `.claude/rules/testing.md` §0 · §5

## 작업

러너가 이 step을 테스트 먼저 → 구현으로 한 호출에서 돌린다.

### 1) `desk/paths.py`에 경로 함수 4개 추가 (기존 함수는 건드리지 않는다)

- `config_path() -> Path`: 환경변수 `DESK_CONFIG`, 없으면 `~/.config/jtwjs-desk/config.json`(ADR-008)
- `conductor_path() -> Path`: 환경변수 `DESK_CONDUCTOR`, 없으면 `~/.claude/conductor.json`(테스트가 실제 파일을 읽지 않게 하는 용도)
- `review_dir(repo: str) -> Path`: `<desk_home_dir>/review/<repo>`
- `share_dir(repo: str) -> Path`: `<desk_home_dir>/share/<repo>`

### 2) `desk/config.py` (신규, 파일을 읽는 함수는 이 모듈의 `load_config` 하나뿐)

- `load_config() -> dict`: 반환 키 `source` (`"config"` | `"conductor"` | `"none"`) · `repos`(`list[Path]`, `~` 펼친 것) · `vault`(`Path | None`) · `criteria_file`(`Path | None`) · `daily_dir`(`Path`, 기본 `~/.claude/daily`) · `evidence_globs`(`list[str]`, 기본 `[]`) · `error`(`str | None`)
  - 규칙은 ADR-008을 따른다: `config_path()` 파일이 있으면 그것만 읽는다(`source:"config"`). 없을 때만 `conductor_path()`를 읽어 `repos` · `seat`(→ `vault`)를 쓴다(`source:"conductor"`, `criteria_file`은 `None`). 둘 다 없으면 `source:"none"`과 빈 `repos`
  - 설정 파일이 있는데 JSON이 깨졌거나 최상위가 객체가 아니면 폴백하지 않는다: `source:"config"`, `repos:[]`, `error`에 사유 한 줄. 키 타입이 틀리면(예: `repos`가 문자열) 그 키만 기본값으로 두고 `error`에 한 줄
  - 예외를 밖으로 던지지 않는다(서버가 요청마다 부른다)
- `unregistered(live_repo_names: list[str], repos: list[Path]) -> list[str]`: 레포 폴더 이름(basename)이 `repos`에 없는 살아 있는 세션의 레포 이름. 중복 제거, 입력 순서 유지(순수 함수)

### 🔴 CRITICAL (CLAUDE.md · PRD에서 인용)

- 사람 이름 · vault 원문 · 세션 대화 원문을 레포와 상태 파일에 넣지 않는다. 테스트 픽스처는 전부 **지어낸 값**(예: 레포 `sample-repo`)
- 이 모듈은 설정 파일 외에는 아무것도 열지 않고, 쓰지 않는다. 다른 프로세스를 실행하지 않는다(`subprocess` · `os.system` · `Popen` 금지)
- `desk/`는 `hooks/` · `scripts/` · `page/`를 import하지 않는다

## Acceptance Criteria

- `verify.test`(`.claude/harness.json`) 통과. `verify.typecheck` · `lint` · `build`는 비어 있다(이 레포는 없음)
- 테스트가 다음을 단언한다: 설정 파일 우선 · 없을 때 conductor 폴백(`seat`→`vault`) · 둘 다 없음 · 깨진 JSON(폴백 안 함 + error) · `~` 펼침 · `evidence_globs` 기본 빈 목록 · `unregistered` 중복 제거

## 검증 절차

1. AC 명령 실행.
2. `desk/config.py`에 `subprocess` · `Popen` · `os.system`이 없는지, `desk/`가 다른 패키지를 import하지 않는지 확인.
3. 결과를 `phases/desk-ledger-tabs/index.json` step 1에 기록(`completed` + `summary` / `error` + `error_message` / `blocked` + `blocked_reason`).

## 금지사항

- hook 우회(`--no-verify`) · 자동 생성물 직접 수정 · 요청 범위 밖 수정 · **테스트 파일 수정**(구현 단계에서) 금지. `desk/paths.py`의 기존 함수 · `phases/desk/` · `docs/`는 고치지 않는다.
- `hooks/` 아래는 이 phase 전체에서 변경하지 않는다(훅 토큰 0 원칙, ADR-009).
