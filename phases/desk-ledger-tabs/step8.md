# Step 8: server-weekly-health

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-2026-11-11/{PRD,ARCHITECTURE,ADR}.md` — 특히 PRD 주간 롤업 · 레포 건강도 수용 조건 · ADR-009 · ADR-012(일간 JSON) · ADR-013(score 규칙)
- `page/server.py` — step 5~7 산출물(`config_block` · `missing_row` 등). 같은 서명 유지
- `desk/rollup.py` · `desk/ledger.py`(`find_score_file` · `parse_score` · `age_days`) · `desk/config.py`
- `.claude/rules/testing.md` §0 · §5

## 작업

러너가 이 step을 테스트 먼저 → 구현으로 한 호출에서 돌린다. 변경은 `page/server.py`(+테스트).

- 시계는 한 곳에서 주입한다: 모듈 함수 `_today() -> date`(기본 `date.today()`)를 만들고 두 엔드포인트가 이것만 쓴다. 테스트가 이 함수를 바꿔 끼운다(`time`을 직접 흉내내지 않는다)

### `GET /weekly`

- `week_dates(_today())`의 각 날짜마다 `cfg["daily_dir"]/<날짜>.json`을 연다. 없거나 JSON이 깨졌거나 객체가 아니면 `None`. 이 경로는 **허용 목록의 `daily_dir` 아래 `YYYY-MM-DD.json` 이름 규칙에 맞는 파일만** 연다
- `desk.rollup.aggregate`의 결과를 `{"config": config_block(cfg), "week": {...}}`로 낸다. 일간 JSON이 하나도 없으면 `present:0`과 `missing` 7개로 나온다(ADR-012 "없는 동안 없음으로 센다")

### `GET /repo-health`

- 레포마다: 폴더가 없으면 `{"repo","missing":"경로 없음"}`. `find_score_file(root)`가 `None`이면 `{"repo","missing":"채점 없음"}`. 찾으면 파일을 읽어 `parse_score` → `None`이면 `{"repo","missing":"형식 확인 필요"}`, 아니면 `{"repo","total","grade","scored_on":"YYYY-MM-DD","age_days"}`
- 채점일(ADR-013): reports 폴더 날짜가 있으면 그것, 아니면 파일 수정시각의 날짜. `age_days = desk.ledger.age_days(scored_on, _today())`
- 응답: `{"config": config_block(cfg), "repos": [...]}`. `ALLOWED_REL`에 score 파일을 넣지 않는다: score는 `find_score_file`이 고정 후보 4곳 안에서만 찾는다

### 🔴 CRITICAL

- desk는 `score.py` · `daily_hub.py`를 **절대 실행하지 않는다.** 이미 쓰인 JSON을 읽기만 한다(PRD `desk-repo-health-trigger`). `subprocess` · `os.system` · `Popen` 금지
- 일간 JSON의 원문 키(`prompts` · `title` · `cwd`)가 있어도 응답에 나가지 않는다(step 4 `aggregate`가 막는다 — 응답에 `aggregate` 결과만 쓴다). 사람 이름 · 대화 원문을 레포 · 상태 파일에 넣지 않는다. 픽스처는 임시 폴더의 **지어낸** 값
- `hooks/`는 변경하지 않는다

## Acceptance Criteria

- `verify.test` 통과(`typecheck` · `lint` · `build`는 이 레포에 없음). 앞 step 테스트 회귀 없음
- 통합 테스트(`_today` 고정): 7일 중 2개만 있을 때 `present:2`와 `missing` 5개 · 일간 JSON에 `prompts` 문자열이 섞여도 응답에 없음 · 깨진 JSON은 없는 날로 셈 · 레포마다 score 있음/없음/경로 없음/형식 틀림 4모양 · reports 날짜 폴더로 `age_days` 계산 · 설정 `none`이면 `config.source` 알림 · Host 틀리면 `403`

## 검증 절차

1. AC 명령 실행.
2. 체크: `subprocess` 계열 없음 · 두 엔드포인트가 파일을 쓰지 않음 · `daily_dir` 밖 파일을 열지 않음.
3. 결과를 `phases/desk-ledger-tabs/index.json` step 8에 기록.

## 금지사항

- hook 우회(`--no-verify`) · 요청 범위 밖 수정 · **테스트 파일 수정**(구현 단계에서) 금지. 앞 step의 부품 서명 · 기존 엔드포인트 · `desk/` 모듈 · `phases/desk/` · `docs/`는 고치지 않는다. `hooks/` · `scripts/`는 변경하지 않는다.
