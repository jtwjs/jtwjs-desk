# Step 3: ledger-signals

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-2026-11-11/{PRD,ARCHITECTURE,ADR}.md` — 특히 ADR-009(읽기 규약) · ADR-013(observations · friction · score 규칙)
- `desk/ledger.py` — step 2 산출물. **같은 파일에 함수를 더한다**(step 2의 함수는 고치지 않는다)
- `~/.claude/plugins/cache/jtwjs-plugins/claude-harness/0.34.0/skills/task-observer/SKILL.md` §2 — `observations.md` 표 형식(열 이름 · `## 열린 것` / `## 닫힌 것`). 읽기만 한다
- `.claude/rules/testing.md` §0 · §5

## 작업

러너가 이 step을 테스트 먼저 → 구현으로 한 호출에서 돌린다. 아래는 순수 함수이며 `find_score_file`만 디렉터리 목록을 본다(파일 내용은 열지 않는다).

- `parse_observations(text: str) -> list[dict]`: `## 열린 것` 아래 마크다운 표 행만. 반환 키 `pattern · kind · count · last · evidence`. `횟수`가 정수가 아니면 `count:None`으로 두고 `unparsed:True`. 다음 `## ` 헤딩(예: `## 닫힌 것`)에서 멈춘다. 헤더 행과 구분선 행은 건너뛴다
- `parse_friction(text: str) -> list[dict]`: ADR-013의 **가정형 파서**. 표 헤더에 `상태`와 `횟수` 칸이 있으면 그 칸 위치를 쓰고, 상태가 `열림` · `보류`인 행만 낸다. 반환 키 `pattern`(첫 칸) · `status` · `count`. 표 헤더가 없거나 행의 칸 수가 헤더와 안 맞으면 그 행 대신 `{"unparsed": True}` 하나를 낸다 — **행의 원문은 반환하지 않는다**(vault 원문을 응답에 싣지 않는다)
- `workflow_rows(obs: list[dict], friction: list[dict]) -> list[dict]`: 두 목록을 하나로. 각 행에 `source`(`"observations"` | `"friction"`)와 `highlight`(`count >= 3`, `count`가 `None`이면 `False`)를 붙이고 `count` 내림차순 정렬(`None`은 맨 뒤, 안정 정렬). `unparsed` 행도 포함
- `parse_score(text: str) -> dict | None`: JSON에서 `total` · `grade`만 꺼내 `{"total", "grade"}`. JSON이 아니거나 두 키가 없으면 `None`
- `find_score_file(repo_root: Path) -> tuple[Path, str | None] | None`: ADR-013의 순서(`.claude/reports/<날짜>/` → `docs/` → `.claude/` → 레포 루트)로 `ai-readiness-score.json`을 찾는다. 앞에서 찾으면 멈춘다. reports는 `YYYY-MM-DD` 이름의 폴더 중 **가장 최근 것**이고 두 번째 값이 그 날짜 문자열(나머지는 `None`). 아무 데도 없으면 `None`
- `age_days(scored_on: date, today: date) -> int`: 일수 차(음수면 0)

### 🔴 CRITICAL

- 사람 이름 · vault 원문 · 세션 대화 원문을 레포에 넣지 않는다. friction 픽스처는 **지어낸** 표(패턴 `샘플 패턴 A` 같은 가짜). 실제 vault 파일은 이 머신에 없고, 있어도 복사하지 않는다
- 다른 프로세스를 실행하지 않는다(`subprocess` · `os.system` · `Popen` 금지). `desk/`는 다른 패키지를 import하지 않는다
- `desk/`가 `score.py` · `daily_hub.py`를 실행하지 않는다. 점수는 이미 쓰인 JSON만 읽는다

## Acceptance Criteria

- `verify.test` 통과(`typecheck` · `lint` · `build`는 이 레포에 없음)
- 테스트가 단언: observations 열린 것만 읽고 닫힌 것 무시 · 횟수가 정수가 아닌 행 · friction 열림/보류만 · 헤더 없는 friction → `unparsed` 한 건에 원문 없음 · 3회 이상만 `highlight` · 횟수 내림차순과 `None` 맨 뒤 · score 4곳 우선순위(앞 위치가 이김, reports는 최신 날짜 폴더) · 아무 데도 없으면 `None` · `parse_score` 깨진 JSON → `None` · `age_days` 음수 방지

## 검증 절차

1. AC 명령 실행.
2. `desk/ledger.py`에 `subprocess` · `Popen` · `os.system`이 없는지, 파일 내용을 읽는 호출(`read_text` · `open(`)이 없는지 확인.
3. 결과를 `phases/desk-ledger-tabs/index.json` step 3에 기록.

## 금지사항

- hook 우회(`--no-verify`) · 요청 범위 밖 수정 · **테스트 파일 수정**(구현 단계에서) 금지. step 2가 만든 함수 · `desk/`의 다른 모듈 · `phases/desk/` · `docs/`는 고치지 않는다. `hooks/`는 이 phase에서 변경하지 않는다.
