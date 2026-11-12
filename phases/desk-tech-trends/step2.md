# Step 2: trends-config

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-tech-trends-2026-11-12/{PRD,ARCHITECTURE,ADR}.md` — ADR 「경로는 설정 키 세 개로 받는다」(비어 있으면 "설정 없음", `trends_marks`가 비면 토글만 막힘)
- `.claude/rules/testing.md` §0 · §1 · §2 · `.claude/rules/non-obvious-patterns.md`
- `desk/config.py` — 특히 `routine_questions` · `routine_answers` 키 처리(`load_config()` 기본값 · 경로 변환 · 빈 문자열 → None · 문자열 아님 → None + `error`에 `'<키> 타입 오류'` · conductor 폴백은 None). **같은 규칙을 따른다**
- `tests/test_desk_config_routine.py` — 이 step의 테스트가 따라 할 스타일

## 작업

러너가 이 step을 테스트 먼저 → 구현으로 한 호출에서 돌린다. **`desk/config.py`와 새 테스트 파일 `tests/test_desk_config_trends.py`만** 만든다/고친다.

- `load_config()`가 돌려주는 dict에 `trends_items` · `trends_reads` · `trends_marks` 세 키를 더한다. 값은 `Path | None`, 기본 None, 빈 문자열은 None, 문자열이 아니면 None + `error`에 `'<키> 타입 오류'`(`routine_*`와 같은 규칙, `routine_*` 코드는 고치지 않는다)
- conductor 폴백 경로에서도 세 키는 None이다
- 기존 키의 동작은 바뀌지 않는다

### 🔴 CRITICAL

- 경로 값을 코드에 박지 않는다. 사람 이름 · vault 원문 경로를 테스트 픽스처에 넣지 않는다(`DESK_CONFIG`를 임시 디렉터리로 돌리고 가짜 경로만 쓴다)

## Acceptance Criteria

- `.claude/harness.json`의 `verify.test` 통과. `typecheck` · `lint` · `build`는 이 레포에 없다
- `tests/test_desk_config_trends.py` 단언: 세 키가 있으면 `Path`로 온다 · 키 없음/빈 문자열이면 None · 문자열 아닌 값(숫자 · 리스트)이면 None + `error`에 키 이름이 든 타입 오류 문구 · conductor 폴백에서 None · 세 키가 서로 독립(하나만 설정해도 나머지는 None) · 기존 `routine_*` 테스트가 그대로 통과
- 엣지 5축: 빈 값 · 비정상 입력(타입 오류) · 실패 경로(config 파일 없음) · 상태 전이(해당 없음) · 동시성(해당 없음)

## 검증 절차

1. AC 명령을 실제 실행한다.
2. `ARCHITECTURE.md` 결정 표의 「설정」 행과 대조.
3. 결과를 `phases/desk-tech-trends/index.json`의 step 2에 기록: 성공 → `completed` + `summary`(1~2줄) / 실패 → `error` + `error_message` / 차단 → `blocked` + `blocked_reason`.

## 금지사항

- hook 우회(`--no-verify`) · 자동 생성물 직접 수정 · 요청 범위 밖 수정 · **테스트 파일 수정**(구현 단계에서) 금지
- 이 step이 맡지 않은 파일은 고치지 않는다. 쌓기만 하는 기록(`docs/`의 지난 설계 · ADR 본문 · `phases/*/`)은 고치지 않는다
