# Step 1: trends-core

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-tech-trends-2026-11-12/{PRD,ARCHITECTURE,ADR}.md` — ADR는 번호가 아직 없어 제목으로 부른다(동향은 wiki가 파일로 · 잔디 칸은 글의 날짜 기준 · 읽음은 멱등 POST · 북마크는 별도 이벤트 파일 · 설정 키 세 개). 읽기 규약은 `docs/desk-2026-11-11/ADR.md`의 ADR-009(GET은 읽기만)
- `.claude/rules/testing.md` §0 · §1 · §2(엣지 5축은 축마다 "해당 없음"까지 적는다) · `.claude/rules/non-obvious-patterns.md`
- `desk/routine.py` — **같은 모양**으로 만든다(JSON Lines 파서 · 마지막 줄이 이김 · 깨진 줄 수 · 순수 함수). 이 step은 `routine.py`를 고치지 않는다 · `tests/test_desk_routine.py` — 테스트 스타일

## 계약 (이 phase 전체가 같은 값을 쓴다 — 코드의 `desk/trends.py` 상수와 docstring이 정본이 된다)

- **동향 줄**(wiki가 동향 파일에 한 줄씩 씀): 필수 `id` · `date`(`YYYY-MM-DD`) · `title` · `url` · `summary` 전부 비어 있지 않은 문자열. 같은 `id`가 여러 줄이면 **마지막 줄이 이긴다**. 필수 필드가 없거나 형식이 틀린 줄은 "깨진 줄"이다
- **읽음 줄**(desk가 읽음 파일에 덧붙임): `{"id": str, "at": 문자열}`. 같은 id가 여럿이어도 읽음은 한 번이다
- **북마크 줄**(desk가 북마크 파일에 덧붙임): `{"id": str, "on": bool, "at": 문자열}`. 글마다 **마지막 줄이 현재 상태**다
- 깨진 줄은 건너뛰고 개수를 센다. 모르는 필드는 무시한다
- **오늘 / 지난 / 미래**: 오늘은 호출자가 넘긴 `today: date`(서버가 `_today()`를 넘긴다). `date == today` 오늘 글, 앞선 날짜는 지난 글, **미래 날짜 글은 어디에도 세지 않고 보이지 않는다**(AI 가정, 반려 가능)
- **글 한 건의 응답 모양**: `{"id","date","title","url","summary","read": bool,"bookmarked": bool}`

## 작업

러너가 이 step을 테스트 먼저 → 구현으로 한 호출에서 돌린다. **새 파일 `desk/trends.py`와 `tests/test_desk_trends.py`만** 만든다. 이 step은 순수 함수만 둔다(파일 I/O · 락 없음, 그건 step 3).

- `parse_items(text: str) -> tuple[dict[str, dict], int]`: id → 마지막 줄 dict(파일에 처음 나온 순서 유지), 깨진 줄 수
- `parse_reads(text: str) -> tuple[set[str], int]`: 읽은 id 집합, 깨진 줄 수
- `parse_marks(text: str) -> tuple[dict[str, bool], int]`: id → 마지막 줄의 `on`, 깨진 줄 수
- `split_items(items, reads, marks, today) -> dict`: `{"today": [글...], "past_unread": [글...]}`. 오늘 글은 파일 순서, 지난 안 읽은 글은 **날짜 내림차순**(같은 날짜는 파일 순서). 미래 글은 제외. 글 모양은 위 계약
- `heatmap(items, reads, today, days=365) -> list[dict]`: `today`를 끝으로 `days`일치(오래된 날부터), 칸마다 `{"date": "YYYY-MM-DD", "total": 그날 글 건수(자르지 않음), "read": 그날 글 중 읽은 distinct id 수를 3으로 자른 값}`. **글의 `date`로 묶는다**(지난 날 글을 읽으면 그 글 날짜 칸이 오른다). 읽음 집합에 있어도 동향에 없는 id는 세지 않는다
- `bookmark_list(items, reads, marks) -> list[dict]`: 마지막 줄이 `on: true`인 글 중 동향에 있는 것만, 날짜 내림차순. 글 모양은 위 계약(`bookmarked`는 true)
- `unread_count(items, reads, today) -> int`: 미래 글을 뺀, 동향에 있고 읽음 집합에 없는 글 수
- 상수 `HEATMAP_DAYS = 365`, `HEATMAP_MAX = 3`

### 🔴 CRITICAL (CLAUDE.md · 설계문서에서 그대로)

- 사람 이름 · vault 원문 · 세션 대화 원문을 레포와 상태 파일에 넣지 않는다. 테스트 픽스처는 지어낸 글(`샘플 글 A` · `https://example.com/a` 같은 가짜)이다
- 외부 패키지를 들이지 않는다(표준 라이브러리만)
- 읽음 · 북마크는 서로 독립이다. 북마크가 잔디 건수를 바꾸지 않는다

## Acceptance Criteria

- `.claude/harness.json`의 `verify.test`(`python3 -m unittest discover -s tests`) 통과. `typecheck` · `lint` · `build`는 이 레포에 없다
- `tests/test_desk_trends.py` 단언: 정상 파싱 · 같은 id 마지막 줄 승 · 깨진 줄(JSON 아님 · 필드 누락 · 날짜 형식 오류) 건너뜀과 개수 · 오늘 3건 분리와 읽음 여부 · 지난 안 읽은 글 날짜 내림차순 · 미래 글 제외 · 잔디 365칸 길이와 끝 날짜 = today · **지난 날 글을 읽으면 그 글 날짜 칸의 read가 오른다** · 같은 id 중복 읽음은 1로 센다 · 동향에 없는 id는 안 센다 · 4건 읽어도 read는 3 · total은 자르지 않는다 · 북마크 마지막 줄이 이김(켬 → 끔 → 켬) · 북마크가 읽음/잔디에 영향 없음 · `unread_count`
- 엣지 5축: 빈 값(빈 텍스트) · 비정상 입력(깨진 줄) · 실패 경로(해당 없음: 순수 함수) · 상태 전이(북마크 켬/끔) · 동시성(해당 없음: 순수 함수)

## 검증 절차

1. AC 명령을 실제 실행한다.
2. `docs/desk-tech-trends-2026-11-12/ARCHITECTURE.md`의 결정 표(잔디 계산 · 북마크 · 모듈) 대조. `desk/trends.py`가 `page/` · `scripts/` · `hooks/`를 import하지 않는지 확인.
3. 결과를 `phases/desk-tech-trends/index.json`의 step 1에 기록: 성공 → `status:"completed"` + `summary`(1~2줄, 다음 step이 쓸 함수 이름과 반환 모양 포함) / 실패 → `status:"error"` + `error_message` / 차단 → `status:"blocked"` + `blocked_reason`.

## 금지사항

- hook 우회(`--no-verify`) · 자동 생성물 직접 수정 · 요청 범위 밖 수정 · **테스트 파일 수정**(구현 단계에서) 금지. `desk/`는 `page/` · `scripts/` · `hooks/`를 import하지 않는다(의존 방향 `page/` · `scripts/` · `hooks/` → `desk/`)
- 이 step이 맡지 않은 파일은 고치지 않는다(`desk/routine.py` 포함). 쌓기만 하는 기록(`docs/`의 지난 설계 · ADR 본문 · `phases/*/`)은 고치지 않는다
