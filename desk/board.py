"""칸반 카드 — 순수 함수(검증 · 열 전이 · 경과 일수 · 후보 표식 · 연결 상태 · 진행도)와
`DESK_HOME/board/<레포>/` 아래 카드 · 시작 요청 · 링크 파일 읽기·쓰기.

시각·오늘 날짜는 인자로 받는다. 쓰기는 전부 `desk/atomic.py`의 `write_json_atomic`.
계약: docs/desk-kanban-2026-11-14/ARCHITECTURE.md 「상태 규약」.
"""
import json
import re
import secrets
from datetime import date, datetime
from pathlib import Path

from desk import paths
from desk.atomic import write_json_atomic

COLUMNS = ("planned", "doing", "done")

LINK_NAME_MAX = 40
LINK_URL_MAX = 2000
LINKS_MAX = 5

_FORWARD = {("planned", "doing"), ("doing", "done")}


def check_title(title) -> str:
    if not isinstance(title, str) or not title.strip():
        raise ValueError("제목이 비었어요")
    return title.strip()


def check_link(name, url) -> tuple:
    if not isinstance(name, str) or not isinstance(url, str):
        raise ValueError("링크 이름과 URL은 문자열이어야 해요")
    name = name.strip()
    if not 1 <= len(name) <= LINK_NAME_MAX:
        raise ValueError(f"링크 이름은 1~{LINK_NAME_MAX}자예요")
    if not url.startswith(("http://", "https://")):
        raise ValueError("URL은 http:// 또는 https://로 시작해야 해요")
    if len(url) > LINK_URL_MAX:
        raise ValueError(f"URL은 {LINK_URL_MAX}자 이하예요")
    return name, url


def check_links(links) -> list:
    if len(links) > LINKS_MAX:
        raise ValueError(f"링크는 최대 {LINKS_MAX}개예요")
    return [check_link(name, url) for name, url in links]


def can_move(cur, new) -> bool:
    return (cur, new) in _FORWARD


def elapsed_days(start_at, pr_at, today: date):
    base = pr_at or start_at
    if not base:
        return None
    return max(0, (today - datetime.fromtimestamp(base).date()).days)


def candidate_mark(card: dict, steps) -> bool:
    return (card.get("column") == "doing" and not card.get("pr_at")
            and len(steps) > 0 and all(s == "completed" for s in steps))


def connection_state(card: dict, phase_exists: bool):
    if card.get("column") != "doing":
        return None
    if not card.get("task"):
        return "designing"
    return None if phase_exists else "disconnected"


def progress(steps):
    if not steps:
        return None
    return {"done": sum(1 for s in steps if s == "completed"), "total": len(steps)}


# ---- 파일 읽기 · 쓰기 -------------------------------------------------------

_ID_RE = re.compile(r"^[0-9]+-[0-9a-f]{4}$")
_CARD_FILE_RE = re.compile(r"^([0-9]+-[0-9a-f]{4})\.json$")
_CARD_KEYS = ("title", "note", "column", "task", "created_at", "doing_at", "pr_at",
              "done_at", "archived_at")


class DuplicateTitle(Exception):
    """같은 레포에 같은 제목의 예정 카드가 있다(409)."""


class WrongColumn(Exception):
    """이 열의 카드에는 허용되지 않는 동작이다(409)."""


class AlreadyRequested(Exception):
    """시작 요청 파일이 이미 있다(409)."""


class NoRequest(Exception):
    """취소할 시작 요청 파일이 없다(409)."""


class TooManyLinks(Exception):
    """링크가 이미 최대 개수다(409)."""


class NotFound(Exception):
    """없는 카드 · 링크(404)."""


def _check_repo(repo) -> str:
    if (not isinstance(repo, str) or repo in ("", ".", "..")
            or "/" in repo or "\\" in repo or "\0" in repo or ".." in repo):
        raise ValueError("레포 이름이 올바르지 않아요")
    return repo


def _check_id(card_id) -> str:
    if not isinstance(card_id, str) or not _ID_RE.match(card_id):
        raise ValueError("카드 id 형식이 올바르지 않아요")
    return card_id


