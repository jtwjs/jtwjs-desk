# ADR: 지휘 책상 확장 — 복습함 · 3역량 · 주간 롤업 · 레포 건강도

> 번호는 [11-03 ADR](../desk-2026-11-03/ADR.md)(001~007)에 이어 008부터. 구현은 claude-harness에서 한다(ADR-012). PRD 결정 표 9개 중 `desk-no-new-collectors` · `desk-transparency-storage` · `desk-reflect-skip-field` · `desk-daily-hub-json-no-prompts` · `desk-repo-health-trigger`는 PRD가 정본이고 여기서는 구조 쪽 결정만 적는다.

## ADR-008 레포 · vault 경로는 `~/.config/jtwjs-desk/config.json`, 없으면 conductor.json 폴백

- 상태: 제안
- 맥락: 새 탭 4개는 레포마다 원장을 열어야 하고 vault의 friction 파일도 연다. desk는 지금 레포를 세션 cwd에서만 알고, vault 경로는 아무 데도 없다. `~/.claude/conductor.json`(`{"seat", "repos"}`)은 이 머신에 아직 없고, 하네스 스킬이 "있으면"으로만 정의한 선택 설정이다
- 결정: `~/.config/jtwjs-desk/config.json`에 `repos` · `vault` · `criteria_file` · `daily_dir`(기본 `~/.claude/daily`) · `evidence_globs`(레포 기준 경로 패턴 목록, 기본 빈 목록)를 손으로 둔다. `evidence_globs`는 임팩트②의 `evidence.md` · `cards/` 위치를 어디서도 못 찾아(PLAN 2026-11-11) 위치를 Finn이 정하도록 둔 키이고, 비어 있으면 화면에 "경로 미설정"으로 나온다(Finn 선택). 이 파일이 없을 때만 `conductor.json`의 `repos` · `seat`(→ vault)를 읽고, 화면에 "폴백 사용 중"을 띄운다. 폴백이 쓰이면 `criteria_file`은 비어 CPO 메모는 "설정 없음"이다. 서버는 살아 있는 세션의 레포 이름이 `repos`에 없으면 `unregistered`로 알린다(자동 추가는 안 한다). 경로는 `DESK_CONFIG`로 바꾼다
- 결정 주체: AI 추천 수용. Finn의 처음 가설은 conductor.json 재사용(이유: 한 곳에서 관리)이었고, 추천(desk 소유 설정 + 폴백)을 받아 그렇게 갔다. 한 곳 관리라는 이유는 폴백으로 일부 살렸다
- 대안: conductor.json 단독(파일이 없으면 새 탭 4개가 통째로 비고, 하네스가 필드 이름을 바꿔도 desk가 모른다. `desk-separate-repo` 결정이 막으려던 결합) · 훅이 cwd로 레포를 자동 학습(vault 경로는 cwd로 못 배워 설정 파일이 어차피 필요하고, 한 번도 안 연 레포는 안 보이고, 훅이 파일을 하나 더 쓴다)
- 결과: 새 레포를 만들면 `repos`에 한 줄을 손으로 더해야 한다. 잊어도 `unregistered`가 알려줘서 조용히 빠지지는 않는다. 대가는 설정 파일 하나가 늘고, `config.py`가 conductor.json 스키마를 가정하는 지점이 한 곳 생기는 것. 하네스가 그 스키마를 바꾸면 폴백만 깨진다

## ADR-009 새 탭은 허용 목록의 원장을 GET마다 읽기만 한다

- 상태: 제안
- 맥락: vault 규칙 9(상시 노출 빈 칸 함정)와 PRD `desk-no-new-collectors`. 서버가 원장을 캐시하거나 요약을 저장하면 그것이 새 수집기가 되고, 원장이 바뀐 뒤에도 옛 값이 남는다. 또 CRITICAL이 vault 원문을 레포와 상태 파일에 넣는 것을 막는다
- 결정: 서버는 GET을 받을 때마다 읽기 허용 목록(ARCHITECTURE 「읽기 규약」)의 경로만 열어 `desk/`의 순수 함수로 행을 만들어 응답한다. 캐시 · 중간 저장 · 로그 기록이 없다. `desk/`와 `page/`에서 다른 프로세스를 실행하지 않는다. vault는 `friction/index.md` 한 파일만 열고 `raw/` · `thread-raw/` · `0_Me/`는 목록에 없다. 파일이 없으면 행을 빼지 않고 "경로 없음" · "파일 없음"으로 낸다
- 결정 주체: AI 추천 수용 (PRD `desk-no-new-collectors`의 구현 방식)
- 대안: 서버가 주기적으로 긁어 한 파일로 저장(수집기가 됨 · 원문이 한 곳에 복사됨) · 허용 목록 없이 설정에 적힌 아무 경로나 열기(설정 오타 하나로 vault 원문이 화면에 나옴)
- 결과: 원장이 바뀌면 다음 GET에 바로 반영된다. 보이는 탭만 부르므로(ADR-010) 디스크 읽기는 탭을 보는 동안만 생긴다. 대가는 GET마다 여러 파일을 여는 것인데 레포 수가 한 자릿수라 문제 없다고 보지만 `미측정: 레포 5개로 GET /competency/workflow 응답 시간, 구현 step에서`. 원장 형식이 바뀌면 파서가 못 읽고 "형식 확인 필요" 행으로 나온다

