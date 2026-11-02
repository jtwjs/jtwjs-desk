# jtwjs-desk

지휘 책상: 판정 대기함(claude.ai 아티팩트)과 트랙 현황 로컬 페이지를 주는 Claude Code 플러그인.

## 🔴 CRITICAL — 어기면 사고

- **사람 이름·vault 원문·세션 대화 원문을 레포와 상태 파일에 넣지 않는다.** 사람은 역할·트랙 라벨로만. vault(`raw/`·`thread-raw/`·`0_Me/`) 원문은 경로 링크도 옮기지 않는다
- **훅은 모델 토큰을 쓰지 않는다.** 상태 파일만 쓰고 끝낸다. `additionalContext`·stdout으로 모델에 글을 넣지 않는다 (트랙 현황을 스크립트로 옮긴 이유가 토큰 0이다)
- **테스트 선행**: `tdd-guard` 훅은 이 레포에서 꺼져 있다(Python 짝 테스트 이름을 못 찾음, `harness.json` tdd 참고). 대신 sdd 러너가 git 기록으로 RED → GREEN을 판정한다. 무엇을 테스트하는지는 → [testing.md](.claude/rules/testing.md) §0
- **hook 우회 금지** (`--no-verify` 등)
- **PR은 `claude-harness:pr-write` 스킬로 만든다.** `gh pr create`를 직접 부르지 않는다
- **push·이슈·PR은 gh 계정 jtwjs로.** 평소 계정(jtw-219)으로는 이 private 레포가 안 보인다. 끝나면 jtw-219로 되돌린다

## 검증

- 아직 없음 — `verify.test`는 첫 테스트가 생길 때 `python3 -m unittest discover -s tests`로 채운다(빈 레포에서는 exit 5)
- 런타임: Python 표준 라이브러리만 (3.14 실측). 외부 패키지를 들이지 않는다

> 정본은 [.claude/harness.json](.claude/harness.json)의 `verify`다. 여기와 어긋나면 `harness-doctor` 검사 1이 잡는다.

## 구조

아직 코드 없음. 첫 설계는 `docs/{feature-YYYY-MM-DD}/`에 남기고, 진입점·의존 방향은 코드가 생기면 여기에 적는다.

## 결정 기록

아키텍처 결정은 `docs/{feature-YYYY-MM-DD}/ADR.md`에 남긴다.
**혼자 일할수록 이게 중요하다** — 팀이면 논의로 남았을 것이 혼자면 아무 데도 안 남고, 나중에 복원이 불가능하다.
**ADR 번호는 혼자 쓰지 않는다** — 처음 나올 때 괄호로 한 줄(`ADR-003(설정 스키마를 blocks 패키지에)`). 문장 끝에 근거로 묶어 다는 자리는 번호만.

## 규칙·참고

- `.claude/rules/` — **자동 로드.** `paths:`에 걸리는 파일을 만질 때 들어온다
- `.claude/references/` — **자동 로드 안 됨.** rules의 ⏬ 트리거로만 연다
- `.claude/README.md` — 어떤 상황에 무엇을 부르나
