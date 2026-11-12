# Step 6: routine-screen

`tdd: false` — 사유: 프레젠테이션 컴포넌트(CSS + DOM 빌더)라 testing.md §0 제외 대상. 서버 계약은 step 4·5 테스트가, 화면과 서버가 이어 붙는 곳은 step 7이 본다.

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-routine-inbox-2026-11-12/{PRD,ARCHITECTURE,ADR}.md` — ADR는 번호가 아직 없어 제목으로 부른다(우편함 JSON Lines 두 파일 · 자동 건너뜀 POST · 미답 배지 nav-counts 합침 · 설정 키 두 개). 기존 읽기 규약은 `docs/desk-2026-11-11/ADR.md`의 ADR-009(GET은 읽기만, 캐시·중간 저장 없음)
- `.claude/rules/testing.md` §0 · §1 · §2(엣지 5축은 축마다 "해당 없음"까지 적는다) · `.claude/rules/non-obvious-patterns.md`
- `page/index.html` — 좌측 메뉴(`#menu`, `.menu-item`, 배지 `span data-badge=judge|review`)와 `selectTab` / `syncMenu`의 탭 전환 · `pageHead` · `el` · `clear` · `screenBox` · `cfgNotes` · `missingTable` · `emptyStateCard` · `decisionCard` · `button` · `inlineNote` · `waitLine` · `postMark` · `renderReview`(복습 화면이 같은 모양: 데이터 받아 그리기) · `fetch...` 폴링 · `/nav-counts` 호출부 · `.claude/design/DESIGN.md`와 `.claude/design/brief.md`(토큰·상태색 규칙 — 색 hex는 `:root`에만) · 판정 화면의 POST 헤더(`X-Desk-Token`)를 만드는 부분

## 계약 (이 phase 전체가 같은 값을 쓴다 — 코드의 `desk/routine.py` 상수와 docstring이 정본이 된다)

- **질문 줄**(wiki가 질문함에 한 줄씩 씀): 필수 `id`(비어 있지 않은 문자열) · `date`(`YYYY-MM-DD`) · `kind`(비어 있지 않은 문자열) · `text`(비어 있지 않은 문자열). 선택 `options`(`[{"key": str, "label": str}, ...]`, 비어 있지 않은 리스트). 같은 `id`가 여러 줄이면 **마지막 줄이 이긴다**. 필수 필드가 없거나 형식이 틀린 줄은 "깨진 줄"이다
- **답 줄**(desk가 답함에 한 줄씩 씀): `id` · `status`(`"answered"` | `"skipped"`) · `value`(answered일 때만, 비어 있지 않은 문자열) · `note`(선택, 문자열) · `at`(`datetime.now().isoformat()` 문자열). 같은 `id`의 **마지막 줄이 이긴다**. 깨진 줄은 건너뛰고 개수를 센다
- **입력 모양 3가지**(서버가 문항마다 `input`으로 내려 준다. 화면은 이 값만 보고 그린다): `"choice"`(선택지 하나 고르기) · `"long"`(여러 줄 글) · `"line"`(한 줄). 판정: `options`가 있으면 `choice` → 없으면 `kind == "복습"`이면 `choice`이고 기본 선택지 `[{"key":"known","label":"알았다"},{"key":"unsure","label":"헷갈림"}]`을 서버가 채워 준다 → `kind == "설명"`이면 `long` → 그 밖(재시험·결정·원칙·모르는 종류)은 `line`. 모르는 종류도 에러가 아니다(PRD 「모르는 종류」)
- **답 검증**: 문항 `id`가 질문함에 있어야 한다. `answered`면 `value`가 비어 있지 않은 문자열이고 길이 상한 이하(상한 값은 `desk/routine.py`의 상수 하나, 4000자 — AI 가정, Finn이 쓰며 바꿀 수 있다). `choice` 입력이면 `value`는 그 문항 선택지의 `key` 중 하나. `note`는 문자열이고 같은 상한 이하
- **상태**: 문항의 마지막 답 줄이 없으면 `unanswered`, 있으면 그 `status`
- **오늘 / 지난**: 오늘은 서버 시계(`page/server.py`의 `_today()`) 기준이다. `date`가 오늘이면 오늘 문항, 오늘보다 앞이면 지난 문항. 미래 날짜 문항은 어디에도 세지 않고 보이지 않는다

## 작업

`tdd: false`는 위 「TDD」 사유 참조. **`page/index.html`만** 고친다. 서버(`page/server.py`)는 step 4·5에서 끝났다 — 서버 응답 모양은 아래 그대로다.

