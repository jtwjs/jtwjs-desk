# Step 10: signal-scope-label

> `tdd: false`: 화면(`page/index.html`) 한 줄이라 단위 테스트 대상이 아니다(`.claude/rules/testing.md` §0). 대신 가짜 원장으로 서버를 띄워 브라우저에서 눈으로 확인한다(`non-obvious-patterns.md` 「서버 · 화면」). sdd-review 2회차 지적(🟡)을 고치는 step이다.

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-hypothesis-gate-2026-11-12/PRD.md` 「결정」 표의 **레포별 보기** 행
- `page/index.html`: `renderHypBand`의 `hyp-summary` 블록(`el("span", { class: "hyp-scope", text: "전체" })`, 약 1826줄) · `extraRepo` · `fetchHypothesis`
- `.claude/rules/non-obvious-patterns.md` 「서버 · 화면」

## 작업

**`page/index.html`만 고친다.**

- 띠 머리 `hyp-scope` 라벨이 고정 "전체"다. 풀스택 탭의 레포 칩(`extraRepo.fullstack`)이 `null`이면 "전체", 아니면 그 레포 이름을 `textContent`로 보인다
- 라벨은 신호 요청에 실제로 쓴 값을 따라야 한다. 칩을 바꾼 직후 이전 레포 숫자가 남아 있는 동안 라벨만 새 레포로 바뀌면 숫자와 이름이 어긋난다. 기존 `fetchHypothesis`가 응답을 반영할 때 쓴 레포 값(또는 `hypState`에 그 값을 함께 저장)을 라벨에 쓰고, 그 값을 알 수 없으면 현재 칩 값을 쓴다. 새 로딩 표시는 만들지 않는다
- 라벨 문자열은 `textContent`로만. 숫자를 화면에서 다시 계산하지 않는다

### 🔴 CRITICAL

- 사람 이름 · vault 원문을 화면 문자열에 넣지 않는다. 신호 실패가 카드 화면을 깨지 않는다(기존 격리 유지)
- `page/index.html` 밖은 고치지 않는다

## Acceptance Criteria

- `verify.test` 통과(기존 테스트 전부)
- **브라우저 확인**: 가짜 `DESK_HOME`/`DESK_CONFIG`로 서버를 띄우고(레포 a·b가 섞인 가짜 원장 + 카드 몇 장), 풀스택 탭에서 ① 칩 전체일 때 띠 라벨 "전체" ② a 선택 후 응답이 오면 라벨 `repo-a`, 숫자는 `curl '…/hypothesis-signal?repo=repo-a'` 값과 같다 ③ 전체로 돌아오면 라벨 "전체". 가짜 데이터 스크린샷만 스크래치패드에 저장한다. 사용자의 기존 브라우저 탭은 건드리지 않는다
- 못 본 것은 통과로 적지 않는다

## 검증 절차

1. AC 명령과 브라우저 확인을 실제 실행한다. 끝나면 서버를 내리고 픽스처를 정리한다.
2. 결과를 `phases/desk-hypothesis-gate/index.json`의 step 10에 기록(`summary`에 본 것 / 못 본 것).

## 금지사항

- hook 우회(`--no-verify`) · 요청 범위 밖 수정 금지. `page/index.html` 밖은 고치지 않는다. 쌓기만 하는 기록은 고치지 않는다
