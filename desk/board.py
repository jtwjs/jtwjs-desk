"""칸반 카드 순수 함수 — 검증 · 열 전이 · 경과 일수 · 후보 표식 · 연결 상태 · 진행도.

파일을 열지 않고 시각·오늘 날짜는 인자로 받는다(파일 읽기·쓰기는 이후 step).
계약: docs/desk-kanban-2026-11-14/ARCHITECTURE.md 「상태 규약」.
"""
from datetime import date, datetime

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