- 새 메뉴 항목 "회고"(이름은 구현자가 정하되 한국어 한 단어) 하나. 3역량 그룹 밖의 최상위 항목이고 기존 항목의 순서 · 이름 · `data-tab`은 안 바꾼다. 배지 `data-badge="routine"`은 `/nav-counts`의 `routine` 숫자를 보인다(숫자가 `null`이면 배지를 숨기고 항목에 툴팁으로 이유를 준다. `errors.routine`). 기존 `judge` · `review` 배지 동작은 그대로다
- 화면이 열릴 때(탭이 선택될 때) **먼저 `POST /routine/rollover`를 한 번 부르고, 끝난 뒤 `GET /routine`을 부른다**(GET은 읽기만이라 건너뜀이 반영되려면 이 순서여야 한다). rollover가 실패해도 GET은 부른다(건너뜀 반영만 못 한 것). 폴링 대상에 이 화면을 넣는지는 기존 화면(복습함)과 같은 규칙을 따른다(보이는 탭만 — ADR-010)
- 응답 `GET /routine`: `{"config", "date", "groups": [{"kind", "items": [{"id","date","kind","text","input","options","state","value","note"}]}], "past": [같은 항목], "broken": n, "missing": [{"what","reason"}]}`. 화면은 **받은 `input` 값만 보고** 그린다(종류 이름으로 분기하지 않는다):
  - `choice` → `options`의 `label`로 버튼 목록(하나만 선택), 선택 뒤 이유 한 줄 입력(선택, `note`)과 저장
  - `long` → 여러 줄 글상자 + 저장
  - `line` → 한 줄 입력 + 저장. 종류 이름이 다섯 종류 밖이면 카드 머리에 종류 이름을 그대로 보인다(PRD 「모르는 종류」)
  - `state`가 `answered`면 저장된 `value`(와 `note`)를 채워 보이고 고쳐서 다시 저장할 수 있다(마지막 줄이 이긴다). `skipped`면 "건너뜀" 상태 라벨 + 점을 보이고 지금이라도 답할 수 있다
- 저장은 `POST /routine/answer`(`id` · `value` · `note`, `X-Desk-Token` 헤더 — 기존 `pick` 제출과 같은 방법). 400 `violations`이면 카드 안에 이유를 보이고 입력을 지우지 않는다. 저장 중 중복 클릭을 막는다
- `missing` 행(설정 없음 / 파일 없음 / 형식 확인 필요)은 이유를 말하는 빈 상태 카드로, `broken > 0`이면 "깨진 줄 n개 건너뜀" 한 줄을 보인다. 문항이 0건이어도 화면은 숨지 않는다(조용히 비어 보이면 안 된다 — ARCHITECTURE의 1순위 위험과 같은 취지)
- 지난 날짜 `past` 문항은 오늘 문항 아래 별도 구역 "지난 건너뜀"으로 보인다
- 색은 `:root` 토큰만 쓰고 hex를 새로 적지 않는다. 서버가 준 문자열은 **`textContent`로만** 넣는다(저장형 XSS 방지 — 이 레포의 기존 규칙). 상태는 색만으로 전하지 않고 라벨 + 점/모양을 같이 둔다

### 🔴 CRITICAL (CLAUDE.md · 설계문서에서 그대로)

- 사람 이름 · vault 원문 · 세션 대화 원문을 레포와 상태 파일에 넣지 않는다. 픽스처는 지어낸 문항(`샘플 문항 A` 같은 가짜)이다
- 훅은 모델 토큰을 쓰지 않는다 — 이 phase는 훅을 건드리지 않는다
- GET은 읽기만 한다(ADR-009). 파일 쓰기는 POST 핸들러에서만 한다

## Acceptance Criteria

- `.claude/harness.json`의 `verify.test`(`python3 -m unittest discover -s tests`) 통과. `typecheck` · `lint` · `build`는 이 레포에 없다
- 테스트 스위트 전체 통과(기존 테스트를 지우지 않는다)
- `grep -nE '#[0-9a-fA-F]{3,8}' page/index.html`의 새 줄(`git diff` 기준)이 `:root` 밖에 0건
- `grep -n 'innerHTML' page/index.html`의 새 줄이 0건
- **미확인으로 남는 것**: 브라우저 렌더. summary에 "미확인: 브라우저 렌더"를 적는다(다음 step이 그것을 잰다)

## 검증 절차

1. AC 명령을 실제 실행한다.
2. 아키텍처 대조 — `docs/desk-routine-inbox-2026-11-12/ARCHITECTURE.md`의 결정 표(자동 건너뜀 · 미답 배지 · 엔드포인트)와 일치하는지, 의존 방향을 지켰는지.
3. `git diff --stat`로 `page/index.html`만 바뀌었는지 확인.
3. 결과를 `phases/desk-routine-inbox/index.json`의 step 6에 기록: 성공 → `status:"completed"` + `summary`(1~2줄, 다음 step이 쓸 함수 이름과 반환 키 포함) / 실패 → `status:"error"` + `error_message` / 차단 → `status:"blocked"` + `blocked_reason`.

## 금지사항

- hook 우회(`--no-verify`) · 자동 생성물 직접 수정 · 요청 범위 밖 수정 · **테스트 파일 수정**(구현 단계에서) 금지. `desk/`는 `page/` · `scripts/` · `hooks/`를 import하지 않는다(의존 방향 `page/` · `scripts/` · `hooks/` → `desk/`)
- 이 step이 맡지 않은 파일은 고치지 않는다(아래 「작업」에 적힌 파일만). 쌓기만 하는 기록(`docs/`의 지난 설계 · ADR 본문 · `phases/*/`)은 고치지 않는다