def _dir(repo) -> Path:
    return paths.board_dir(_check_repo(repo))


def _card_path(repo, card_id) -> Path:
    return _dir(repo) / f"{_check_id(card_id)}.json"


def _request_path(repo, card_id) -> Path:
    return _dir(repo) / f"{_check_id(card_id)}.request.json"


def _refs_path(repo, card_id) -> Path:
    return _dir(repo) / f"{_check_id(card_id)}.refs.json"


def _load_json(path: Path):
    """읽어서 JSON으로 돌려준다. 파일이 없으면 None, 깨졌으면 ValueError."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    try:
        return json.loads(text)
    except ValueError as e:
        raise ValueError(f"깨진 JSON: {path.name}") from e


def _valid_card(data) -> bool:
    return (isinstance(data, dict) and isinstance(data.get("title"), str)
            and data.get("column") in COLUMNS)


def new_card_id(now) -> str:
    return f"{int(now)}-{secrets.token_hex(2)}"


def _read_request(repo, card_id):
    """(요청 시각 또는 None, 깨짐 여부)."""
    path = _request_path(repo, card_id)
    try:
        data = _load_json(path)
    except ValueError:
        return None, True
    if data is None:
        return None, False
    at = data.get("at") if isinstance(data, dict) else None
    if isinstance(at, bool) or not isinstance(at, (int, float)):
        return None, True
    return at, False


def read_refs(repo, card_id) -> tuple:
    """(링크 목록, 깨짐 여부). 파일이 없으면 ([], False), 깨졌으면 ([], True)."""
    path = _refs_path(repo, card_id)
    try:
        data = _load_json(path)
    except ValueError:
        return [], True
    if data is None:
        return [], False
    refs = data.get("refs") if isinstance(data, dict) else None
    if not isinstance(refs, list) or not all(
            isinstance(r, dict) and {"id", "name", "url"} <= r.keys() for r in refs):
        return [], True
    return refs, False


def read_card(repo, card_id) -> dict:
    path = _card_path(repo, card_id)
    data = _load_json(path)
    if data is None:
        raise NotFound(card_id)
    if not _valid_card(data):
        raise ValueError(f"깨진 카드: {path.name}")
    return data


def list_cards(repo) -> tuple:
    """(카드 목록, 깨진 카드 파일 수). 항목에 id · requested_at · request_broken · refs_broken을 붙인다."""
    d = _dir(repo)
    if not d.is_dir():
        return [], 0
    cards, broken = [], 0
    for path in sorted(d.iterdir()):
        m = _CARD_FILE_RE.match(path.name)
        if not m:
            continue
        try:
            data = _load_json(path)
        except ValueError:
            broken += 1
            continue
        if not _valid_card(data):
            broken += 1
            continue
        card_id = m.group(1)
        requested_at, request_broken = _read_request(repo, card_id)
        _, refs_broken = read_refs(repo, card_id)
        cards.append({**data, "id": card_id, "requested_at": requested_at,
                      "request_broken": request_broken, "refs_broken": refs_broken})
    return cards, broken


def _write_card(repo, card_id, data) -> None:
    write_json_atomic(_card_path(repo, card_id), {k: data.get(k) for k in _CARD_KEYS})


def _new_ref_id(existing) -> str:
    taken = {r["id"] for r in existing}
    while True:
        ref_id = "r" + secrets.token_hex(2)
        if ref_id not in taken:
            return ref_id


def add_card(repo, title, note, now, links=()) -> dict:
    _check_repo(repo)
    title = check_title(title)
    checked = check_links(list(links))
    cards, _ = list_cards(repo)
    if any(c["column"] == "planned" and c["title"].strip() == title for c in cards):
        raise DuplicateTitle(title)
    card_id = new_card_id(now)
    while _card_path(repo, card_id).exists():
        card_id = new_card_id(now)
    data = {"title": title, "note": note if isinstance(note, str) else "", "column": "planned",
            "task": None, "created_at": now, "doing_at": None, "pr_at": None,
            "done_at": None, "archived_at": None}
    _write_card(repo, card_id, data)
    if checked:
        refs = []
        for name, url in checked:
            refs.append({"id": _new_ref_id(refs), "name": name, "url": url})
        write_json_atomic(_refs_path(repo, card_id), {"refs": refs})
    return {**data, "id": card_id}


def delete_card(repo, card_id) -> None:
    card = read_card(repo, card_id)
    if card["column"] != "planned":
        raise WrongColumn(card["column"])
    _request_path(repo, card_id).unlink(missing_ok=True)
    _refs_path(repo, card_id).unlink(missing_ok=True)
    _card_path(repo, card_id).unlink(missing_ok=True)


def archive_card(repo, card_id, now) -> None:
    card = read_card(repo, card_id)
    if card["column"] == "planned":
        raise WrongColumn("planned")
    card["archived_at"] = now
    _write_card(repo, card_id, card)


def revive_card(repo, card_id) -> None:
    card = read_card(repo, card_id)
    card["archived_at"] = None
    _write_card(repo, card_id, card)


def request_start(repo, card_id, now) -> None:
    card = read_card(repo, card_id)
    if card["column"] != "planned":
        raise WrongColumn(card["column"])
    if _request_path(repo, card_id).exists():
        raise AlreadyRequested(card_id)
    write_json_atomic(_request_path(repo, card_id), {"at": now})


def cancel_request(repo, card_id) -> None:
    card = read_card(repo, card_id)
    if card["column"] != "planned":
        raise WrongColumn(card["column"])
    path = _request_path(repo, card_id)
    if not path.exists():
        raise NoRequest(card_id)
    path.unlink()


def _save_refs(repo, card_id, refs) -> None:
    write_json_atomic(_refs_path(repo, card_id), {"refs": refs})


def add_ref(repo, card_id, name, url) -> dict:
    read_card(repo, card_id)
    name, url = check_link(name, url)
    refs, _ = read_refs(repo, card_id)
    if len(refs) >= LINKS_MAX:
        raise TooManyLinks(card_id)
    ref = {"id": _new_ref_id(refs), "name": name, "url": url}
    _save_refs(repo, card_id, refs + [ref])
    return ref


def update_ref(repo, card_id, ref_id, name, url) -> dict:
    read_card(repo, card_id)
    name, url = check_link(name, url)
    refs, _ = read_refs(repo, card_id)
    for ref in refs:
        if ref["id"] == ref_id:
            ref["name"], ref["url"] = name, url
            _save_refs(repo, card_id, refs)
            return ref
    raise NotFound(ref_id)


def delete_ref(repo, card_id, ref_id) -> None:
    read_card(repo, card_id)
    refs, _ = read_refs(repo, card_id)
    kept = [r for r in refs if r["id"] != ref_id]
    if len(kept) == len(refs):
        raise NotFound(ref_id)
    _save_refs(repo, card_id, kept)


def move_card(repo, card_id, new_column, now) -> None:
    card = read_card(repo, card_id)
    if new_column not in COLUMNS or not can_move(card["column"], new_column):
        raise ValueError(f"{card['column']} → {new_column} 이동은 허용되지 않아요")
    card["column"] = new_column
    card["doing_at" if new_column == "doing" else "done_at"] = now
    _write_card(repo, card_id, card)


def mark_pr(repo, card_id, now) -> None:
    card = read_card(repo, card_id)
    if card["column"] != "doing" or card.get("pr_at"):
        raise ValueError("PR 대기 표시는 진행 카드에 한 번만 적어요")
    card["pr_at"] = now
    _write_card(repo, card_id, card)


def set_task(repo, card_id, task) -> None:
    if (not isinstance(task, str) or not task.strip() or task.strip() in (".", "..")
            or "/" in task or "\\" in task or ".." in task or "\0" in task):
        raise ValueError("task 이름이 올바르지 않아요")
    card = read_card(repo, card_id)
    card["task"] = task.strip()
    _write_card(repo, card_id, card)
