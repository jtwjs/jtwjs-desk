---
name: decision-inbox
description: 지휘가 사용자에게 선택이 필요한 판정을 올리거나, 이미 올린 판정의 새 선택을 확인할 때 쓴다. Use when the conductor needs to raise a judgment call that requires the user to pick an option, or needs to check for new picks on judgments it already raised.
---

지휘(conductor)가 판정 대기함(`scripts/desk.py`)과 오가는 절차다. **전부 CLI로만 오간다 — `desk/`·`page/`를 import하지 않고, `scripts/desk.py`의 동작을 여기서 다시 구현하거나 베끼지 않는다.** 아래 명령은 전부 `${CLAUDE_PLUGIN_ROOT}/scripts/desk.py`를 그대로 부른다(PRD 사용자 시나리오 ③, ADR-006).

## 1. 판정 올리기

ADR-006 질문 형식으로 JSON을 만들어 stdin으로 넘긴다(또는 파일 경로):

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/desk.py" ask <레포> -
```

질문 형식: `id · order · issue · area · question · why · options[{key,label,recommended}] · see[] · aiDecided[{key,label}] · premiseOpen`.

- `id`는 지휘가 정한다. 세션·질문 성격을 담은 짧은 slug를 권장한다(겹치는 `id`로 다시 `ask`하면 거절된다 — 덮어쓰지 않는다).
- **CRITICAL**: `question`·`why`·`note` 등 자유 텍스트 필드에 사람 이름·vault 원문·대화 원문을 넣지 않는다(CLAUDE.md 1번 규칙). 사람은 역할·트랙 라벨로만 쓴다.

## 2. 새 선택 확인

사용자에게 돌아가기 전이나 새 턴을 시작할 때처럼 자연스러운 시점에, 반영 안 된 새 선택만 읽는다:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/desk.py" picks --new --repo <레포>
```

**126건을 한 번에 훑는 방식(옛 MCP `db_list`)으로 돌아가지 않는다.** 매번 전체를 다시 읽지 말고, 마지막으로 확인한 시각을 `--since`(epoch, float)로 넘겨 그 이후 갱신된 선택만 본다.

## 3. 선택 해석

`picks --new`가 내주는 한 줄 JSON은 다음을 담는다:

- `choice`(옵션 key) 또는 `customText`(직접 쓴 답) 중 하나가 있다.
- `note`·`noteKind`(`reason`|`scope`|`new`) — 왜 그렇게 골랐는지.
- `aiRejected`가 있으면, 그 키가 가리키는 `aiDecided` 항목을 사람이 반려한 것이다. 이 경우 기본 가정으로 되돌리지 말고 사람이 고른 쪽을 따른다.

## 4. 반영 찍기

선택대로 실제로 일을 반영한 뒤(이슈 생성·코드 변경 등) 반영을 찍는다:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/desk.py" applied <레포> <id> --issue <URL>
```

반영을 찍지 않고 넘어가면 화면에 "반영됨" 표시가 영영 뜨지 않는다(PRD 비포 지표 "반영 표시가 있는 판정 0/126"를 되풀이하지 않기 위한 단계다). 반영 전까지는 사람이 몇 번이든 다시 고를 수 있고(PRD desk-repick), 반영을 찍은 뒤에는 화면에서 그 판정이 잠긴다.

## 5. 하지 않는 것

- 이 스킬은 하네스 `conductor` 스킬을 수정하지 않는다(PRD 범위 밖 — "하지 않을 것: 하네스 지휘 스킬 수정". 후속에서 하네스 쪽이 이 스킬을 가리키는 한 줄만 더한다).
- claude.ai 아티팩트를 쓰지 않는다(옛 판정 대기함 126건은 기록으로만 둔다).
- 폰에서 판정하지 않는다(Tailscale 전까지는 PRD 범위 밖. 폰은 ntfy 알림만 받는다).
