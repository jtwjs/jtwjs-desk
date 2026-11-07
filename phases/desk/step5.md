# Step 5: desk-page

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-2026-11-03/{PRD,ARCHITECTURE,ADR}.md` — 특히 PRD 「사용자 시나리오」·「수용 조건」(판정·트랙 두 섹션) · ADR-004(토큰)
- `page/server.py`의 `GET /sessions`·`GET /judgments`·`POST /pick` 응답·요청 형식(step 4 산출물) — 필드 이름을 그대로 맞춘다
- step 4가 만든 최소 `page/index.html`의 `__DESK_TOKEN__` 자리표시자 — **이 문자열은 그대로 두고 그 자리에 실제 `<script>`를 채운다.**

## 작업

**`tdd: false` — 이유**: ARCHITECTURE 「테스트 전략」이 명시: "화면(`index.html`)은 자동 테스트하지 않는다. 판단은 전부 서버 쪽 순수 함수에 있고, 화면은 수동 확인 목록으로 본다." 판단 로직(정렬·신호 없음·형식 검증)은 전부 step 1·4에서 이미 테스트됐다.

`page/index.html` 하나(JS·CSS 인라인, 외부 CDN·프레임워크 없음 — 외부 패키지 금지). **`page/`는 `desk/`만 import 대상이 아니다(브라우저 JS는 파이썬 모듈을 import하지 않는다) — 오직 서버의 HTTP 응답 형식에만 의존한다.**

- 탭 둘: **트랙** · **판정**. 전환은 클라이언트 쪽에서만(새 요청 없음).
- **트랙 탭**: `GET /sessions`를 15초마다 polling(ADR-002 "페이지는 15초마다 다시 읽는다"). 레포별로 묶어 그리고, 서버가 이미 정렬해 준 순서(승인 대기 > 신호 없음 > 입력 대기 > 작업 중 > 완료)를 그대로 그린다(클라이언트는 재정렬하지 않음 — 판단은 서버에). 각 항목에 "n분 전"(`lastAt` 기준, 클라이언트 `Date.now()`로 매 polling마다 다시 계산 — 표시 전용이라 서버 판정과는 무관).
- **판정 탭**: `GET /judgments`를 15초마다 polling. 카드마다 `question`·`why`·`options`(각 `label`, `recommended`면 강조 표시) · **AI가 정한 것(`aiDecided`)은 options와 분리된 별도 칸** · `premiseOpen`이면 전제 열림 표시 · 직접 쓰기 입력칸(`customText`) · `applied`가 있으면 카드 잠금 + "반영됨" + `issue` 링크 표시(수정 UI 비활성화).
- 옵션 클릭 또는 직접 쓰기 제출 → `POST /pick`(바디: `repo·id·choice|customText·note·noteKind`, 헤더 `X-Desk-Token: <DESK_TOKEN>`). 응답 `409`면 "이미 반영됨"으로 안내하고 그 카드를 다시 불러온다(재시도 없음). `403`이면 토큰 불일치 안내(새로고침 유도 — 서버가 재시작됐을 수 있음, ADR-004 "서버를 다시 띄우면 열린 탭은 새로고침해야 한다").
- `<script>const DESK_TOKEN = "__DESK_TOKEN__";</script>`를 보존한 채, 이 상수를 `POST /pick`의 `X-Desk-Token` 헤더 값으로 쓴다.

### 🔴 CRITICAL (CLAUDE.md에서 인용 — 이 step에 직결)

- 사람 이름·vault 원문·세션 대화 원문을 화면에 그대로 노출하지 않는다 — 서버가 주는 필드(`question`·`why`·`note` 등)를 그대로 보여줄 뿐 추가하지 않는다(원문이 그 필드에 들어가지 않게 하는 책임은 지휘 쪽이다, step 3 참고).

## Acceptance Criteria

- `.claude/harness.json`의 `verify.test` 통과(이 step은 새 테스트를 추가하지 않는다 — 위 이유 참고. step 1~4가 추가한 테스트가 그대로 통과하면 된다).
- 수동 확인 목록(ARCHITECTURE 「화면은... 수동 확인 목록(목업의 칸이 다 보이나)으로 본다」): `page/server.py`를 로컬에서 띄우고 브라우저로 `http://127.0.0.1:<port>/`에 접속해 ① 탭 전환이 되는가 ② 트랙 탭에 가짜 세션 상태 파일을 떨어뜨렸을 때 순서·"n분 전"이 보이는가 ③ 판정 탭에 가짜 ask 파일을 떨어뜨렸을 때 카드의 모든 칸(선택지·AI가 정한 것·전제 열림·직접 쓰기)이 보이는가 ④ 옵션 클릭이 `pick` 파일을 만드는가 ⑤ `applied` 파일이 있는 카드가 잠겨 보이는가. 결과를 `summary`에 체크리스트로 남긴다.

## 검증 절차

1. 위 AC의 `verify.test` + 수동 확인 목록 다섯 항목 실행.
2. 아키텍처 체크리스트: 클라이언트가 정렬·신호없음 판단을 다시 하지 않는가(서버 응답 순서를 그대로 쓰는가). CORS·외부 리소스(CDN) 요청이 없는가.
3. 결과를 `phases/desk/index.json` step 5에 기록(수동 확인 다섯 항목 결과를 `summary`에 포함).

## 금지사항

- hook 우회 · 자동 생성물 직접 수정 · 요청 범위 밖 수정 금지.
- `__DESK_TOKEN__` 자리표시자 문자열을 다른 이름으로 바꾸지 않는다(step 4와 계약). 정렬·신호없음 판단 로직을 JS로 다시 만들지 않는다(서버 응답을 그대로 신뢰).
