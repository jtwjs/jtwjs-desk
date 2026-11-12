"""기술 동향 텍스트 → 오늘/지난 글 · 잔디 · 북마크 목록. 계산 함수는 텍스트 · dict를 받는 순수 함수이고, 파일에 쓰는 함수(record_*)만 모듈 락을 잡는다.

계약(이 phase 전체가 같은 값을 쓴다):
- 동향 줄(wiki가 동향 파일에 씀): 필수 id · date(YYYY-MM-DD) · title · url · summary(전부 비어 있지 않은
  문자열). 같은 id는 마지막 줄이 이긴다. 필수 필드가 없거나 형식이 틀린 줄은 깨진 줄이다.
- 읽음 줄(desk가 읽음 파일에 덧붙임): {"id": str, "at": str}. 같은 id가 여럿이어도 읽음은 한 번이다.
- 북마크 줄(desk가 북마크 파일에 덧붙임): {"id": str, "on": bool, "at": str}. 글마다 마지막 줄이 현재 상태.
- 깨진 줄은 건너뛰고 개수를 센다. 모르는 필드는 무시한다.
- 오늘은 호출자가 넘긴 today. date == today 오늘 글, 앞선 날짜는 지난 글, 미래 날짜 글은 어디에도 세지 않는다.
- 글 한 건의 응답 모양: {"id","date","title","url","summary","read": bool,"bookmarked": bool}
"""
import json
import re
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

from desk import routine

HEATMAP_DAYS = 365
HEATMAP_MAX = 3

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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


def _valid_item(row) -> bool:
    return (isinstance(row, dict)
            and all(_nonempty_str(row.get(k)) for k in ("id", "title", "url", "summary"))
            and _valid_date(row.get("date")))


def _valid_read(row) -> bool:
    return (isinstance(row, dict) and _nonempty_str(row.get("id"))
            and isinstance(row.get("at"), str))


def _valid_mark(row) -> bool:
    return (isinstance(row, dict) and _nonempty_str(row.get("id"))
            and isinstance(row.get("on"), bool) and isinstance(row.get("at"), str))


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


def parse_items(text: str) -> tuple:
    """동향 텍스트 → (id → 마지막 줄 dict(처음 나온 순서), 깨진 줄 수)."""
    return _parse_lines(text, _valid_item)


def parse_reads(text: str) -> tuple:
    """읽음 텍스트 → (읽은 id 집합, 깨진 줄 수)."""
    rows, broken = _parse_lines(text, _valid_read)
    return set(rows), broken


def parse_marks(text: str) -> tuple:
    """북마크 텍스트 → (id → 마지막 줄의 on, 깨진 줄 수)."""
    rows, broken = _parse_lines(text, _valid_mark)
    return {i: r["on"] for i, r in rows.items()}, broken


def _view(row: dict, reads, marks) -> dict:
    return {"id": row["id"], "date": row["date"], "title": row["title"],
            "url": row["url"], "summary": row["summary"],
            "read": row["id"] in reads, "bookmarked": bool(marks.get(row["id"], False))}


def split_items(items: dict, reads, marks: dict, today: date) -> dict:
    """{"today": 오늘 글(파일 순서), "past_unread": 지난 안 읽은 글(날짜 내림차순, 같은 날은 파일 순서)}."""
    out = {"today": [], "past_unread": []}
    for row in items.values():
        d = date.fromisoformat(row["date"])
        if d == today:
            out["today"].append(_view(row, reads, marks))
        elif d < today and row["id"] not in reads:
            out["past_unread"].append(_view(row, reads, marks))
    out["past_unread"].sort(key=lambda g: g["date"], reverse=True)  # 안정 정렬
    return out


def heatmap(items: dict, reads, today: date, days: int = HEATMAP_DAYS) -> list:
    """today를 끝으로 days일치(오래된 날부터). 칸 = {"date", "total", "read"}.

    글의 date로 묶는다. total은 자르지 않고, read는 distinct 읽은 id 수를 HEATMAP_MAX로 자른다.
    동향에 없는 읽음 id는 세지 않는다. 북마크는 모른다.
    """
    total, read = {}, {}
    for row in items.values():
        total[row["date"]] = total.get(row["date"], 0) + 1
        if row["id"] in reads:
            read[row["date"]] = read.get(row["date"], 0) + 1
    cells = []
    for offset in range(days - 1, -1, -1):
        key = (today - timedelta(days=offset)).isoformat()
        cells.append({"date": key, "total": total.get(key, 0),
                      "read": min(read.get(key, 0), HEATMAP_MAX)})
    return cells


def bookmark_list(items: dict, reads, marks: dict) -> list:
    """마지막 줄이 on인 글 중 동향에 있는 것만, 날짜 내림차순(같은 날은 파일 순서)."""
    rows = [_view(row, reads, marks) for row in items.values() if marks.get(row["id"])]
    rows.sort(key=lambda g: g["date"], reverse=True)
    return rows


def unread_count(items: dict, reads, today: date) -> int:
    """미래 글을 뺀, 동향에 있고 읽음 집합에 없는 글 수."""
    return sum(1 for row in items.values()
               if date.fromisoformat(row["date"]) <= today and row["id"] not in reads)


# --- 쓰기 껍질(파일 I/O). 읽음 · 북마크 파일에 쓰는 모든 경로가 _LOCK을 잡는다 -------------
# 서버가 ThreadingHTTPServer라 요청이 겹칠 수 있다. 락 안에서 파일을 다시 읽어 멱등을 지킨다.
# 동향 파일은 wiki가 쓰고 desk는 읽기만 한다. OSError는 삼키지 않고 올린다(서버가 500으로 바꾼다).
_LOCK = threading.Lock()


def _append_line(path: Path, line: dict) -> None:
    """JSON 한 줄을 한 번의 write로 덧붙인다. 끝 개행이 없으면 개행부터. 락은 호출자가 잡는다."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(line, ensure_ascii=False) + "\n"
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            if f.tell() > 0:
                f.seek(-1, 2)
                if f.read(1) != b"\n":
                    payload = "\n" + payload
    except OSError:
        pass
    with open(path, "a", encoding="utf-8") as f:
        f.write(payload)


def record_read(items_path, reads_path, item_id: str, now: datetime) -> str:
    """"unknown_id"(동향에 없음) · "duplicate"(이미 읽음) · "ok"(한 줄 덧붙임)."""
    with _LOCK:
        items, _ = parse_items(routine.read_text_or_none(items_path) or "")
        if item_id not in items:
            return "unknown_id"
        reads, _ = parse_reads(routine.read_text_or_none(reads_path) or "")
        if item_id in reads:
            return "duplicate"
        _append_line(reads_path, {"id": item_id, "at": now.isoformat()})
        return "ok"


def record_mark(items_path, marks_path, item_id: str, on: bool, now: datetime) -> str:
    """"unknown_id" · "same"(현재 상태가 on과 같음, 없으면 꺼짐) · "ok"(한 줄 덧붙임)."""
    with _LOCK:
        items, _ = parse_items(routine.read_text_or_none(items_path) or "")
        if item_id not in items:
            return "unknown_id"
        marks, _ = parse_marks(routine.read_text_or_none(marks_path) or "")
        if bool(marks.get(item_id, False)) == on:
            return "same"
        _append_line(marks_path, {"id": item_id, "on": on, "at": now.isoformat()})
        return "ok"
