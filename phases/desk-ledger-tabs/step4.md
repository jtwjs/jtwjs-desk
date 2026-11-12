# Step 4: rollup

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-2026-11-11/{PRD,ARCHITECTURE,ADR}.md` — 특히 ADR-012(일간 JSON 모양 · 관대한 읽기) · ADR-009
- `desk/sort.py` — 순수 함수 모듈 문체 참고
- `.claude/rules/testing.md` §0 · §5

## 작업

러너가 이 step을 테스트 먼저 → 구현으로 한 호출에서 돌린다. 신규 `desk/rollup.py`. **파일을 열지 않는 순수 함수 둘.**

- `week_dates(today: date, n: int = 7) -> list[str]`: `today`를 포함해 최근 `n`일의 `YYYY-MM-DD` 문자열, 오래된 날부터
- `aggregate(days: list[tuple[str, dict | None]]) -> dict`: `(날짜, 그 날의 일간 JSON 또는 None)` 목록을 합친다. 입력 JSON의 모양은 ADR-012: `sessions`(정수) · `stuck`(정수) · `repos`(`[{name, commits, progress[]}]`) · `cards`(`[{summary}]`)
  - 반환 키: `days`(입력 길이) · `present`(JSON이 있는 날 수) · `missing`(JSON이 `None`인 날짜 목록) · `sessions`(합) · `stuck`(합) · `commits`(레포 commits 합) · `cards`(카드 개수 합) · `projects`(서로 다른 레포 이름 수) · `repos`(`[{name, commits, progress}]` — 같은 이름은 합치고 `commits` 합산, `progress`는 입력 순서대로 중복 제거)
  - 🔴 **관대하게 읽는다**: 키가 없거나 타입이 틀리면 그 값만 0 · 빈 목록으로 본다. 예외를 던지지 않는다(ADR-012)
  - 🔴 **원문 키를 통과시키지 않는다**: 입력에 `prompts` · `title` · `cwd`가 섞여 있어도 반환값 어디에도 나타나지 않아야 한다. 반환은 위 키만 쓰는 **새 dict**로 만든다(입력 dict를 복사해 고치지 않는다). `cards`는 개수만 낸다(요지 문장은 이 모듈이 내보내지 않는다)

### 🔴 CRITICAL

- 대화 원문 · 사람 이름을 레포에 넣지 않는다. 픽스처는 지어낸 값. 원문 키 차단 테스트의 입력 문자열도 가짜(`"SECRET-PROMPT-TEXT"` 같은)로
- 다른 프로세스를 실행하지 않는다(`subprocess` · `os.system` · `Popen` 금지). `desk/`는 다른 패키지를 import하지 않는다. `daily_hub.py`는 실행하지 않는다

## Acceptance Criteria

- `verify.test` 통과(`typecheck` · `lint` · `build`는 이 레포에 없음)
- 테스트가 단언: `week_dates` 길이 · 순서 · 월 경계 · 합계 4종 · 빠진 날이 `missing`에 · 모두 `None`이면 합계 0 · 같은 레포 이름 병합 · 타입이 틀린 입력 무시 · `prompts`/`title`/`cwd` 문자열이 `json.dumps(반환값)`에 없음

## 검증 절차

1. AC 명령 실행.
2. `desk/rollup.py`가 파일을 열지 않는지, 입력을 그대로 반환에 섞지 않는지 확인.
3. 결과를 `phases/desk-ledger-tabs/index.json` step 4에 기록.

## 금지사항

- hook 우회(`--no-verify`) · 요청 범위 밖 수정 · **테스트 파일 수정**(구현 단계에서) 금지. `desk/`의 다른 모듈 · `phases/desk/` · `docs/`는 고치지 않는다. `hooks/`는 이 phase에서 변경하지 않는다.
