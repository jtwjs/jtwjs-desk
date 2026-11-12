# Step 6: server-workflow-fullstack

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-2026-11-11/{PRD,ARCHITECTURE,ADR}.md` — 특히 ADR-009 · ADR-010 · ADR-013
- `page/server.py` — **step 5 산출물**: `read_ledger` · `ALLOWED_REL` · `read_vault_friction` · `config_block` · `missing_row` · `list_phase_indexes`. 이 step은 이 부품을 쓰기만 한다(같은 서명 유지)
- `desk/ledger.py` — `parse_observations` · `parse_friction` · `workflow_rows` · `parse_inbox` · `classify_area` · `fullstack_order`
- `tests/` 안 step 5의 서버 통합 테스트 — 같은 임시 환경 구성을 재사용(복사 대신 같은 헬퍼가 있으면 그것을 import)
- `.claude/rules/testing.md` §0 · §5

## 작업

러너가 이 step을 테스트 먼저 → 구현으로 한 호출에서 돌린다. 변경은 `page/server.py`에 GET 둘 추가(+테스트).

### `GET /competency/workflow`

- 레포마다 `.claude/observations.md`를 `read_ledger`로 읽어 `parse_observations`, vault가 설정돼 있으면 `read_vault_friction` → `parse_friction`. `workflow_rows`로 합쳐 레포 이름을 붙인다(friction 행은 `repo` 없음)
- 응답: `{"config": config_block(cfg), "rows": [{source, repo?, pattern?, kind?, count, last?, highlight, unparsed?}], "missing": [...]}`
- 읽을 파일이 없는 레포는 `missing_row`로, vault가 설정돼 있는데 friction 파일이 없으면 `missing_row("(vault)", "friction", "파일 없음")`로. `vault`가 설정에 없으면 friction은 조용히 건너뛰지 않고 `config`가 알린다(`config.source`/`error`는 step 5 규칙 그대로)
- `unparsed` 행은 **원문 없이** 그대로 내려보낸다(ADR-013)

### `GET /competency/fullstack`

- 레포마다 `_learn/inbox.md` → `parse_inbox` → 종류가 `기술` · `도메인`인 카드만(`막힌 질문` · `직무`는 복습함 쪽이거나 범위 밖이라 여기서 뺀다). `classify_area`로 영역 분류, 영역별로 `fullstack_order`
- 응답: `{"config", "groups": {"fe": [...], "be": [...], "infra": [...], "domain": [...], "미분류": [...]}, "missing": [...]}`. 카드 항목: `{repo, title, kind, status, where, summary}`
- 빈 영역도 키는 항상 있다(빈 목록)

### 🔴 CRITICAL

- 사람 이름 · vault 원문 · 세션 대화 원문을 레포 · 상태 파일 · 로그에 넣지 않는다. 읽은 내용은 응답으로만 나가고 어디에도 저장하지 않는다(캐시 금지, ADR-009). vault는 `friction/index.md` 한 파일 외에 열지 않는다. 픽스처는 임시 폴더 안의 **지어낸** 파일
- `desk/`와 `page/`에서 다른 프로세스를 실행하지 않는다(`subprocess` · `os.system` · `Popen` 금지). `hooks/`는 변경하지 않는다
- 새 GET도 `check_host` 실패 시 `403`

## Acceptance Criteria

- `verify.test` 통과(`typecheck` · `lint` · `build`는 이 레포에 없음). 앞 step 테스트 회귀 없음
- 통합 테스트: observations 행이 횟수 내림차순 · 3회 이상만 `highlight` · friction 열림/보류 행이 같은 목록에 · friction 형식이 가정과 다르면 `unparsed` 행(원문 문자열이 응답에 없음) · 파일 없는 레포가 `missing`에 · fullstack이 영역별로 묶이고 상태 순서(`모름` → `설명 들음` → `내 말로 설명 가능`) · `직무`·`막힌 질문` 제외 · Host 틀리면 `403`

## 검증 절차

1. AC 명령 실행.
2. 체크: 응답 · 코드 어디에도 vault 허용 경로 외의 경로가 없음 · 파일 쓰기 호출이 새로 생기지 않음 · `subprocess` 계열 없음.
3. 결과를 `phases/desk-ledger-tabs/index.json` step 6에 기록.

## 금지사항

- hook 우회(`--no-verify`) · 요청 범위 밖 수정 · **테스트 파일 수정**(구현 단계에서) 금지. step 5의 부품 서명 · 기존 엔드포인트 동작 · `desk/` 모듈 · `phases/desk/` · `docs/`는 고치지 않는다. `hooks/` · `scripts/`는 변경하지 않는다.
