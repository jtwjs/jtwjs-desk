# Step 3: trends-write

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-tech-trends-2026-11-12/{PRD,ARCHITECTURE,ADR}.md` — ADR 「읽음은 멱등 POST」 · 「북마크는 별도 이벤트 파일」. 읽기 규약은 `docs/desk-2026-11-11/ADR.md`의 ADR-009
- `.claude/rules/testing.md` §0 · §1 · §2 · `.claude/rules/non-obvious-patterns.md`
- `desk/trends.py` — step 1 산출물(`parse_items` · `parse_reads` · `parse_marks`와 계약 docstring). **같은 파일에 함수를 더한다**(step 1의 함수는 고치지 않는다)
- `desk/routine.py` — `read_text_or_none` · 모듈 수준 락 · `append_answer`(락 안 한 번의 `write` 덧붙이기, 파일 끝 개행 보정). **같은 규약을 따른다.** `desk/atomic.py`는 통째 쓰기용이라 이 step의 덧붙이기에 쓰지 않는다

## 결정 (구현 때 확인하기로 했던 것을 여기서 정한다)

- `routine.read_text_or_none`은 공개 이름이라 `desk/trends.py`가 `from desk import routine`으로 **그대로 부른다**. 헬퍼를 `atomic.py`로 옮기지 않는다(`routine.py`는 고치지 않는다). 락은 `trends.py`가 **자기 모듈 락 하나**를 따로 둔다(회고 락과 섞지 않는다)

## 작업

러너가 이 step을 테스트 먼저 → 구현으로 한 호출에서 돌린다. **`desk/trends.py`(step 1 파일에 추가)와 새 테스트 파일 `tests/test_desk_trends_write.py`만** 만든다. 파일을 읽고 쓰는 얇은 껍질이다.

- 모듈 수준 `threading.Lock` 하나. **읽음 · 북마크 파일에 쓰는 모든 경로가 이 락을 잡는다**(서버가 `ThreadingHTTPServer`라 요청이 겹칠 수 있다)
- `append_line(path: Path, line: dict) -> None`: JSON 한 줄(`ensure_ascii=False`) + `\n`을 **한 번의 `write`**로 덧붙인다(`"a"`, `utf-8`). 디렉터리가 없으면 만든다. 파일 끝이 개행으로 끝나지 않으면 개행부터 쓴다. 락은 호출자가 잡는다(비공개 이름 `_append_line`이어도 된다)
- `record_read(items_path: Path, reads_path: Path, item_id: str, now: datetime) -> str`: 락 안에서 **동향 파일과 읽음 파일을 이 시점에 다시 읽고**, 동향에 없으면 `"unknown_id"`(쓰지 않음), 이미 읽음이면 `"duplicate"`(쓰지 않음), 아니면 `{"id", "at": now.isoformat()}`를 덧붙이고 `"ok"`
- `record_mark(items_path: Path, marks_path: Path, item_id: str, on: bool, now: datetime) -> str`: 락 안에서 동향 · 북마크 파일을 다시 읽고, 동향에 없으면 `"unknown_id"`, **현재 상태(마지막 줄, 없으면 꺼짐)가 `on`과 같으면 `"same"`**(쓰지 않음), 아니면 `{"id", "on", "at"}`를 덧붙이고 `"ok"`
- 쓰기 중 `OSError`는 **잡지 않고 올린다**(서버가 500으로 바꾼다. 조용히 삼키면 읽음이 거짓으로 보인다)
- 읽음과 북마크는 서로의 파일을 읽지도 쓰지도 않는다

### 🔴 데이터 무결성

- 같은 id를 동시에 두 번 읽음 처리해도 줄이 하나다(락 안에서 다시 읽는 것이 핵심)
- 동향 파일(wiki가 쓴다)에는 desk가 절대 쓰지 않는다

### 🔴 CRITICAL

- 사람 이름 · vault 원문 · 세션 대화 원문을 레포와 상태 파일에 넣지 않는다. 픽스처는 가짜 글이다
- GET은 읽기만 한다(ADR-009). 이 step의 쓰기 함수는 POST 핸들러(step 5)만 부른다

## Acceptance Criteria

- `.claude/harness.json`의 `verify.test` 통과. `typecheck` · `lint` · `build`는 이 레포에 없다
- `tests/test_desk_trends_write.py` 단언: `record_read` ok 시 한 줄 · 같은 id 두 번째는 `duplicate`이고 줄이 안 늘어난다 · 동향에 없는 id는 `unknown_id`이고 파일이 안 바뀐다 · 읽음 파일이 없으면 첫 읽음에 만들어진다(디렉터리 없음 포함) · 끝 개행 없는 파일에서 줄이 안 붙는다 · `record_mark` 켬 → 같은 켬은 `same` → 끔 → 켬이 줄 3개 · 동향에 없는 id는 `unknown_id` · 북마크 기록이 읽음 파일을 안 바꾸고 읽음 기록이 북마크 파일을 안 바꾼다 · 쓸 수 없는 경로(예: 파일 자리에 디렉터리)에서 `OSError`가 올라온다 · **동시성: 스레드 여러 개(`threading.Barrier`로 동시 출발)가 같은 id로 `record_read`를 부른 뒤 읽음 파일에 그 id 줄이 정확히 1개이고 `ok`가 정확히 1건이다**(sleep에 의존하지 않는다)
- 엣지 5축: 빈 값(빈 파일) · 비정상 입력(없는 id) · 실패 경로(OSError) · 상태 전이(북마크 켬/끔) · 동시성(위 단언)

## 검증 절차

1. AC 명령을 실제 실행한다.
2. `ARCHITECTURE.md`의 쓰기 엔드포인트 · 북마크 행과 대조. `desk/trends.py`가 `page/` · `scripts/` · `hooks/`를 import하지 않는지, 동향 파일에 쓰는 호출이 없는지 확인.
3. 결과를 `phases/desk-tech-trends/index.json`의 step 3에 기록: 성공 → `completed` + `summary`(1~2줄, 함수 이름과 반환 값 포함) / 실패 → `error` + `error_message` / 차단 → `blocked` + `blocked_reason`.

## 금지사항

- hook 우회(`--no-verify`) · 자동 생성물 직접 수정 · 요청 범위 밖 수정 · **테스트 파일 수정**(구현 단계에서) 금지. `desk/`는 `page/` · `scripts/` · `hooks/`를 import하지 않는다
- 이 step이 맡지 않은 파일은 고치지 않는다(`desk/routine.py` 포함). 쌓기만 하는 기록(`docs/`의 지난 설계 · ADR 본문 · `phases/*/`)은 고치지 않는다