## ADR-010 탭마다 GET 하나, 화면은 보이는 탭만 부른다

- 상태: 제안
- 맥락: 탭이 6개로 늘면 15초 폴링 한 번에 원장 전부를 여는 구조는 낭비다. 한 엔드포인트에 다 담으면 느린 원장 하나가 전체 탭을 늦춘다
- 결정: 엔드포인트는 `GET /review` · `/competency/workflow` · `/competency/proactive` · `/competency/fullstack` · `/weekly` · `/repo-health`. 화면은 탭을 열 때 한 번, 열려 있는 동안 15초마다 그 탭 것만 부른다(3역량은 현재 서브 탭 것만). 상단 탭은 트랙 · 판정 · 복습함 · 3역량 · 주간 롤업 · 레포 건강도 6개이고 3역량 안에 서브 탭 3개를 둔다. 기존 `/sessions` · `/judgments`는 그대로
- 결정 주체: AI 추천 수용 (PRD 남은 ⚠️ 엔드포인트 이름 · UI 배치)
- 대안: `/api/overview` 하나에 전부(느린 원장 하나가 모든 탭을 늦춤 · 안 보는 탭의 원장도 읽음) · 3역량을 탭 3개로 펼침(PRD가 정한 "3역량 안에 서브섹션 3개"와 어긋남)
- 결과: 탭 단위로 실패가 갈린다(한 탭이 깨져도 나머지가 산다). 대가는 엔드포인트 6개와 화면의 탭별 폴링 관리 코드

## ADR-011 복습 끝 · 공유 끝 마킹은 서버가 쓴다

- 상태: 제안
- 맥락: 11-03 ADR-006은 반영(`applied`)을 지휘 세션이 `desk.py`로 쓰게 했다. 복습 끝과 공유 끝은 사람이 화면에서 누르는 행동이고 세션이 개입할 이유가 없다. 세션을 거치면 토큰을 쓰고 한 단계가 늘어난다
- 결정: `POST /review/done {repo, key}` → `~/.jtwjs-desk/review/<레포>/<key>.done.json`, `POST /share/shared {repo, id}` → `~/.jtwjs-desk/share/<레포>/<id>.shared.json`. 보호는 ADR-004 그대로. 항목 키는 작업 `phase-<task>`, 카드 `card-<제목 sha1 앞 8자>`. `/review`는 `done` 마킹이 있는 항목을 뺀다. 공유 `.md` 파일은 세션이 쓰고(claude-harness sdd REFLECT) 서버는 `.md`를 쓰거나 지우지 않는다
- 결정 주체: AI 추천 수용 (PRD `desk-transparency-storage`의 `.shared.json` 패턴을 복습함에도 적용)
- 대안: 복습 끝도 지휘 세션이 `desk.py`로 마킹(사람이 누르고 세션이 받아 쓰는 왕복, 토큰 사용) · 원장(`_learn/inbox.md`)에 직접 반영 기록(원장을 desk가 쓰게 됨, ADR-009 위반)
- 결과: 단순하고 토큰이 안 든다. 서버가 쓰기 주체인 파일이 pick에 이어 둘 더 늘어난다. 한계: 카드 제목을 고치면 키가 바뀌어 `done`이 풀리고 다시 뜬다. 같은 제목의 카드 둘은 하나로 센다(inbox 규칙이 같은 제목은 상태만 올리므로 정상 경로에서는 안 생긴다)

## ADR-012 claude-harness 쪽 구현과 desk가 기대하는 모양 (구현은 claude-harness에서)

