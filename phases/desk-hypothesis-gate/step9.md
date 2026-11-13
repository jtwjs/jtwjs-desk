# Step 9: signal-repo-chip

> `tdd: false`: 화면(`page/index.html`)이라 단위 테스트 대상이 아니다(`.claude/rules/testing.md` §0). 대신 가짜 원장으로 서버를 띄워 브라우저에서 눈으로 확인한다(`non-obvious-patterns.md` 「서버 · 화면」).

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-hypothesis-gate-2026-11-12/PRD.md` 「결정」 표의 **레포별 보기** 행
- `page/index.html`: `repoFilterChip` · `extraRepo` · `renderFullstack` · `fetchHypothesis` · `renderHypBand` · `hypState`
- `.claude/design/checkpoints/05-hypothesis-signal.md` (verdict 승인, 읽기만)
- `.claude/rules/non-obvious-patterns.md` 「서버 · 화면」 「화면 · 서버 집계」

## 작업

**`page/index.html`만 고친다.**

- 풀스택 탭에는 카드 목록을 거르는 **기존 레포 칩**이 있다(`repoFilterChip("fullstack", …)`, 카드가 있을 때만 보임). 이 칩 상태(`extraRepo.fullstack`)를 신호에도 쓴다
- `fetchHypothesis`가 `extraRepo.fullstack`이 `null`이 아니면 `/hypothesis-signal?repo=` + `encodeURIComponent(값)`으로 부른다. 15초 폴링도 같은 값을 쓴다
- 칩 선택지는 카드 레포 목록 ∪ 신호 응답의 `repos`(중복 없이)다. 카드가 0건이어도 `repos`가 있으면 칩이 보인다. 칩을 눌러 레포가 바뀌면 카드 목록과 신호를 **둘 다** 다시 그린다(신호는 다시 요청한다)
- 레포를 바꾼 직후 이전 레포 숫자가 잠깐 보일 수 있다. 응답이 올 때까지 마지막 값을 유지하는 기존 규칙을 따르고, 새 로딩 표시는 만들지 않는다
- 응답 문자열은 `textContent`로만 쓴다. 숫자(`pct` · `n` · `m`)를 화면에서 다시 계산하지 않는다
- 신호 응답이 `repos`를 안 주는 경우(`missing`)는 기존 화면 그대로

### 🔴 CRITICAL

- 사람 이름 · vault 원문을 화면 문자열에 넣지 않는다. 신호 실패가 카드 화면을 깨지 않는다(기존 격리 유지)
- `page/index.html` 밖은 고치지 않는다

## Acceptance Criteria

- `verify.test` 통과(기존 테스트 전부)
- **브라우저 확인**: 가짜 `DESK_HOME`/`DESK_CONFIG`로 서버를 띄우고(레포 a·b가 섞인 가짜 원장 + 카드 몇 장), 풀스택 탭에서 ① 칩 값이 전체 → a → b로 돈다 ② a일 때 띠 숫자가 `curl '…/hypothesis-signal?repo=repo-a'` 응답과 같다 ③ 카드 목록도 같은 레포로 걸린다 ④ 카드 0건 + 원장만 있어도 칩이 보인다. 가짜 데이터 스크린샷만 스크래치패드에 저장한다. 사용자의 기존 브라우저 탭은 건드리지 않는다
- 못 본 것은 통과로 적지 않는다

## 검증 절차

1. AC 명령과 브라우저 확인을 실제 실행한다. 끝나면 서버를 내리고 픽스처를 정리한다.
2. 결과를 `phases/desk-hypothesis-gate/index.json`의 step 9에 기록(`summary`에 본 것 / 못 본 것).

## 금지사항

- hook 우회(`--no-verify`) · 요청 범위 밖 수정 금지. `page/index.html` 밖은 고치지 않는다. 쌓기만 하는 기록은 고치지 않는다
