"""원장 텍스트 → 행. 전부 텍스트 · dict를 받는 순수 함수다(파일을 열지 않는다).

step 2: 학습 카드(`_learn/inbox.md`) · phase `reflect` · 항목 키.
step 3: observations · friction · 워크플로우 행 · score. `find_score_file`만 디렉터리 목록을 본다.
"""
import hashlib
import json
import re
from datetime import date
from pathlib import Path

_HEADING = re.compile(r"^## (\d{4}-\d{2}-\d{2}) · (.+?)\s*$")
_KINDS = ("막힌 질문", "기술", "직무", "도메인")
_REVIEW_KINDS = ("기술", "도메인", "막힌 질문")
_STATUS_ORDER = {"모름": 0, "설명 들음": 1, "내 말로 설명 가능": 2}
_UNKNOWN_STATUS = 3

_FE_EXT = (".tsx", ".jsx", ".vue", ".css", ".scss")
_FE_DIRS = ("components/", "pages/", "app/", "apps/web")
_BE_EXT = (".kt", ".java", ".py", ".go", ".sql")
_BE_DIRS = ("src/main/", "api/", "server/", "controller/", "service/",
            "repository/", "migration")
_INFRA_EXT = (".tf",)
_INFRA_DIRS = (".github/workflows/", "k8s/", "helm/", "charts/", "terraform/")
_INFRA_BASE = ("dockerfile", "docker-compose", "nginx")


def _field(line: str, name: str):
    prefix = f"- {name}:"
    return line[len(prefix):].strip() if line.startswith(prefix) else None


def _parse_kind(value: str) -> str:
    for kind in _KINDS:
        if value.startswith(kind):
            return kind
    return ""


def _parse_where(value: str) -> str:
    m = re.search(r"`([^`]+)`", value)
    return m.group(1) if m else ""


def parse_inbox(text: str) -> list:
    """`## YYYY-MM-DD · 제목` 카드를 dict 목록으로. 주석 블록 안은 건너뛴다."""
    cards = []
    current = None
    in_comment = False
    for raw in text.splitlines():
        line = raw.rstrip()
        if in_comment:
            if "-->" in line:
                in_comment = False
            continue
        if line.lstrip().startswith("<!--"):
            if "-->" not in line:
                in_comment = True
            continue
        if line.startswith("## "):
            m = _HEADING.match(line)
            if m:
                current = {"title": m.group(2), "date": m.group(1), "kind": "",
                           "status": "", "where": "", "vault": "", "summary": ""}
                cards.append(current)
            else:
                current = None
            continue
        if current is None:
            continue
        for name, key, conv in (("종류", "kind", _parse_kind),
                                ("상태", "status", str),
                                ("이 레포 어디", "where", _parse_where),
                                ("vault", "vault", str),
                                ("요지", "summary", str)):
            value = _field(line, name)
            if value is not None:
                current[key] = conv(value)
                break
    return cards


def review_cards(cards: list) -> list:
    """기술 · 도메인 · 막힌 질문 중 `vault`가 빈 카드(직무는 뺀다, ADR-013)."""
    return [c for c in cards if c.get("kind") in _REVIEW_KINDS and not c.get("vault")]


def _is_fe(path: str) -> bool:
    return path.endswith(_FE_EXT) or any(d in path for d in _FE_DIRS)


def _is_be(path: str) -> bool:
    return path.endswith(_BE_EXT) or any(d in path for d in _BE_DIRS)


def _is_infra(path: str) -> bool:
    base = path.rsplit("/", 1)[-1].lower()
    return (path.endswith(_INFRA_EXT)
            or any(d in path for d in _INFRA_DIRS)
            or base.startswith(_INFRA_BASE))


def classify_area(where: str, kind: str) -> str:
    """도메인 종류면 domain, 아니면 경로 신호로 fe → be → infra 순, 못 가르면 미분류."""
    if kind == "도메인":
        return "domain"
    path = where or ""
    if _is_fe(path):
        return "fe"
    if _is_be(path):
        return "be"
    if _is_infra(path):
        return "infra"
    return "미분류"


def fullstack_order(cards: list) -> list:
    """복습 순서: 모름 → 설명 들음 → 내 말로 설명 가능, 모르는 값은 맨 뒤. 안정 정렬."""
    return sorted(cards, key=lambda c: _STATUS_ORDER.get(c.get("status"), _UNKNOWN_STATUS))


def card_key(title: str) -> str:
    return "card-" + hashlib.sha1(title.encode("utf-8")).hexdigest()[:8]