- 상태: 제안
- 맥락: 이 기능은 jtwjs-desk(읽는 쪽)와 claude-harness(쓰는 쪽) 두 레포에 걸친다. PRD `desk-docs-location`: 설계는 여기 한 곳, 구현은 하네스에서. 읽는 쪽이 쓰는 쪽 모양을 모르면 파서가 추측 위에 선다
- 결정: 하네스 레포의 구현은 별도 sdd 작업으로 한다. desk는 아래 모양을 기대하고, 모르는 키는 무시하고 빠진 키는 비어 있는 것으로 읽는다(둘 다 desk 쪽에서 관대하게)
  - `phases/{task}/index.json`: `"reflect": {"understanding_check": "done" | "skipped"}` 필드 추가. 기존 필드 · `sdd_runner.py` · `task-observer` · `harness-run` 동작은 변하지 않아야 한다
  - `daily_hub.py --json <path>`: `~/.claude/daily/YYYY-MM-DD.json`(HTML과 같은 폴더 · 같은 날짜 이름)에 `{"date", "sessions": N, "stuck": N, "repos": [{"name", "commits": N, "progress": ["phase 진행줄"]}], "cards": [{"summary"}]}`. `prompts` · `title` · `cwd` 원문은 넣지 않는다(PRD `desk-daily-hub-json-no-prompts`)
  - `sdd` DESIGN 끝에 "스피드 제안 판정카드 작성"(`area: speed-suggestion`), REFLECT 「회고 1장」 끝에 "투명성 공유파일 작성"(`~/.jtwjs-desk/share/<레포>/<id>.md`) 단계를 문서화
- 결정 주체: AI 추천 수용 (PRD `desk-docs-location`, `desk-reflect-skip-field`)
- 대안: 하네스에도 별도 설계 세션(결정이 두 곳으로 흩어짐) · desk가 하네스 파일을 직접 고침(경계 위반, 하네스는 desk를 모르고 desk는 하네스를 고치지 않는다)
- 결과: desk 구현과 하네스 구현을 독립적으로 시작할 수 있다. 일간 JSON이 아직 없는 동안 주간 롤업은 "없음"으로 센다. 위험: 위 JSON 모양은 이 문서가 처음 정한 것이라, 하네스 step에서 바꾸면 desk 파서(`desk/rollup.py`)를 같이 고쳐야 한다. 그때 이 ADR을 먼저 고친다

## ADR-013 원장 형식은 확인한 것은 확정, 못 본 것은 가정형 파서

- 상태: 제안
- 맥락: PLAN(2026-11-11)에서 원장 형식을 실제로 확인했다. `observations.md`는 task-observer 스킬 정의로, `_learn/inbox.md`는 파일 머리의 카드 형식으로, score 경로는 `ai-readiness-cartography` 스킬과 하네스 훅으로 확인함. vault `1_MyBrain/brain/friction/` 폴더는 이 머신에 없어 행 형식을 못 봤다
- 결정:
  - `observations.md`: `## 열린 것` 표(패턴 · 종류 · 횟수 · 마지막 · 근거)를 읽는다. `## 닫힌 것`은 무시
  - `inbox.md`: `## YYYY-MM-DD · 제목` 카드 하나씩, 줄 `종류` · `상태` · `vault:`를 읽는다. 종류 `직무`는 PRD 범위 밖이라 복습함 · 풀스택에서 뺀다(PRD는 기술 · 도메인 · 막힌질문). 카드 영역 분류는 `learning-level.md` §2의 경로 신호를 카드의 `이 레포 어디` 경로에 적용하고, 못 가르면 `미분류`로 둔다
  - friction: 표 형식을 가정한다. `상태` 칸이 `열림` · `보류`이고 `횟수` 칸이 있는 행만 읽고, 못 읽는 행은 "형식 확인 필요" 행으로 낸다. 파일이 없으면 "파일 없음"(ADR-009)
  - score: `.claude/reports/<날짜>/` → `docs/` → `.claude/` → 레포 루트 순서로 `ai-readiness-score.json`을 찾는다(앞에서 찾으면 멈춤, reports는 날짜 폴더 중 가장 최근). 읽는 키는 `total` · `grade`. 채점일은 reports면 날짜 폴더 이름, 아니면 파일 수정시각
- 결정 주체: Finn (friction 파서를 가정형으로 가기, 옵션 A 선택). 나머지는 AI 추천 수용
- 대안: friction을 이번 범위에서 빼기(AI워크플로우 수용 조건 하나가 안 닫힘) · 경로 · 형식을 Finn이 확인한 뒤 진행(step 시작이 막힘)
- 결과: step이 막히지 않는다. 위험: friction 실제 형식이 가정과 다르면 탭에 "형식 확인 필요" 행만 나오고 파서를 고쳐야 한다. 그 수정은 `desk/ledger.py` 한 곳이다. 채점일을 수정시각으로 읽는 경로는 체크아웃 · 복사로 시각이 바뀌면 틀릴 수 있다
