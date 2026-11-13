"""가설 게이트 원장 텍스트 → 신호 띠 숫자. 전부 텍스트 · 리스트를 받는 순수 함수이고 파일을 읽거나 쓰지 않는다.

계약(step 3의 응답이 compute_signal의 dict를 그대로 싣는다):
- 맡김 줄: ts, repo, task, gate, area, hyp, rec, acc, why, rebut, skip. 누락 키는 빈 값으로 읽는다.
- 적중 줄: {ref(원 줄의 ts), hit(right|partial|wrong), by}. 같은 ref는 마지막 줄만 센다.
- 의미 있는 줄 = gate · hyp · rec 중 하나라도 채워진 맡김 줄.
- 출력에는 원문 칸의 값을 싣지 않는다(숫자 · 불리언 · 줄 번호 · 고정 이유 문구뿐).
"""
import json

AREAS = ("FE", "BE", "infra", "domain")
HITS = ("right", "partial", "wrong")
UNKNOWN_REPO = "(알수없음)"


def parse_ledger(text: str) -> tuple:
    """원장 텍스트 → (줄 dict 목록, 깨진 줄 [{"line", "reason"}]). 빈 줄은 무시한다."""
    rows, broken = [], []
    for no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            broken.append({"line": no, "reason": "JSON 아님"})
            continue
        if not isinstance(row, dict):
            broken.append({"line": no, "reason": "객체 아님"})
            continue
        rows.append(row)
    return rows, broken


def _pct(n: int, m: int) -> dict:
    return {"n": n, "m": m, "pct": None if m == 0 else round(100 * n / m)}


def _flag(row: dict, key: str) -> bool:
    return row.get(key) is True


def _gate(row: dict) -> bool:
    gate = row.get("gate")
    return isinstance(gate, str) and bool(gate.strip())


def _text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _is_hit(row: dict) -> bool:
    return "ref" in row


def _meaningful(row: dict) -> bool:
    return _gate(row) or _flag(row, "hyp") or _flag(row, "rec")


def _in_denominator(row: dict) -> bool:
    return _flag(row, "rec") and _gate(row)


def _accept_no_reason(row: dict) -> bool:
    return _in_denominator(row) and _flag(row, "acc") and not _flag(row, "why")


def _area_of(row: dict) -> str:
    area = row.get("area")
    return area if area in AREAS else "unknown"


def _last_hits(rows: list) -> dict:
    hits = {}
    for row in rows:
        if _is_hit(row) and row.get("hit") in HITS:
            hits[str(row["ref"])] = row["hit"]
    return hits


def _streak_and_reask(entries: list, threshold) -> tuple:
    """(repo, task)가 있는 맡김 줄을 원장 순서대로 읽어 (연속 값, 재요구 켜짐)을 낸다."""
    streak, reasked = 0, False
    current, seen_hyp, seen_rebut = None, False, False
    for row in entries:
        key = (_text(row.get("repo")), _text(row.get("task")))
        if key != current:
            current, streak = key, 0
            seen_hyp = seen_rebut = False
        if reasked:
            seen_hyp = seen_hyp or _flag(row, "hyp")
            seen_rebut = seen_rebut or _flag(row, "rebut")
            if seen_hyp and seen_rebut:
                reasked = False
                seen_hyp = seen_rebut = False
        if _accept_no_reason(row):
            streak += 1
            # 켜지는 건 연속이 늘어난 줄에서만이다(꺼진 직후 같은 값으로 다시 켜지지 않게)
            if (not reasked and isinstance(threshold, int) and not isinstance(threshold, bool)
                    and streak >= threshold):
                reasked = True
                seen_hyp = seen_rebut = False
        elif _flag(row, "why"):
            streak = 0
    return streak, reasked


def _is_correction(row: dict) -> bool:
    return "ref" in row and "gate" in row and row.get("hit") not in HITS


