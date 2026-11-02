# .claude/ — 이 레포의 하네스

## 어떤 상황에 무엇을 부르나

| 상황 | 부를 것 |
|---|---|
| 과제가 막연하다 / PRD가 없다 | `sdd` ① 계획 DESIGN이 인터뷰로 세 장을 만든다(절차는 플러그인의 `skills/sdd/references/design.md`) |
| 이유·근거만 확인한다(결정 전 · 슬랙 답 · 기획 검토) | `why` — 파일 없이 WHY 트리·근거 판정표만 |
| 설계는 끝났고 구현 계획을 세운다 | `harness` |
| step 계획에 빈칸이 많다 | `harness` §2가 그 자리에서 캐묻는다(DESIGN으로 되돌아가지 않음) |
| 화면이 있는 기능(시안·디자인) | `sdd` 디자인 트랙: `design-brief`(DESIGN, 브리프→시안) → `design-critique`(시안 평가) → `design-reconcile`(REVIEW, 구현 화면 대조) |
| 기능·버그 작업을 처음부터 끝까지 | `sdd` (위 단계를 알아서 넘긴다) |
| 병렬 트랙을 조율한다 | `conductor` (worktree 세션 2개 이상일 때 지휘 세션 하나) |
| 원인 모를 버그·간헐적 실패 | `root-cause-debugger` |
| 하네스가 썩었는지 점검 | `harness-doctor` |
| 같은 지시·같은 교정이 반복된다 | `task-observer` (3회부터 승격 후보. 원장은 `observations.md`) |
| 인수인계 없이 맡은 레포 / `_brain/`이 비어 있다 | `brain-walk` (코드만 읽어 첫 다섯 장) |
| 프로젝트 지식을 통합 wiki로 | `brain-sync` (팀 `_brain`). 개인 학습 `_learn/`은 통합 wiki의 주간 통합이 가져간다 |
| 세션에서 말로 설명하고 흘린 것 | `/revise-claude-md` (`sdd` ④ REFLECT 「하네스 되돌림」에서, 커밋 전 사람이 있을 때. 세션 끝 환기는 돌지 않는다. 종착지는 CLAUDE.md가 아니라 **아래 판정**을 따른다) |

## 이 폴더의 구조

| | 로드 | 담는 것 |
|---|---|---|
| `harness.json` | — | ⭐ **정본.** 검증 명령·TDD 범위·릴리스 도구 |
| `rules/` | **자동** (`paths:`에 걸릴 때) | **판정** — 위반인가 아닌가. 짧게 |
| `references/` | **수동** (rules의 ⏬ 트리거) | **변환** — 그래서 어떻게 고치나. 길어도 됨 |
| `observations.md` | — (로드 안 됨) | **계수기** — 반복된 것과 횟수. `task-observer`만 쓴다 |

> 🔴 **`references/`는 자동으로 읽히지 않는다.** rules에 `⏬` 트리거가 걸려 있어야 열린다. 트리거 없는 references는 죽은 문서이고, `harness-doctor` 검사 2가 잡는다.

## rules에 무엇을 넣나

판정 한 줄: **"이걸 안 읽고 코드를 쓰면 규칙을 어기게 되나?"**
→ 예면 `rules/`(짧게 줄여서), 아니오면 `references/`.
→ 어겨선 안 되는데 길면 **판정만 rules, 설명은 references**로 쪼갠다.

**폴더마다 다른 규칙이면** 하위 `CLAUDE.md`를 만들지 말고 `rules/`에 `paths:` glob을 건다.
하위 `CLAUDE.md`는 `harness-doctor` 검사 5가 재지 않아 **조용히 자란다** — 3층 밖으로 새는 길이다.

⚠️ `paths:`를 붙였다고 길어도 되는 게 아니다. **매칭되면 그 파일은 통째로** 로드된다.
