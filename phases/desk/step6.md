# Step 6: desk-skill-doc

## 읽어야 할 파일

- `CLAUDE.md`, `docs/desk-2026-11-03/{PRD,ARCHITECTURE,ADR}.md` — 특히 ADR-006(desk 스크립트 명령·형식) · PRD 「사용자 시나리오」③ · 「하지 않을 것: 하네스 지휘 스킬 수정」
- `scripts/desk.py`의 서브커맨드·인자(step 3 산출물) — 이 문서가 부르는 명령은 거기 실제로 있는 것만
- 형식 참고: `~/dev/jtwjs/claude-harness/skills/harness-run/SKILL.md`의 `${CLAUDE_PLUGIN_ROOT}` 스크립트 호출 패턴, `~/dev/jtwjs/claude-harness/skills/why/SKILL.md`의 frontmatter

## 작업

**`tdd: false` — 이유**: 코드가 아니라 절차 문서다(ARCHITECTURE "skills/decision-inbox/SKILL.md | 지휘가 판정을 올리고 읽는 절차 | 코드"). 테스트할 동작이 없다.

`skills/decision-inbox/SKILL.md` 하나. frontmatter(`name: decision-inbox`, `description`에 "Use when" 절 포함 — 지휘가 사용자에게 선택이 필요한 판정을 올리거나, 올린 판정의 새 선택을 확인할 때)와 본문.

본문에 담을 절차(전부 `${CLAUDE_PLUGIN_ROOT}/scripts/desk.py`를 명령으로 부른다 — **import하지 않는다, 코드를 베끼지 않는다**):

1. **판정 올리기**: ADR-006 질문 형식(`id · order · issue · area · question · why · options[{key,label,recommended}] · see[] · aiDecided[{key,label}] · premiseOpen`)으로 JSON을 만들어 `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/desk.py" ask <레포> -`에 stdin으로 넘긴다(또는 파일). `id`는 지휘가 정한다(겹치면 거절됨 — 세션·질문 성격을 담은 짧은 slug 권장). **CRITICAL**: `question`·`why`·`note` 등 자유 텍스트 필드에 사람 이름·vault 원문·대화 원문을 넣지 않는다(CLAUDE.md 1번 규칙 인용).
2. **새 선택 확인**: 자연스러운 시점(사용자에게 돌아가기 전, 새 턴 시작 시)에 `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/desk.py" picks --new --repo <레포>`로 반영 안 된 새 선택만 읽는다. **126건을 한 번에 읽는 방식(옛 MCP db_list)으로 돌아가지 않는다** — 매번 전체를 훑지 않고 `--since`로 마지막 확인 시각 이후만 본다.
3. **선택 해석**: `choice`(옵션 key) 또는 `customText`(직접 씀) 중 하나. `note`·`noteKind`(`reason`|`scope`|`new`)로 왜 그렇게 골랐는지. `aiRejected`가 있으면 그 `aiDecided` 항목을 반려한 것 — 그 경우엔 기본 가정으로 되돌리지 말고 사람이 고른 쪽을 따른다.
4. **반영 찍기**: 선택대로 실제로 일을 반영한 뒤(이슈 생성·코드 변경 등) `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/desk.py" applied <레포> <id> --issue <URL>`을 부른다. 반영하지 않고 넘어가면 화면에 "반영됨" 표시가 영영 안 뜬다(PRD 비포 지표 "반영 표시가 있는 판정 0/126"를 되풀이하지 않는 목적).
5. **하지 않는 것**: 이 스킬은 하네스 `conductor` 스킬을 수정하지 않는다(PRD 범위 밖, 후속에서 한 줄 연결). claude.ai 아티팩트를 쓰지 않는다. 폰에서 판정하지 않는다(Tailscale 전까지, PRD 범위 밖).

## Acceptance Criteria

- `python3 -c "import yaml" 2>/dev/null; python3 -c "
import re,sys
text=open('skills/decision-inbox/SKILL.md').read()
assert text.startswith('---'), 'frontmatter 없음'
"` 형태로 frontmatter 존재만 최소 확인(이 레포에 YAML 파서가 없으면 `---`로 시작·끝나는 블록 존재만 문자열로 확인해도 된다 — 외부 패키지 금지 원칙상 `pyyaml` 새로 들이지 않는다).
- 문서가 부르는 `scripts/desk.py` 서브커맨드(`ask`·`picks --new`·`applied`) 이름이 step 3 실제 구현의 서브커맨드 이름과 정확히 같다(grep으로 대조).
- `.claude/harness.json`의 `verify.test` 통과(이 step은 코드를 바꾸지 않으니 기존 테스트가 그대로 통과하면 된다).

## 검증 절차

1. 위 AC 확인(frontmatter 존재 + 서브커맨드 이름 대조 + 기존 test 통과).
2. 아키텍처 체크리스트: 문서가 `desk.py` 내부 구현(파일 경로·클래스 이름)을 설명하지 않고 **CLI 사용법만** 설명하는가(코드와 중복되면 하나가 바뀔 때 다른 하나가 썩는다).
3. 결과를 `phases/desk/index.json` step 6에 기록. **이 step이 마지막 step이므로 `verify` 전체(앱 전체) 명령으로 검증한다**(harness-run §2 judge 표 "phase 마지막 step이면 전체").

## 금지사항

- hook 우회 · 자동 생성물 직접 수정 · 요청 범위 밖 수정 금지.
- 하네스 `conductor`·`sdd` 등 claude-harness 레포의 스킬 파일을 수정하지 않는다(PRD "하지 않을 것"). `scripts/desk.py`의 실제 동작을 이 문서에서 다시 구현하거나 바꾸지 않는다.