def phase_key(task: str) -> str:
    return "phase-" + task


def skipped_phases(indexes: list) -> list:
    """`reflect.understanding_check == "skipped"`인 task 이름. 형식이 틀리면 건너뛴다."""
    out = []
    for task, index in indexes:
        if not isinstance(index, dict):
            continue
        reflect = index.get("reflect")
        if isinstance(reflect, dict) and reflect.get("understanding_check") == "skipped":
            out.append(task)
    return out


# ---- step 3: observations · friction · score ----

_DATE_DIR = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SCORE_NAME = "ai-readiness-score.json"
_FRICTION_OPEN = ("열림", "보류")
_GRADE_COLORS = ("green", "amber", "red")


def _cells(line: str):
    """`| a | b |` 한 줄을 칸 목록으로. 표 줄이 아니면 None."""
    s = line.strip()
    if not s.startswith("|"):
        return None
    s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _is_separator(cells) -> bool:
    return all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c) and any(cells)


def _to_int(value: str):
    return int(value) if re.fullmatch(r"\d+", value) else None


def parse_observations(text: str) -> list:
    """`## 열린 것` 표의 행만. 다음 `## ` 헤딩에서 멈춘다."""
    rows = []
    in_open = False
    header_seen = False
    for line in text.splitlines():
        if line.startswith("## "):
            if in_open:
                break
            in_open = line[3:].strip() == "열린 것"
            continue
        if not in_open:
            continue
        cells = _cells(line)
        if cells is None or _is_separator(cells):
            continue
        if not header_seen:
            header_seen = True
            continue
        cells = (cells + [""] * 5)[:5]
        count = _to_int(cells[2])
        row = {"pattern": cells[0], "kind": cells[1], "count": count,
               "last": cells[3], "evidence": cells[4]}
        if count is None:
            row["unparsed"] = True
        rows.append(row)
    return rows


def parse_friction(text: str) -> list:
    """가정형 파서(ADR-013). 열림 · 보류 행만. 못 읽는 행은 원문 없이 `{"unparsed": True}`."""
    header = None
    rows = []
    saw_table = False
    for line in text.splitlines():
        cells = _cells(line)
        if cells is None:
            continue
        saw_table = True
        if _is_separator(cells):
            continue
        if header is None:
            if "상태" in cells and "횟수" in cells:
                header = cells
            continue
        if len(cells) != len(header):
            rows.append({"unparsed": True})
            continue
        status = cells[header.index("상태")]
        if status not in _FRICTION_OPEN:
            continue
        rows.append({"pattern": cells[0], "status": status,
                     "count": _to_int(cells[header.index("횟수")])})
    if header is None and (saw_table or text.strip()):
        return [{"unparsed": True}]
    return rows


def workflow_rows(obs: list, friction: list) -> list:
    """observations + friction을 한 목록으로. count 내림차순, None은 맨 뒤(안정 정렬)."""
    merged = []
    for source, items in (("observations", obs), ("friction", friction)):
        for item in items:
            row = dict(item)
            count = row.get("count")
            row["source"] = source
            row["highlight"] = count is not None and count >= 3
            merged.append(row)
    return sorted(merged, key=lambda r: (r.get("count") is None, -(r.get("count") or 0)))


def parse_score(text: str):
    """JSON에서 `total` · `grade` · (유효하면) `grade_color`만. 깨졌거나 키가 없으면 None."""
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or "total" not in data or "grade" not in data:
        return None
    result = {"total": data["total"], "grade": data["grade"]}
    color = data.get("grade_color")
    if isinstance(color, str) and color.lower() in _GRADE_COLORS:
        result["grade_color"] = color.lower()
    return result


def find_score_file(repo_root: Path):
    """ADR-013 순서로 score 파일 위치를 찾는다. (경로, 채점일 문자열 | None) 또는 None."""
    reports = repo_root / ".claude" / "reports"
    if reports.is_dir():
        dated = sorted((d.name for d in reports.iterdir()
                        if d.is_dir() and _DATE_DIR.match(d.name)), reverse=True)
        for name in dated:
            candidate = reports / name / _SCORE_NAME
            if candidate.is_file():
                return candidate, name
    for base in (repo_root / "docs", repo_root / ".claude", repo_root):
        candidate = base / _SCORE_NAME
        if candidate.is_file():
            return candidate, None
    return None


def age_days(scored_on: date, today: date) -> int:
    return max((today - scored_on).days, 0)
