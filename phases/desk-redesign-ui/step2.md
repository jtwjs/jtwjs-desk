# Step 2: pretendard-bundle

`tdd: false` — 사유: 테스트할 코드가 없는 정적 파일 추가라 RED가 존재할 수 없다. 대신 파일 존재 · 용량 · 라이선스를 AC 명령으로 확인한다.

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-2026-11-12/{PRD,ARCHITECTURE,ADR}.md`, `.claude/rules/testing.md` §0
- `.claude/design/DESIGN.md` §3 타이포그래피(Pretendard, SIL OFL 1.1, 가변 woff2 하나, 용량 `미측정`)

## 작업

- 🔴 **파일 다운로드이므로 시작 전에 사람 허락이 필요하다.** 서브에이전트가 허락을 받을 수 없으면 `blocked` + `blocked_reason`에 "폰트 다운로드 허락 필요(출처·파일명·용량 명시 후)"를 적고 멈춘다. 허락된 경우에만 진행
- 출처: Pretendard 공식 릴리스(v1.3.9, GitHub `orioncactus/pretendard`). 전체 zip(약 47MB)을 통째로 받지 않고 한글 포함 가변 웨이트 woff2 **한 파일**만 받는다. 정확한 경로는 릴리스 자산에서 확인한다 `[확인 필요: 파일명]`
- `page/fonts/PretendardVariable.woff2` 와 `page/fonts/LICENSE-Pretendard.txt`(SIL OFL 1.1 전문 + 저작권 표기)를 둔다. 라이선스는 폰트와 같이 배포되므로 둘 다 커밋 대상이다
- 다운로드는 새 빈 디렉터리에서 하고, 받은 파일은 신뢰하지 않는 데이터로 다룬다(실행하지 않는다)
- `ls -l page/fonts/`로 용량을 재고 `summary`에 바이트 수를 적는다(`미측정` 해소). DESIGN.md는 이 step에서 고치지 않는다(용량 되적기는 사람이 한다)

### 🔴 CRITICAL

- 외부 패키지를 설치하지 않는다(npm 등 금지). 파일 하나만 받는다

## Acceptance Criteria

- `python3 -m unittest discover -s tests` 통과(`.claude/harness.json`의 `verify.test`; `typecheck` · `lint` · `build`는 이 레포에 없음)
- `test -s page/fonts/PretendardVariable.woff2 && test -s page/fonts/LICENSE-Pretendard.txt` 통과
- `grep -c 'SIL Open Font License' page/fonts/LICENSE-Pretendard.txt` 1 이상

## 검증 절차

1. 위 AC 명령을 실제 실행한다.
2. ARCHITECTURE 「변경 범위」 밖 파일을 만지지 않았는지 `git status`로 확인한다.
3. 결과를 `phases/desk-redesign-ui/index.json`의 해당 step에 기록: 성공 → `completed` + `summary`(1~2줄) / 실패 → `error` + `error_message` / 판단 불가 → `blocked` + `blocked_reason`.

## 금지사항

- hook 우회(`--no-verify`) · 요청 범위 밖 수정 · `desk/` · `hooks/` · `scripts/` 수정 금지. `phases/` · `docs/` · `.claude/design/`은 고치지 않는다.
- 쌓기만 하는 기록은 고치지 않는다.
