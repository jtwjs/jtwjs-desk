# Step 1: signal-core

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-hypothesis-gate-2026-11-12/{PRD,ARCHITECTURE,ADR}.md` — PRD 「결정」(원장 필드 · 연속 · 리셋·건너뜀) 과 수용 조건 표의 이름 11개 중 영역 건수·적중 · 가설 먼저 · 이유 없이 수락 · 연속 값 · 재요구 상태 · 건너뜀 건수 · 식별 없는 줄 · 깨진 줄 · 원문 없음
- `.claude/rules/testing.md` §0 · `.claude/rules/non-obvious-patterns.md`
- `desk/trends.py` — 따라야 할 패턴: JSONL을 줄 단위로 읽어 깨진 줄은 건너뛰고 개수를 함께 돌려주는 순수 함수 구조
- `tests/test_desk_trends.py` — 테스트 모양 참고(unittest, 가짜 데이터)

## 작업

**`desk/signal.py` 하나만 새로 만든다**(순수 함수만. 파일 읽기·서버·설정은 이 step 밖). 테스트는 `tests/test_desk_signal.py`.

원장 한 줄(JSON 객체)의 칸은 PRD 「원장 필드 추가」 행이 정본이다. 누락 키는 빈 값으로 읽는다. 맡김 줄: `ts, repo, task, gate, area, hyp, rec, acc, why, rebut, skip`. 적중 줄: `{ref, hit, by}` — `hit`은 `right|partial|wrong`, 같은 `ref`가 여러 줄이면 **마지막 줄만** 센다. 영문 값은 desk가 맞음 · 부분 · 틀림으로 매핑한다(응답 키는 아래 계약).

시그니처:

- `parse_ledger(text: str) -> (rows: list[dict], broken: list[dict])` — 줄마다 JSON 파싱. 객체가 아니거나 파싱에 실패한 줄은 `{"line": 줄번호(1부터), "reason": "JSON 아님" | "객체 아님"}`으로 `broken`에 넣고 건너뛴다. 빈 줄은 무시. **수정 후보는 값이 하나로 정해질 때만** 적는다: `broken` 항목에 `"fix"` 키를 두되 이번 step에서는 정해진 경우를 만들지 않고 키 자체를 생략한다(ADR의 깨진 줄 결정)
- `compute_signal(rows, broken, streak_threshold=None) -> dict` — 아래 계약의 dict를 돌려준다

**계약(이 문서가 정본, step 3의 응답이 이 dict를 그대로 싣는다):**

```
{
  "areas": {                      # 키는 FE, BE, infra, domain 네 개 고정(없어도 0으로 채움)
    "FE": {"count": n, "right": n, "partial": n, "wrong": n, "pending": n,
           "acc_no_reason": {"n": n, "m": n, "pct": int|null}},
    ...
  },
  "unknown_area": n,              # area가 unknown이거나 비어 있는 의미 있는 줄 수(카드 4장에는 없지만 합계에 든다)
  "hyp_first": {"n": n, "m": n, "pct": int|null},
  "acc_no_reason": {"n": n, "m": n, "pct": int|null},
  "streak": n,
  "reasked": bool,                # 재요구 켜짐. streak_threshold가 None이면 항상 false
  "skipped": n,
  "no_ident": n,                  # (repo, task) 식별이 비어 연속에서 제외된 줄 수
  "broken": [ {"line": n, "reason": str}, ... ],
  "meaningful": n,                # 의미 있는 줄 수
  "empty": bool                   # 맡김 줄이 0건
}
```

`pct`는 `m == 0`이면 `null`, 아니면 `round(100 * n / m)`(정수). `null`을 0으로 바꾸지 않는다(기록 없음과 0%는 다르다).

계산 규칙(PRD 「결정」 · 수용 조건과 같다):

- **의미 있는 줄** = `gate` · `hyp` · `rec` 중 하나라도 채워진 맡김 줄. `areas[x].count`는 area가 x인 의미 있는 줄의 수(입력 건수)
- **적중**: 적중 줄의 `ref`로 원 맡김 줄을 찾아 그 줄의 `area`에 센다. `ref`가 어느 줄도 가리키지 않으면 건너뛰고 개수에 넣지 않는다. 가설 입력 예(`hyp` true)인데 적중 줄이 없는 줄은 `pending`
- **가설 먼저**: 분자 = `hyp` true인 줄, 분모 = 의미 있는 줄. 게이트에서 건너뛴 줄(`gate`만 채워짐)도 분모에 든다
- **이유 없이 수락**: 분모 = `rec` true이고 `gate`가 있는 줄(`gate=null` 줄은 분모·분자에서 뺀다), 분자 = 그중 `acc` true AND `why` false. 영역별 값도 같은 규칙으로 영역 안에서 센다
- **연속 · 건너뜀 · 재요구**는 `(repo, task)` 쌍 단위로 원장 순서대로 센다. 연속: 이유 없이 수락(위 분자 조건)이면 +1, 이유를 쓴 줄(`why` true)이면 0, `(repo, task)`가 바뀌면 0. **task가 null이거나 비어 있는 줄은 세지도 끊지도 않는다**(`no_ident`로만 센다). 건너뜀: `skip` true인 줄 수
- **재요구**: `streak_threshold`가 정수이고 연속이 그 값에 닿으면 켜짐. 켜진 뒤 `why`만 쓴 줄이 와도 켜진 채 유지(연속 값만 0). 같은 `(repo, task)`에서 `hyp` true 줄과 `rebut` true 줄이 순서 무관으로 둘 다 나오면 둘째 줄에서 꺼짐. 켜진 뒤 `(repo, task)`가 바뀌면 모은 것을 버린다
- **원문 없음**: 이 함수의 출력에 `hyp`·`why` 등 원문 칸의 값을 싣지 않는다. 입력 줄에 원문 문자열이 섞여 있어도 출력은 숫자 · 불리언 · 줄 번호 · 고정 이유 문구뿐이다

### 🔴 CRITICAL (CLAUDE.md 그대로)

- 사람 이름 · vault 원문 · 세션 대화 원문을 코드와 테스트 샘플에 넣지 않는다. 테스트의 가짜 원장은 `repo-a` · `task-1` 같은 가짜 값만 쓴다
- 외부 패키지를 들이지 않는다(표준 라이브러리만)
- desk는 이 기능에서 원장을 쓰지 않는다. 이 모듈에 파일 쓰기를 넣지 않는다

## Acceptance Criteria

- `.claude/harness.json`의 `verify.test`(`python3 -m unittest discover -s tests`) 통과
- 테스트가 PRD 수용 조건 표의 아래 이름을 각각 한 개 이상 단언한다: 영역 건수·적중(같은 `ref` 마지막 줄 · 판정 전 포함) · 가설 먼저(의미 없는 줄 섞어도 같음, 의미 있는 줄 0이면 `pct` null) · 이유 없이 수락(`gate=null` 섞어도 같음, 분모 0이면 null) · 연속 값 · 재요구 상태(기준 2) · 건너뜀 건수 · 식별 없는 줄(a 수락, a 수락, 빈 줄, a 수락 → 3) · 깨진 줄 · 원문 없음
- `typecheck` · `lint` · `build`는 이 레포에 없다

## 검증 절차

1. AC 명령을 실제 실행한다.
2. 계약의 키 이름이 위 dict와 글자까지 같은지 대조한다(step 3 · 4가 이 키를 읽는다).
3. 결과를 `phases/desk-hypothesis-gate/index.json`의 step 1에 기록: 성공 → `completed` + `summary`(1~2줄) / 실패 → `error` + `error_message` / 차단 → `blocked` + `blocked_reason`.

## 금지사항

- hook 우회(`--no-verify`) · 자동 생성물 직접 수정 · 요청 범위 밖 수정 · **테스트 파일 수정**(구현 단계에서) 금지
- `desk/signal.py` 와 `tests/test_desk_signal.py` 밖의 파일은 고치지 않는다(설정 · 서버 · 화면은 뒤 step). 쌓기만 하는 기록(`docs/`의 지난 설계 · ADR 본문 · `phases/*/`)은 고치지 않는다
