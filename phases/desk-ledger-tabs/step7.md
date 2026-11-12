# Step 7: server-proactive-share

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-2026-11-11/{PRD,ARCHITECTURE,ADR}.md` — 특히 PRD 「범위」 3역량-적극성과 수용 조건 · ADR-008(`criteria_file` · `evidence_globs`) · ADR-009 · ADR-011(`.shared.json`)
- `page/server.py` — step 5 · 6 산출물(`read_ledger` · `ALLOWED_REL` · `list_phase_indexes` · `config_block` · `missing_row` · `_check_post_guard` · 이름 검증). 같은 서명 유지
- `desk/paths.py`(`share_dir`) · `desk/atomic.py` · `desk/config.py`
- `phases/desk/index.json` — step의 `started_at` · `completed_at` 형식(ISO 문자열인지 코드로 확인). 이 파일은 읽기만 한다
- `.claude/rules/testing.md` §0 · §5

## 작업

러너가 이 step을 테스트 먼저 → 구현으로 한 호출에서 돌린다. 변경은 `page/server.py`(+테스트).

### `GET /competency/proactive`

응답: `{"config", "criteria", "speed", "impact", "transparency", "missing"}`

- **criteria**: 설정 `criteria_file`이 있으면 그 파일 **텍스트 그대로**(`{"text": "..."}`), 없으면 `{"text": None, "note": "설정 없음"}`. 파일을 못 읽으면 `{"text": None, "note": "읽을 수 없음"}`. desk는 내용을 해석하지 않는다
- **speed**: `{"durations": [{repo, task, minutes}], "metric2": "측정 안 함", "workflow_link": "workflow"}`
  - ① `list_phase_indexes`의 각 phase에서 step의 `started_at`~`completed_at`이 모두 있는 것만으로 phase 총 분(가장 이른 시작 → 가장 늦은 완료). 타임스탬프가 없는 phase는 목록에서 빼되 `no_data` 개수로 센다. 파싱 실패는 예외 없이 건너뜀
  - ② 문구는 고정: `"측정 안 함"`(PRD `desk-speed-metric2`). ③ 링크 값만 두고 **숫자를 중복 집계하지 않는다**(AI워크플로우 탭이 갖고 있다)
- **impact**:
  - ① phase index의 `docs` 폴더에 `PRD.md`가 있으면 `{repo, task, prd: "<docs>/PRD.md"}`(경로만, 내용은 싣지 않는다)
  - ② 설정 `evidence_globs`의 패턴을 각 레포 루트 기준 `Path.glob`으로 풀어, 파일을 수정시각 내림차순 상위 5개 `{repo, path, mtime}`(경로와 시각만, 내용 안 읽음). 패턴 목록이 비었으면 `{"note": "경로 미설정"}`. 패턴에 `..`가 있거나 절대경로면 그 패턴만 무시하고 `config.error`가 아닌 `impact.ignored`에 개수를 낸다
- **transparency**: `share_dir(<레포 이름>)/*.md` 중 같은 id의 `<id>.shared.json`이 **없는** 것만 `{repo, id, text}`. `id`는 파일 이름에서 `.md`를 뺀 것, `text`는 `.md` 내용 그대로. 설정 레포의 폴더 이름만 훑는다(ADR-009)

### `POST /share/shared {repo, id}`

- `_check_post_guard()` → 이름 검증(`repo` · `id`는 `^[A-Za-z0-9._-]+$`, 아니면 `400`) → `share_dir(repo)/<id>.shared.json`에 `{"at": <ISO-8601 문자열>}` 원자적으로 → `200`. `.md` 파일은 만들거나 지우지 않는다(ADR-011). 멱등

### 🔴 CRITICAL

- 사람 이름 · vault 원문 · 세션 대화 원문을 레포 · 상태 파일 · 마킹 파일에 넣지 않는다. `criteria_file` · 공유 텍스트는 **응답으로만** 나가고 저장 · 캐시 금지. 픽스처는 임시 폴더의 **지어낸** 문서
- 투명성 콘텐츠를 desk가 슬랙에 보내지 않는다(PRD 하지 않을 것). 외부 전송 코드 없음
- `desk/`와 `page/`에서 다른 프로세스를 실행하지 않는다(`subprocess` · `os.system` · `Popen` 금지). `hooks/`는 변경하지 않는다

## Acceptance Criteria

- `verify.test` 통과(`typecheck` · `lint` · `build`는 이 레포에 없음). 앞 step 테스트 회귀 없음
- 통합 테스트: `criteria_file` 있음/없음/못 읽음 세 모양 · `metric2`가 `"측정 안 함"` · 소요시간이 타임스탬프로 계산되고 타임스탬프 없는 phase는 `no_data` · `PRD.md` 있는 phase에 링크 · `evidence_globs` 비면 `경로 미설정` · 패턴에 걸린 파일이 최신순 · `..` 패턴 무시 · 미반영 공유 파일만 노출(`.shared.json` 있으면 빠짐) · `POST /share/shared` 뒤 사라짐 · 토큰 누락 `403` · `repo`에 `../` → `400`

## 검증 절차

1. AC 명령 실행.
2. 체크: `evidence_globs` 처리 코드가 레포 루트 밖으로 못 나감 · `.md` 쓰기/삭제 코드 없음 · `subprocess` 계열 없음.
3. 결과를 `phases/desk-ledger-tabs/index.json` step 7에 기록.

## 금지사항

- hook 우회(`--no-verify`) · 요청 범위 밖 수정 · **테스트 파일 수정**(구현 단계에서) 금지. 앞 step의 부품 서명 · 기존 엔드포인트 · `desk/` 모듈 · `phases/desk/` · `docs/`는 고치지 않는다. `hooks/` · `scripts/`는 변경하지 않는다.
