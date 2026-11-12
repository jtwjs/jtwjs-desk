"""우편함(질문함·답함) 텍스트 → 문항·답. 전부 텍스트 · dict를 받는 순수 함수다(파일을 열지 않는다).

계약(이 phase 전체가 같은 값을 쓴다):
- 질문 줄(wiki가 질문함에 씀): 필수 id · date(YYYY-MM-DD) · kind · text(전부 비어 있지 않은 문자열),
  선택 options(`[{"key", "label"}, ...]`, 비어 있지 않은 리스트). 같은 id는 마지막 줄이 이긴다.
- 답 줄(desk가 답함에 씀): id · status("answered" | "skipped") · value(answered일 때만) ·
  note(선택) · at. 같은 id는 마지막 줄이 이긴다. 깨진 줄은 건너뛰고 개수를 센다.
- 입력 모양 `input`: "choice" | "long" | "line". options가 있으면 choice, 아니면 kind가 복습이면
  choice(기본 선택지 `REVIEW_DEFAULT_OPTIONS`), 설명이면 long, 그 밖(모르는 종류 포함)은 line.
- 상태: 답 줄이 없으면 unanswered, 있으면 그 status.
- 오늘/지난: 오늘은 호출하는 쪽이 넘긴다. 미래 날짜 문항은 어디에도 세지 않는다.
"""
import json
import re
from datetime import date

ANSWER_MAX_CHARS = 4000
REVIEW_DEFAULT_OPTIONS = [{"key": "known", "label": "알았다"},
                          {"key": "unsure", "label": "헷갈림"}]

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_STATUSES = ("answered", "skipped")


def _nonempty_str(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _valid_date(value) -> bool:
    if not isinstance(value, str) or not _DATE.match(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _valid_options(options) -> bool:
    return (isinstance(options, list) and bool(options)
            and all(isinstance(o, dict) and _nonempty_str(o.get("key"))
                    and _nonempty_str(o.get("label")) for o in options))


def _valid_question(row) -> bool:
    if not isinstance(row, dict):
        return False
    if not all(_nonempty_str(row.get(k)) for k in ("id", "kind", "text")):
        return False
    if not _valid_date(row.get("date")):
        return False
    return "options" not in row or _valid_options(row["options"])


def _valid_answer(row) -> bool:
    if not isinstance(row, dict) or not _nonempty_str(row.get("id")):
        return False
    status = row.get("status")
    if status not in _STATUSES:
        return False
    return status == "skipped" or _nonempty_str(row.get("value"))


def _parse_lines(text: str, is_valid) -> tuple:
    rows = {}
    broken = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            broken += 1
            continue
        if not is_valid(row):
            broken += 1
            continue
        rows[row["id"]] = row
    return rows, broken


def parse_questions(text: str) -> tuple:
    """질문함 텍스트 → (id → 마지막 줄의 문항, 깨진 줄 수). 빈 줄은 무시한다."""
    return _parse_lines(text, _valid_question)


def parse_answers(text: str) -> tuple:
    """답함 텍스트 → (id → 마지막 답 줄, 깨진 줄 수). 빈 줄은 무시한다."""
    return _parse_lines(text, _valid_answer)


def effective_options(q: dict):
    """choice 입력의 선택지. options가 있으면 그것, 복습이면 기본 선택지, 아니면 None."""
    if q.get("options"):
        return q["options"]
    if q.get("kind") == "복습":
        return REVIEW_DEFAULT_OPTIONS
    return None


def input_shape(q: dict) -> str:
    """화면이 보는 입력 모양: choice | long | line. 모르는 종류는 line이다."""
    if effective_options(q) is not None:
        return "choice"
    if q.get("kind") == "설명":
        return "long"
    return "line"


def question_state(q: dict, answers: dict) -> str:
    """unanswered | answered | skipped."""
    row = answers.get(q.get("id"))
    return row["status"] if row else "unanswered"


def validate_answer(q, body) -> list:
    """어긴 필드 이름 목록(빈 리스트면 통과). 예외를 던지지 않는다."""
    if not isinstance(q, dict):
        return ["id"]
    if not isinstance(body, dict):
        return ["value"]
    bad = []
    status = body.get("status", "answered")
    if status not in _STATUSES:
        bad.append("status")
    if status == "answered":
        value = body.get("value")
        if not _nonempty_str(value) or len(value) > ANSWER_MAX_CHARS:
            bad.append("value")
        elif input_shape(q) == "choice":
            keys = [o["key"] for o in effective_options(q)]
            if value not in keys:
                bad.append("value")
    note = body.get("note")
    if note is not None and (not isinstance(note, str) or len(note) > ANSWER_MAX_CHARS):
        bad.append("note")
    return bad


def _view(q: dict, answers: dict) -> dict:
    row = answers.get(q["id"]) or {}
    return {**q, "input": input_shape(q), "options": effective_options(q),
            "state": question_state(q, answers),
            "value": row.get("value", ""), "note": row.get("note", "")}


def split_by_date(questions: dict, answers: dict, today: date) -> dict:
    """{"today": 오늘 문항 전부, "past": 지난 문항 중 answered가 아닌 것}. 미래는 뺀다."""
    out = {"today": [], "past": []}
    for q in questions.values():
        d = date.fromisoformat(q["date"])
        if d == today:
            out["today"].append(_view(q, answers))
        elif d < today:
            view = _view(q, answers)
            if view["state"] != "answered":
                out["past"].append(view)
    return out


def group_by_kind(items: list) -> list:
    """종류는 처음 나온 순서, 항목 순서 유지."""
    groups = {}
    for item in items:
        groups.setdefault(item["kind"], {"kind": item["kind"], "items": []})["items"].append(item)
    return list(groups.values())


def unanswered_today_count(questions: dict, answers: dict, today: date) -> int:
    """오늘 날짜 문항 중 unanswered인 수(skipped · answered는 안 센다)."""
    return sum(1 for q in questions.values()
               if date.fromisoformat(q["date"]) == today
               and question_state(q, answers) == "unanswered")
