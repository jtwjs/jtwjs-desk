# Step 2: signal-config

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-hypothesis-gate-2026-11-12/{PRD,ARCHITECTURE,ADR}.md` — ARCHITECTURE 「원장 경로 설정 키」 · 「아직 열린 것」(연속 기준 횟수의 설정 키)
- `.claude/rules/testing.md` §0 · `.claude/rules/non-obvious-patterns.md`
- `desk/config.py` — `load_config`의 기본 dict(`routine_questions` · `trends_items` 등)와 문자열 경로 키를 읽는 `for key in (...)` 블록. 새 키는 같은 모양으로 더한다
- 기존 설정 테스트(`tests/` 안에서 `load_config`를 부르는 파일)를 찾아 같은 방식으로 쓴다

## 작업

**`desk/config.py`만 고친다**(+ 테스트 파일 한 개: `tests/test_desk_config_hypothesis.py`).

- 키 하나: **`hypothesis_ledger`** (문자열 경로, 빈 문자열은 설정 없음 = `None`). 기본 dict에 `None`으로 넣고, 기존 문자열 경로 키 블록의 키 목록에 더한다. 타입이 문자열이 아니면 기존 키와 같이 `errors`에 `"hypothesis_ledger 타입 오류"`를 넣는다
- 키 하나 더: **`hypothesis_streak_threshold`** (양의 정수). 기본값 `None` = 재요구 판정을 하지 않는다. 정수가 아니거나 1 미만이면 `None`으로 두고 `errors`에 `"hypothesis_streak_threshold 타입 오류"`. 이 키의 이름과 「기본은 판정 안 함」은 AI 제안이다(ARCHITECTURE 열린 것: Finn이 기준 기간 뒤 값을 정한다). 값을 지어 넣지 않는다
- `bool`은 정수로 보지 않는다(`True`가 1로 읽히지 않게)

### 🔴 CRITICAL

- 사람 이름 · vault 원문을 코드와 테스트에 넣지 않는다(가짜 경로 `/tmp/ledger.jsonl` 같은 값만)
- `load_config`는 서버가 요청마다 부른다 — 밖으로 예외를 던지지 않는 기존 구조를 깨지 않는다

## Acceptance Criteria

- `verify.test` 통과(기존 설정 테스트가 깨지지 않는다)
- 테스트가 단언한다: 키 없음 → 둘 다 `None` · 경로 문자열 → 그대로 · 빈 문자열 → `None` · 숫자가 들어간 경로 → `error`에 타입 오류 · 임계값 2 → 2 · 임계값 `"2"`/`0`/`True` → `None` + error

## 검증 절차

1. AC 명령을 실제 실행한다.
2. 기존 키(`trends_*` 등)의 동작이 안 바뀌었는지 기존 테스트 통과로 확인한다.
3. 결과를 `phases/desk-hypothesis-gate/index.json`의 step 2에 기록(성공 `completed` + `summary` / 실패 `error` / 차단 `blocked`).

## 금지사항

- hook 우회(`--no-verify`) · 요청 범위 밖 수정 · **테스트 파일 수정**(구현 단계에서) 금지
- `desk/config.py`와 위 테스트 파일 밖은 고치지 않는다. 쌓기만 하는 기록은 고치지 않는다
