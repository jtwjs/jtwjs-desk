"""ADR-006 질문 · 선택 형식을 그대로 스키마로 삼는 검증.

실패를 값으로 돌린다(예외를 던지지 않는다, implementation-patterns.md 패턴 6).
어긴 필드 이름의 목록을 반환하고, 빈 리스트면 통과다.
"""

ASK_FIELDS = (
    "id",
    "order",
    "issue",
    "area",
    "question",
    "why",
    "options",
    "see",
    "aiDecided",
    "premiseOpen",
)

PICK_REQUIRED_FIELDS = ("at", "choice")

_VALID_NOTE_KINDS = ("reason", "scope", "new")


def _is_non_empty_str(value) -> bool:
    return isinstance(value, str) and value != ""


def _valid_option(option) -> bool:
    return (
        isinstance(option, dict)
        and _is_non_empty_str(option.get("key"))
        and _is_non_empty_str(option.get("label"))
        and isinstance(option.get("recommended"), bool)
    )


def _valid_ai_decided(entry) -> bool:
    return (
        isinstance(entry, dict)
        and _is_non_empty_str(entry.get("key"))
        and _is_non_empty_str(entry.get("label"))
    )


def validate_ask(data: dict) -> list:
    """질문 형식 검증. 어긴 필드 이름 목록을 반환한다(빈 리스트면 통과)."""
    if not isinstance(data, dict):
        return list(ASK_FIELDS)

    violations = []

    if not _is_non_empty_str(data.get("id")):
        violations.append("id")

    order = data.get("order")
    if not isinstance(order, int) or isinstance(order, bool):
        violations.append("order")

    issue = data.get("issue")
    if "issue" not in data or not (issue is None or isinstance(issue, str)):
        violations.append("issue")

    if not _is_non_empty_str(data.get("area")):
        violations.append("area")

    if not _is_non_empty_str(data.get("question")):
        violations.append("question")

    if not _is_non_empty_str(data.get("why")):
        violations.append("why")

    options = data.get("options")
    if (
        not isinstance(options, list)
        or len(options) == 0
        or not all(_valid_option(o) for o in options)
    ):
        violations.append("options")

    see = data.get("see")
    if not isinstance(see, list) or not all(isinstance(s, str) for s in see):
        violations.append("see")

    ai_decided = data.get("aiDecided")
    if not isinstance(ai_decided, list) or not all(
        _valid_ai_decided(a) for a in ai_decided
    ):
        violations.append("aiDecided")

    if not isinstance(data.get("premiseOpen"), bool):
        violations.append("premiseOpen")

    return violations


def validate_pick(data: dict) -> list:
    """선택 형식 검증. 어긴 필드 이름 목록을 반환한다(빈 리스트면 통과)."""
    if not isinstance(data, dict):
        return list(PICK_REQUIRED_FIELDS)

    violations = []

    if not _is_non_empty_str(data.get("at")):
        violations.append("at")

    choice = data.get("choice")
    if not _is_non_empty_str(choice):
        violations.append("choice")

    custom_text = data.get("customText")
    if choice == "custom":
        if not _is_non_empty_str(custom_text):
            violations.append("customText")
    elif custom_text is not None and not isinstance(custom_text, str):
        violations.append("customText")

    note = data.get("note")
    if note is not None and not isinstance(note, str):
        violations.append("note")

    note_kind = data.get("noteKind")
    if note:
        if note_kind not in _VALID_NOTE_KINDS:
            violations.append("noteKind")
    elif note_kind is not None and note_kind not in _VALID_NOTE_KINDS:
        violations.append("noteKind")

    ai_rejected = data.get("aiRejected")
    if ai_rejected is not None and (
        not isinstance(ai_rejected, list)
        or not all(isinstance(k, str) for k in ai_rejected)
    ):
        violations.append("aiRejected")

    return violations
