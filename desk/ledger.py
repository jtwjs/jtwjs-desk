"""원장 텍스트 → 행. 전부 텍스트 · dict를 받는 순수 함수다(파일을 열지 않는다).

step 2: 학습 카드(`_learn/inbox.md`) · phase `reflect` · 항목 키.
"""
import hashlib
import re

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
