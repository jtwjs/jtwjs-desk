# Step 12: signal-diff-screen

> `tdd: false`: 화면(`page/index.html`)이라 단위 테스트 대상이 아니다(`.claude/rules/testing.md` §0). 대신 가짜 원장으로 서버를 띄워 브라우저에서 눈으로 확인한다(`non-obvious-patterns.md` 「서버 · 화면」).

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-hypothesis-gate-2026-11-12/PRD.md` 「결정」 표의 **난이도 칸 `diff`** 행 · **레포별 보기** 행
- `page/index.html`: `renderHypBand` · `hypCard` · `hypState` · `hypReasonRow` 와 `.hyp-*` 스타일(약 480~560줄). 기존 띠 모양 · 토큰을 그대로 따른다
- `.claude/design/checkpoints/05-hypothesis-signal.md` (읽기만)
- `.claude/rules/non-obvious-patterns.md` 「서버 · 화면」 「화면 · 서버 집계」

## 작업

**`page/index.html`만 고친다.** 서버는 step 11에서 응답에 `diff`(`{easy|mid|hard|none: {right, partial, wrong, pending}}`)를 이미 준다.

- 영역 카드 아래에 **작은 표**를 그린다. 눈으로 훑기 편해야 한다(Finn 결정).

```
          맞음  부분  틀림  판정 전
 쉬움      8     2     1     1
 보통      3     1     2     1
 어려움    1     0     2     0
 미정      5     1     0     2
```

- 행 이름: `easy`=쉬움 · `mid`=보통 · `hard`=어려움 · `none`=미정. 열 이름: 맞음 · 부분 · 틀림 · 판정 전(`pending`)
- **건수만 보인다.** 합계 · 비율 · 판정 색(좋다/나쁘다 색)은 만들지 않는다. 0도 숫자로 채운다. 행 이름은 기존 muted 글자색, 숫자는 본문색. 점수 색은 쓰지 않는다
- 표 제목 한 줄: 「난이도별 적중」. 응답 문자열은 `textContent`로만. 숫자를 화면에서 다시 계산하지 않는다(서버 값 그대로)
- 보이는 조건: `mode`가 정상(`ok`)일 때. `missing` · 로딩 · 기록 0건(`empty`)이면 표를 안 그린다(기존 띠 규칙을 따른다). 응답에 `diff`가 없으면 표를 안 그린다
- 레포 칩이 걸려 있으면 그 응답의 `diff`를 그대로 그린다(서버가 이미 걸러 준다). 신호 실패 때는 마지막 값을 유지하는 기존 규칙을 따른다

### 🔴 CRITICAL

- 사람 이름 · vault 원문을 화면 문자열에 넣지 않는다. 신호 실패가 카드 화면을 깨지 않는다(기존 격리 유지)
- `page/index.html` 밖은 고치지 않는다

## Acceptance Criteria

- `verify.test` 통과(기존 테스트 전부)
- **브라우저 확인**: 가짜 `DESK_HOME`/`DESK_CONFIG`로 서버를 띄우고(레포 a·b 섞인 가짜 원장, `diff`가 easy·mid·hard·null·없음으로 섞이고 적중 줄도 있음) 풀스택 탭에서 ① 표 네 행 · 네 열이 보이고 숫자가 `curl '…/hypothesis-signal'`의 `diff` 값과 같다 ② 레포 칩을 a로 바꾸면 표 숫자가 `?repo=repo-a` 값으로 바뀐다 ③ 합계 · 비율 · 판정 색이 없다 ④ 기록 0건 서버에서는 표가 안 보인다. 가짜 데이터 스크린샷만 스크래치패드에 저장한다. 사용자의 기존 브라우저 탭은 건드리지 않는다
- 못 본 것은 통과로 적지 않는다

## 검증 절차

1. AC 명령과 브라우저 확인을 실제 실행한다. 끝나면 서버를 내리고 픽스처를 정리한다.
2. 결과를 `phases/desk-hypothesis-gate/index.json`의 step 12에 기록(`summary`에 본 것 / 못 본 것).

## 금지사항

- hook 우회(`--no-verify`) · 요청 범위 밖 수정 금지. `page/index.html` 밖은 고치지 않는다. 쌓기만 하는 기록은 고치지 않는다