def _apply_corrections(rows: list) -> list:
    """맡김 줄 목록에 보정(같은 ref는 마지막)을 덮어쓴 새 목록. 없는 ref의 보정은 무시한다."""
    fixes = {str(r["ref"]): r["gate"] for r in rows if _is_correction(r)}
    if not fixes:
        return [r for r in rows if not _is_hit(r)]
    out = []
    for r in rows:
        if _is_hit(r):
            continue
        key = str(r.get("ts"))
        out.append({**r, "gate": fixes[key]} if key in fixes else r)
    return out


def _repo_of(row: dict) -> str:
    return _text(row.get("repo")) or UNKNOWN_REPO


def repos_of(rows: list) -> list:
    """맡김 줄(ref 없음)의 레포 이름을 나온 순서로 중복 없이. 「(알수없음)」은 있으면 맨 뒤 한 번."""
    names, unknown = [], False
    for row in rows:
        if _is_hit(row):
            continue
        name = _repo_of(row)
        if name == UNKNOWN_REPO:
            unknown = True
        elif name not in names:
            names.append(name)
    return names + [UNKNOWN_REPO] if unknown else names


def filter_rows(rows: list, repo) -> list:
    """repo 맡김 줄과, ref가 그 줄의 ts인 적중·보정 줄만. repo가 None이거나 모르는 이름이면 rows 그대로."""
    if repo is None or repo not in repos_of(rows):
        return rows
    kept = {str(r.get("ts")) for r in rows if not _is_hit(r) and _repo_of(r) == repo}
    return [r for r in rows
            if (str(r["ref"]) in kept if _is_hit(r) else _repo_of(r) == repo)]


def diff_table(rows: list) -> dict:
    """의미 있는 줄(보정 반영)을 난이도(easy·mid·hard·none) × 상태(right·partial·wrong·pending)로 센다."""
    hits = _last_hits(rows)
    table = {k: {"right": 0, "partial": 0, "wrong": 0, "pending": 0}
             for k in ("easy", "mid", "hard", "none")}
    for row in _apply_corrections(rows):
        if not _meaningful(row):
            continue
        level = row.get("diff")
        cell = table[level if level in ("easy", "mid", "hard") else "none"]
        hit = hits.get(str(row.get("ts")))
        if hit:
            cell[hit] += 1
        elif _flag(row, "hyp"):
            cell["pending"] += 1
    return table


def compute_signal(rows: list, broken: list, streak_threshold=None) -> dict:
    hits = _last_hits(rows)
    ledger = _apply_corrections(rows)
    meaningful = [r for r in ledger if _meaningful(r)]

    areas = {a: {"count": 0, "right": 0, "partial": 0, "wrong": 0, "pending": 0,
                 "acc_no_reason": {"n": 0, "m": 0}} for a in AREAS}
    unknown_area = 0
    for row in meaningful:
        area = _area_of(row)
        if area == "unknown":
            unknown_area += 1
            continue
        card = areas[area]
        card["count"] += 1
        hit = hits.get(str(row.get("ts")))
        if hit:
            card[hit] += 1
        elif _flag(row, "hyp"):
            card["pending"] += 1
    for row in ledger:
        if _in_denominator(row) and _area_of(row) != "unknown":
            counter = areas[_area_of(row)]["acc_no_reason"]
            counter["m"] += 1
            counter["n"] += _accept_no_reason(row)
    for card in areas.values():
        c = card["acc_no_reason"]
        card["acc_no_reason"] = _pct(c["n"], c["m"])

    identified = [r for r in ledger if _text(r.get("task"))]
    streak, reasked = _streak_and_reask(identified, streak_threshold)

    return {
        "areas": areas,
        "unknown_area": unknown_area,
        "hyp_first": _pct(sum(_flag(r, "hyp") for r in meaningful), len(meaningful)),
        "acc_no_reason": _pct(sum(_accept_no_reason(r) for r in ledger),
                              sum(_in_denominator(r) for r in ledger)),
        "streak": streak,
        "reasked": reasked,
        "skipped": sum(_flag(r, "skip") for r in ledger),
        "no_ident": len(ledger) - len(identified),
        "broken": [{"line": b["line"], "reason": b["reason"]} for b in broken],
        "meaningful": len(meaningful),
        "empty": not ledger,
    }
