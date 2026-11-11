# Step 9: page-tabs

`tdd: false` — 사유: 화면(`index.html`)은 자동 테스트하지 않는다. 판단은 전부 서버 순수 함수에 있고 화면은 수동 확인 목록으로 본다(ARCHITECTURE 「테스트 전략」, `.claude/rules/testing.md` §0 "개별 프레젠테이션 컴포넌트").

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-2026-11-11/{PRD,ARCHITECTURE,ADR}.md` — 특히 ARCHITECTURE 「UI 배치」 · 「엔드포인트」 · ADR-010
- `page/index.html` — 기존 탭 구조(`.tab-btn[data-tab]` · `.tab-panel` · 탭 전환 스크립트) · 기존 폴링 · POST가 `__DESK_TOKEN__`을 쓰는 방식 · 서버 응답 문자열을 DOM에 넣는 방식. **먼저 전부 읽고 같은 스타일을 따른다**
- `page/server.py`의 새 엔드포인트 응답 모양(step 5~8 산출물)

## 작업

변경은 `page/index.html` 한 파일. 로직(정렬 · 파싱 · 분류)을 화면에 두지 않는다 — 서버가 준 대로 그린다.

- 상단 탭을 6개로: `트랙 · 판정 · 복습함 · 3역량 · 주간 롤업 · 레포 건강도`(기존 둘은 그대로). 3역량 안에 서브 탭 `AI워크플로우 · 적극성 · 풀스택`
- **보이는 탭만 부른다**(ADR-010): 탭을 열 때 한 번, 열려 있는 동안 기존 폴링 주기로 그 탭의 엔드포인트만(3역량은 현재 서브 탭만). 숨은 탭은 요청하지 않는다. 기존 트랙 · 판정 폴링은 그대로
- 각 탭 위에 `config` 한 줄: `source`가 `conductor`면 "폴백 사용 중", `none`이면 "설정 없음", `unregistered`가 있으면 "미등록 레포 n개: 이름…", `error`가 있으면 그 문구
- `missing` 목록은 항목을 숨기지 않고 "레포 · 무엇 · 경로 없음/파일 없음"으로 그린다. 조용히 빈 탭이 없어야 한다
- **복습함**: 항목마다 `복습함 반영` 버튼 → `POST /review/done`(토큰 헤더, 기존 `/pick`과 같은 방식) → 성공하면 목록을 다시 불러온다
- **AI워크플로우**: 행을 서버 순서대로. `highlight` 행은 눈에 띄게. `unparsed`는 "형식 확인 필요"
- **적극성** 위에서 아래로: CPO 기준 메모(항상 펼침, `text`가 `None`이면 `note`) → 스피드(① 소요시간 ② `metric2` 문구 ③ AI워크플로우 서브 탭으로 가는 링크, 숫자 없음) → 임팩트(① PRD 경로 ② 최근 갱신분 또는 "경로 미설정") → 투명성(미반영 공유 파일: 본문 · `복사` 버튼(`navigator.clipboard`) · `공유함` 버튼 → `POST /share/shared`)
- **풀스택**: `groups`의 영역별 섹션(FE · BE · infra · 도메인 · 미분류), 서버 순서대로
- **주간 롤업**: `week`의 합계(세션 · 프로젝트 · 커밋 · 학습카드 · 막힌 것)와 레포별 진행, `missing` 날짜
- **레포 건강도**: 레포별 점수 · 등급 · "n일 전 채점" 또는 `missing` 문구

### 🔴 CRITICAL

- 🔴 서버 응답의 문자열(카드 제목 · 공유 텍스트 · CPO 기준 · 패턴 등)은 원장 파일의 **임의 텍스트**다. `innerHTML`에 문자열을 이어 붙이지 않는다. `textContent`로 넣거나 이스케이프한다(저장형 XSS 방지 — 기존 코드가 이미 안전한 방식을 쓰면 그것을 따르고, 아니면 이 step에서 새 코드에 한해 `textContent`)
- 화면이 슬랙 등 외부로 전송하지 않는다(복사만 한다). 사람 이름 · vault 원문을 `index.html`에 하드코딩하지 않는다
- `hooks/`는 변경하지 않는다

## Acceptance Criteria

- `verify.test` 통과(`typecheck` · `lint` · `build`는 이 레포에 없음). 기존 테스트 회귀 없음(`GET /`가 토큰 자리표시자를 치환하는 기존 테스트 포함)
- `grep -n "__DESK_TOKEN__" page/index.html`이 기존과 같은 한 곳
- 새 코드에서 서버 응답 값을 `innerHTML +=`나 템플릿 문자열로 HTML에 이어 붙이지 않았다(변경 diff를 직접 훑어 확인하고 `summary`에 적는다)
- 수동 확인 목록(`summary`에 해당 여부를 적는다): 탭 6개와 3역량 서브 탭 3개가 전환된다 · 숨은 탭이 요청하지 않는다(브라우저 네트워크 탭) · `config` 한 줄 · `missing` 행 · 복습 반영 버튼 · 적극성 순서 · 복사 · 공유함 버튼

## 검증 절차

1. AC 명령 실행 + 위 grep.
2. 체크: 로직이 서버가 아닌 화면에 새로 생기지 않았는가.
3. 결과를 `phases/desk-ledger-tabs/index.json` step 9에 기록(수동 확인을 못 한 항목은 `summary`에 `미확인`으로 적는다).

## 금지사항

- hook 우회(`--no-verify`) · 요청 범위 밖 수정 금지. `page/server.py` · `desk/` · `phases/desk/` · `docs/`는 고치지 않는다. 기존 트랙 · 판정 탭의 동작은 바꾸지 않는다. `hooks/` · `scripts/`는 변경하지 않는다.
