# Step 2: ledger-learn

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-2026-11-11/{PRD,ARCHITECTURE,ADR}.md` — 특히 ADR-011(항목 키) · ADR-013(inbox 형식 · 영역 분류)
- `_learn/inbox.md` — **카드 형식은 파일 머리의 HTML 주석 안에 있다.** 이 파일의 실제 카드 문장은 테스트 픽스처에 복사하지 않는다(형식만 본다)
- `desk/sort.py` — 순수 함수 모듈의 문체 참고
- `.claude/rules/testing.md` §0 · §5

## 작업

러너가 이 step을 테스트 먼저 → 구현으로 한 호출에서 돌린다. 신규 `desk/ledger.py`(이 step과 step 3이 같은 파일에 함수를 더한다). **모든 함수는 텍스트 · dict를 인자로 받는 순수 함수다 — 파일을 열지 않는다.**

- `parse_inbox(text: str) -> list[dict]`: 카드 하나 = `## YYYY-MM-DD · 제목` 헤딩 아래 줄들. 반환 dict 키: `title · date · kind · status · where · vault · summary`. 줄 이름은 `종류:` `상태:` `이 레포 어디:` `vault:` `요지:`. `vault:` 값이 없으면 `""`
  - 🔴 파일 머리의 `<!-- 카드 형식 … -->` 주석 블록 안의 예시 헤딩(`## YYYY-MM-DD · 제목`)은 카드가 아니다. 주석 안은 건너뛴다
  - `종류:` 줄은 `기술 | 직무 | 도메인 | 막힌 질문` 중 하나로 시작하고 뒤의 `· 출처:` 같은 꼬리는 버린다. `이 레포 어디`는 백틱 안 경로(여러 개면 첫 번째)
  - 헤딩 형식이 안 맞는 `##` 줄은 카드로 세지 않는다
- `review_cards(cards: list[dict]) -> list[dict]`: 종류가 `기술` · `도메인` · `막힌 질문`이고 `vault`가 비어 있는 카드(ADR-013: `직무`는 뺀다)
- `classify_area(where: str, kind: str) -> str`: `"fe" | "be" | "infra" | "domain" | "미분류"`. 종류가 `도메인`이면 `"domain"`. 아니면 `learning-level.md` §2의 경로 신호(아래)를 `where`에 적용, 하나도 안 맞으면 `"미분류"`
  - fe: `*.tsx *.jsx *.vue *.css *.scss` · 경로에 `components/` `pages/` `app/` `apps/web`
  - be: `*.kt *.java *.py *.go *.sql` · `src/main/` `api/` `server/` `controller/` `service/` `repository/` · 마이그레이션
  - infra: `Dockerfile*` `docker-compose*` · `.github/workflows/` · `k8s/` `helm/` `charts/` `terraform/` `*.tf` · `nginx*`
  - 둘 이상 맞으면 fe → be → infra 순으로 먼저 맞는 것(단순 규칙, 여기서 정한다)
- `fullstack_order(cards: list[dict]) -> list[dict]`: 상태 순서 `모름` → `설명 들음` → `내 말로 설명 가능`, 모르는 상태 값은 맨 뒤. 같은 상태끼리는 입력 순서 유지(안정 정렬)
- `card_key(title: str) -> str`: `"card-"` + 제목 UTF-8 sha1의 앞 8자(ADR-011). `phase_key(task: str) -> str`: `"phase-" + task`
- `skipped_phases(indexes: list[tuple[str, dict]]) -> list[str]`: `(task, index.json dict)` 목록에서 `reflect.understanding_check == "skipped"`인 task 이름. `reflect` 키가 없거나 형식이 틀리면 건너뛴다(예외 없음, ADR-012 "빠진 키는 비어 있는 것")

### 🔴 CRITICAL

- 사람 이름 · vault 원문 · 세션 대화 원문을 레포에 넣지 않는다. 픽스처 카드는 지어낸 제목(예: `샘플 개념 A`)과 경로(`src/sample/app.tsx` 같은 가짜)로
- 다른 프로세스를 실행하지 않는다(`subprocess` · `os.system` · `Popen` 금지). `desk/`는 다른 패키지를 import하지 않는다

## Acceptance Criteria

- `verify.test` 통과(`typecheck` · `lint` · `build`는 이 레포에 없음)
- 테스트가 단언: 주석 안 예시 헤딩 무시 · 카드 필드 파싱 · `vault:` 빈 카드만 복습 대상 · `직무` 제외 · 영역 분류(fe/be/infra/domain/미분류 각 1건+) · 상태 순서 · 카드 키가 같은 제목에 같은 값 · `reflect` 없는 index는 건너뜀

## 검증 절차

1. AC 명령 실행.
2. `desk/ledger.py`가 파일을 열지 않는지(`open(` · `read_text` 없음) 확인.
3. 결과를 `phases/desk-ledger-tabs/index.json` step 2에 기록.

## 금지사항

- hook 우회(`--no-verify`) · 요청 범위 밖 수정 · **테스트 파일 수정**(구현 단계에서) 금지. `desk/`의 기존 모듈 · `_learn/inbox.md` · `phases/desk/` · `docs/`는 고치지 않는다. `hooks/`는 이 phase에서 변경하지 않는다.
