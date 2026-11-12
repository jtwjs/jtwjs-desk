# Step 4: trends-get

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-tech-trends-2026-11-12/{PRD,ARCHITECTURE,ADR}.md` — PRD 수용 조건 1 · 5 · 6 · 7 · 11 · 13 · 14 · 16 · 18, ADR-009(GET은 읽기만)
- `.claude/rules/testing.md` §0 · §1 · §2 · `.claude/rules/non-obvious-patterns.md` — 특히 「서버 · 화면」(화면이 읽는 필드를 서버가 실제로 보내는지)
- `desk/trends.py`(step 1 · 3 산출물) · `desk/config.py`(step 2의 세 키) · `desk/routine.py`의 `read_text_or_none`
- `page/server.py` — `build_routine`(이유 행 `missing` 패턴) · `count_nav`(`isolated(name, fn)`로 항목 격리, 실패 시 None + `errors[name]`에 예외 이름만) · `_today()` · `do_GET` 라우팅 · `config_block`
- `tests/test_desk_server_routine.py` · `tests/test_desk_server_navcounts_routine.py` — 테스트 스타일(가짜 `DESK_HOME`/`DESK_CONFIG`)

## 계약

`GET /trends` 응답(JSON, 서버가 계산하고 화면은 받은 대로 그린다):

```
{
  "config": config_block(cfg),
  "date": "YYYY-MM-DD",            // _today()
  "today": [글...],                  // 오늘 글, 파일 순서
  "past_unread": [글...],            // 날짜 내림차순
  "heatmap": [{"date","total","read"}...],  // 365칸, 오래된 날부터
  "bookmarks": [글...],              // 날짜 내림차순, 글 모양에 read 포함
  "broken": int,                     // 동향 · 읽음 · 북마크의 깨진 줄 합
  "can_record_read": bool,           // trends_reads 설정됨
  "can_bookmark": bool,              // trends_marks 설정됨
  "missing": [{"what": str, "reason": str}]
}
```

- 글 모양은 step 1의 계약(`id,date,title,url,summary,read,bookmarked`)
- `missing` 이유는 구분한다: `trends_items`가 None이면 `{"what":"동향","reason":"설정 없음"}`, 파일이 없으면 `"파일 없음"`, 읽을 수 없거나 파싱 결과가 전부 깨졌으면 `"형식 확인 필요"`. 설정이 있고 읽었는데 오늘 글이 0건이면 `missing`은 비고 `today`가 `[]`다(화면이 「오늘 동향 0건」을 그린다). 이 경우에도 응답은 200이고 서버는 죽지 않는다
- `trends_reads` · `trends_marks`가 None이면 해당 파일은 빈 것으로 취급하고 `can_record_read`/`can_bookmark`가 false다. 파일이 없을 뿐이면(설정은 있음) 빈 것으로 취급하고 can_*는 true
- `GET /nav-counts` 응답에 키 **`trends`**(= `unread_count`) 하나를 더한다. `isolated`로 격리 — 이 값을 못 구하면 `trends: null`과 `errors["trends"]`만 바뀌고 `judge` · `review` · `routine`은 그대로다. 기존 키와 동작은 바뀌지 않는다

## 작업

러너가 이 step을 테스트 먼저 → 구현으로 한 호출에서 돌린다. **`page/server.py`(`build_trends` 추가 · `do_GET`에 `/trends` 라우트 · `count_nav`에 `trends` 항목)와 새 테스트 파일 `tests/test_desk_server_trends.py`만** 만든다/고친다. 쓰기(POST)는 step 5라 이 step은 만들지 않는다.

- `build_trends(cfg: dict) -> dict`: 위 계약대로. 파일 읽기는 `routine.read_text_or_none`, 계산은 `desk/trends.py` 함수만 쓴다(서버에 집계 로직을 새로 쓰지 않는다)
- GET은 **파일을 바꾸지 않는다**(ADR-009)

### 🔴 CRITICAL

- 사람 이름 · vault 원문 · 세션 대화 원문을 레포와 상태 파일에 넣지 않는다. 픽스처는 가짜 글이다
- 훅은 모델 토큰을 쓰지 않는다 — 이 phase는 훅을 건드리지 않는다
- 응답에 파일 경로 · 예외 메시지를 싣지 않는다(예외 이름만, `count_nav`와 같은 규칙)

## Acceptance Criteria

- `.claude/harness.json`의 `verify.test` 통과. `typecheck` · `lint` · `build`는 이 레포에 없다
- `tests/test_desk_server_trends.py` 단언: 오늘 3건이 제목 · 요약 · 링크 · `read`와 함께 온다 · 읽음 파일에 id가 있으면 그 글 `read`가 true · 지난 안 읽은 글이 날짜 내림차순 · 잔디 365칸에 지난 날 글을 읽으면 그 글 날짜 칸이 오른다 · 설정 없음 / 파일 없음 / 형식 확인 필요 / 오늘 0건이 서로 다른 응답이고 모두 200 · 깨진 줄 수가 `broken`에 든다 · `trends_reads` 비면 `can_record_read` false · `trends_marks` 비면 `can_bookmark` false · 북마크 목록과 글의 `bookmarked` · GET 전후 세 파일이 안 바뀐다 · `/nav-counts`의 `trends`가 안 읽은 건수(지난 날 포함, 미래 제외) · 동향 파일을 못 읽어 `trends`가 null이어도 `judge` · `review` · `routine` 값은 그대로 온다 · 응답 JSON에 가짜 경로 문자열이 없다
- 엣지 5축: 빈 값(빈 파일 · 오늘 0건) · 비정상 입력(깨진 줄) · 실패 경로(파일 없음 · 설정 없음) · 상태 전이(읽음 전 → 후 응답 변화) · 동시성(해당 없음: 읽기 전용)

## 검증 절차

1. AC 명령을 실제 실행한다.
2. `ARCHITECTURE.md` 구조 그림 · 읽기 엔드포인트 행과 대조.
3. 결과를 `phases/desk-tech-trends/index.json`의 step 4에 기록: 성공 → `completed` + `summary`(1~2줄, 응답 키 포함) / 실패 → `error` + `error_message` / 차단 → `blocked` + `blocked_reason`.

## 금지사항

- hook 우회(`--no-verify`) · 자동 생성물 직접 수정 · 요청 범위 밖 수정 · **테스트 파일 수정**(구현 단계에서) 금지
- 이 step이 맡지 않은 파일은 고치지 않는다(`page/index.html` 포함 — 화면은 step 6, 7). 쌓기만 하는 기록(`docs/`의 지난 설계 · ADR 본문 · `phases/*/`)은 고치지 않는다
