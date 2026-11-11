"""일간 JSON 여러 날을 합치는 순수 함수 (ADR-012). 파일을 열지 않는다.

입력은 관대하게 읽는다(키 없음·타입 틀림은 0 · 빈 목록). 반환은 새 dict이며
`prompts` · `title` · `cwd` 같은 원문 키와 카드 요지는 내보내지 않는다.
"""
from datetime import date, timedelta


def week_dates(today: date, n: int = 7) -> list[str]:
    """today를 포함한 최근 n일의 YYYY-MM-DD, 오래된 날부터."""
    return [(today - timedelta(days=i)).isoformat() for i in range(n - 1, -1, -1)]


def _int(value) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _list(value) -> list:
    return value if isinstance(value, list) else []


def aggregate(days: list) -> dict:
    """(날짜, 일간 JSON | None) 목록을 합친다."""
    missing = []
    present = sessions = stuck = cards = 0
    repos: dict[str, dict] = {}
    for date_str, data in days:
        if not isinstance(data, dict):
            missing.append(date_str)
            continue
        present += 1
        sessions += _int(data.get("sessions"))
        stuck += _int(data.get("stuck"))
        cards += sum(1 for c in _list(data.get("cards")) if isinstance(c, dict))
        for repo in _list(data.get("repos")):
            if not isinstance(repo, dict):
                continue
            name = repo.get("name")
            if not isinstance(name, str) or not name:
                continue
            entry = repos.setdefault(name, {"name": name, "commits": 0, "progress": []})
            entry["commits"] += _int(repo.get("commits"))
            for line in _list(repo.get("progress")):
                if isinstance(line, str) and line not in entry["progress"]:
                    entry["progress"].append(line)
    repo_rows = list(repos.values())
    return {
        "days": len(days),
        "present": present,
        "missing": missing,
        "sessions": sessions,
        "stuck": stuck,
        "commits": sum(r["commits"] for r in repo_rows),
        "cards": cards,
        "projects": len(repo_rows),
        "repos": repo_rows,
    }
