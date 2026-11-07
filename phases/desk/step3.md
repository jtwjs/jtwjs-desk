# Step 3: desk-script

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-2026-11-03/{PRD,ARCHITECTURE,ADR}.md` — 특히 ADR-006(desk 스크립트 명령·질문/선택 형식) · PRD 결정 표 `desk-prune-days`(기본 7일) · `desk-repick`
- `desk/paths.py`·`desk/atomic.py`·`desk/validate.py`(step 1 산출물)
- `.claude/rules/testing.md` §0·§1(BDD 3계층)

## 작업

`scripts/desk.py` — 지휘가 Bash로 직접 부르는 CLI(ADR-006). **`scripts/`는 `desk/`만 import한다**(ARCHITECTURE 경계 — `hooks/`·`page/`를 import하지 않는다). `argparse`로 서브커맨드 4개를 둔다.

- `cmd_ask(repo: str, raw: str) -> int`
  - `raw`가 `-`면 stdin에서, 아니면 파일 경로에서 JSON을 읽는다.
  - `desk.validate.validate_ask`로 검증. 어긴 필드가 있으면 그 목록을 stderr에 출력하고 `1`.
  - 같은 `id`의 질문 파일이 **이미 있으면 거절**(ADR-001 "같은 id로 다시 ask하면 거절한다, 덮어쓰지 않는다") — stderr에 이유, `1`.
  - 통과하면 `createdAt=time.time()`을 더해 `desk.paths`의 inbox 경로(`<repo>/<id>.json`)에 `desk.atomic.write_json_atomic`으로 쓴다. 성공 시 `0`.
- `cmd_picks_new(repo: str | None, since: float | None) -> int`
  - `repo`가 없으면 inbox 전체 레포를 훑는다. 각 `<id>.pick.json`을 읽어, **같은 id의 `.applied.json`이 없는 것만** 후보로 삼는다(ADR-006).
  - `since`가 있으면 `pick.at > since`인 것만(다시 고른 선택은 `at`이 갱신돼 다시 걸린다 — PRD `desk-repick`).
  - 후보마다 `{"repo":..., "id":..., **pick}` 한 줄 JSON을 stdout에 출력(한 줄 = 한 판정). 후보 0개면 아무것도 출력하지 않고 `0`.
- `cmd_applied(repo: str, id: str, issue: str | None, follow_up: list[str]) -> int`
  - 대상 질문 파일(`<id>.json`)이 없으면 stderr에 이유, `1`(아직 묻지도 않은 판정을 반영 처리할 수 없다).
  - `{"appliedAt": time.time(), "issue": issue, "followUp": follow_up}`을 `<id>.applied.json`에 원자적으로 쓴다. 이미 있으면 덮어쓴다(재반영은 막지 않음 — 반영 자체를 취소할 방법이 없어서다). `0`.
- `cmd_prune(days: int = 7) -> int`
  - 기본값 7(PRD `desk-prune-days`). 모든 레포의 `<id>.applied.json`을 훑어 `now - appliedAt > days*86400`인 것의 **세 파일(`<id>.json`·`<id>.pick.json`·`<id>.applied.json`, 없는 것은 무시)을 지운다.** 지운 개수를 stdout에 한 줄(`f"pruned {n}"`)로 보고. `0`.
- `main(argv: list[str]) -> int`: 서브커맨드 라우팅. 알 수 없는 커맨드·인자 오류는 argparse 기본 동작(stderr + `2`)에 맡긴다.

### 🔴 CRITICAL (CLAUDE.md에서 인용 — 이 step에 직결)

- 사람 이름·vault 원문·세션 대화 원문을 질문·선택·반영 파일에 넣지 않는다. `validate_ask`가 막는 필드 밖에 자유 텍스트 필드(`question`·`why`·`note` 등)가 있으므로, **이 스크립트 자체가 내용을 검사하진 않는다** — 쓰는 사람(지휘)이 지키는 규칙이다. 코드에 예시·테스트 데이터를 넣을 때도 가짜 역할명만 쓴다.

## Acceptance Criteria

- `.claude/harness.json`의 `verify.test` 통과.
- 왕복 테스트: `ask` → 임시 inbox에 파일 생성 확인 → 가짜 `.pick.json`을 직접 떨어뜨리고 `picks --new`가 그 한 줄을 출력하는지 확인 → `applied` 실행 후 같은 `picks --new`가 더 이상 그 id를 출력하지 않는지 확인 → `prune --days 0`으로 즉시 세 파일이 지워지는지 확인.
- `ask`에 같은 `id`를 두 번 보내면 두 번째는 `1`과 거절 메시지(stderr).

## 검증 절차

1. 위 AC 명령·시나리오 실행.
2. 아키텍처 체크리스트: `scripts/desk.py`가 `hooks/`·`page/`를 import하지 않는가. 모든 쓰기가 `desk.atomic.write_json_atomic`을 거치는가(직접 `open(...).write` 없는가).
3. 결과를 `phases/desk/index.json` step 3에 기록.

## 금지사항

- hook 우회 · 자동 생성물 직접 수정 · 요청 범위 밖 수정 · 테스트 파일 수정(구현 커밋에서) 금지.
- `hooks/`·`page/`를 import하지 않는다. 질문·선택 형식(ADR-006)을 이 step에서 바꾸지 않는다 — 바뀌면 ADR을 먼저 고친다.
