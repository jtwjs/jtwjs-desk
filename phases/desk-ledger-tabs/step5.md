# Step 5: server-review

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-2026-11-11/{PRD,ARCHITECTURE,ADR}.md` — 특히 ADR-009(허용 목록 · 읽기만) · ADR-010(탭마다 GET) · ADR-011(마킹은 서버가 씀) · ADR-004(11-03: 토큰 · Origin · Host)
- `page/server.py` — 기존 `do_GET` · `do_POST` · `_handle_pick`의 검사 순서 · `check_host` · `list_sessions` · `_send_json`. **`/pick` 동작은 바꾸지 않는다**
- `desk/config.py` · `desk/ledger.py`(step 1~3 산출물) · `desk/paths.py` · `desk/atomic.py`
- `hooks/desk_hook.py`의 세션 상태 파일에 레포 이름을 쓰는 필드 이름(코드로 확인)
- `tests/test_desk_server.py` — 서버를 임시 포트 · 임시 `DESK_HOME`으로 띄우는 테스트 패턴
- `.claude/rules/testing.md` §0 · §5

## 작업

러너가 이 step을 테스트 먼저 → 구현으로 한 호출에서 돌린다. 변경은 `page/server.py` 한 파일(+테스트). `page/`는 `desk/`만 import한다.

### 1) 공통 부품 (이 step이 만들고 step 6~8이 쓴다)

- **읽기 허용 목록(ADR-009)**: `read_ledger(repo_root: Path, rel: str) -> str | None` — `rel`이 허용 상수(`ALLOWED_REL`)에 든 것만 연다. 아니면 `ValueError`. 이 step의 `ALLOWED_REL`은 `.claude/observations.md` · `_learn/inbox.md`. 파일이 없으면 `None`. `list_phase_indexes(repo_root: Path) -> list[tuple[str, dict]]`: `phases/*/index.json`만 읽어 `(task, dict)`(깨진 JSON은 건너뜀). 뒤 step이 `ALLOWED_REL`에 항목을 **추가**한다
- `read_vault_friction(vault: Path | None) -> str | None`: `<vault>/1_MyBrain/brain/friction/index.md` **고정 한 경로만**. `vault`가 `None`이거나 파일이 없으면 `None`. 다른 vault 경로를 여는 함수는 만들지 않는다
- `config_block(cfg: dict) -> dict`: `{"source", "unregistered", "error"}` — `unregistered`는 `desk.config.unregistered(live_repo_names, cfg["repos"])`. 살아 있는 세션의 레포 이름은 `list_sessions()` 결과의 레포 필드에서 얻는다
- `missing_row(repo: str, what: str, reason: str) -> dict`: `{"repo","what","missing"}` — `reason`은 `"경로 없음"`(레포 폴더가 없음) 또는 `"파일 없음"`. 읽을 파일이 없는 레포는 **행을 빼지 않고** 이 행을 응답 `missing` 목록에 넣는다
- 새 POST 공통 검사 `_check_post_guard()`: `X-Desk-Token` 일치 → `Origin` → `check_host` 순서, 실패하면 모두 `403`(기존 `/pick`과 같은 순서). `/pick` 코드를 이 함수로 바꾸지 않는다
- 이름 검증: `repo`는 `^[A-Za-z0-9._-]+$`, 항목 키는 `^(phase|card)-[A-Za-z0-9._-]+$`. 안 맞으면 `400`(경로 조작 방지)

### 2) `GET /review`

- `check_host` 실패 → `403`. 설정은 **요청마다** `load_config()`로 읽는다(설정을 고치면 바로 반영)
- 레포마다(`cfg["repos"]`, 레포 키는 폴더 이름): `skipped_phases(list_phase_indexes(root))` → `{"repo","kind":"phase","key":phase_key(task),"title":task}` · `review_cards(parse_inbox(text))` → `{"repo","kind":"card","key":card_key(title),"title","card_kind","status","where","summary"}`. `review_dir(repo)/<key>.done.json`이 있는 항목은 뺀다(ADR-011)
- 응답: `{"config": config_block(cfg), "items": [...], "missing": [...]}`. 설정이 `none`이면 `items:[]`와 `config`만(조용히 비지 않도록 `config.source`가 알린다)

### 3) `POST /review/done {repo, key}`

- `_check_post_guard()` → 이름 검증(`400`) → `review_dir(repo)/<key>.done.json`에 `{"at": <ISO-8601 문자열>}`를 `desk.atomic.write_json_atomic`으로 쓴다 → `200 {"ok": true}`. 이미 있으면 덮어써도 `200`(멱등)

### 🔴 CRITICAL

- 사람 이름 · vault 원문 · 세션 대화 원문을 레포 · 상태 파일 · 마킹 파일에 넣지 않는다. 읽은 내용은 **응답으로만** 나가고 어디에도 저장하지 않는다(ADR-009). 마킹 파일에는 `at`만 쓴다. 테스트 픽스처는 임시 폴더 안의 **지어낸** 레포 · 카드
- 훅은 모델 토큰을 쓰지 않는다 — `hooks/`는 변경하지 않는다. `desk/`와 `page/`에서 다른 프로세스를 실행하지 않는다(`subprocess` · `os.system` · `Popen` 금지)
- CORS 헤더를 내지 않는다(ADR-004)

## Acceptance Criteria

- `verify.test` 통과(`typecheck` · `lint` · `build`는 이 레포에 없음). 기존 `tests/test_desk_server.py`가 그대로 통과(`/pick` 회귀 없음)
- 통합 테스트(임시 포트 · `DESK_HOME` · `DESK_CONFIG` · `DESK_CONDUCTOR`): 건너뛴 phase + `vault:` 빈 카드가 `/review`에 보임 · `직무` 카드는 안 보임 · `POST /review/done` 뒤 `/review`에서 사라짐 · 토큰 누락 `403` · Origin 다름 `403` · 키 형식 틀림 `400` · 설정 없음 → `config.source=="none"` · 레포 폴더가 없으면 `missing`에 `경로 없음` · `ALLOWED_REL` 밖 경로를 `read_ledger`에 주면 `ValueError`

## 검증 절차

1. AC 명령 실행.
2. 체크: `page/`가 `hooks/` · `scripts/`를 import하지 않음 · 응답 헤더에 CORS 없음 · `done.json` 외에 쓰는 파일이 없음 · `subprocess` 계열 없음.
3. 결과를 `phases/desk-ledger-tabs/index.json` step 5에 기록.

## 금지사항

- hook 우회(`--no-verify`) · 요청 범위 밖 수정 · **테스트 파일 수정**(구현 단계에서) 금지. 기존 `/pick` · `/shutdown` · `/version` 동작과 `desk/`의 step 1~4 산출물 · `phases/desk/` · `docs/`는 고치지 않는다. `hooks/` · `scripts/`는 변경하지 않는다.
