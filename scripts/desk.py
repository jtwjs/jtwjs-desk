"""지휘가 Bash로 직접 부르는 CLI (ADR-006).

`scripts/`는 `desk/`만 import한다 — `hooks/`·`page/`는 import하지 않는다
(ARCHITECTURE 경계). 서브커맨드 4개: `ask` · `picks --new` · `applied` · `prune`.

🔴 CRITICAL(CLAUDE.md): 사람 이름·vault 원문·세션 대화 원문을 질문·선택·반영
파일에 넣지 않는다. `validate_ask`가 막는 필드 밖에 자유 텍스트 필드(`question`·
`why`·`note` 등)가 있으므로, 이 스크립트 자체가 내용을 검사하진 않는다 —
쓰는 사람(지휘)이 지키는 규칙이다.
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from desk import atomic, paths, validate  # noqa: E402


def _read_raw(raw: str) -> str:
    """raw가 "-"면 stdin에서, 아니면 파일 경로에서 텍스트를 읽는다."""
    if raw == "-":
        return sys.stdin.read()
    return Path(raw).read_text(encoding="utf-8")


def cmd_ask(repo: str, raw: str) -> int:
    """질문 파일을 쓴다. 형식 위반·중복 id·읽기 실패면 stderr + 1."""
    try:
        text = _read_raw(raw)
    except OSError as e:
        print(f"ask: raw를 읽을 수 없다: {e}", file=sys.stderr)
        return 1

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"ask: raw가 올바른 JSON이 아니다: {e}", file=sys.stderr)
        return 1

    violations = validate.validate_ask(data)
    if violations:
        print(f"ask: 어긴 필드 {violations}", file=sys.stderr)
        return 1

    ask_path = paths.inbox_dir(repo) / f"{data['id']}.json"
    if ask_path.exists():
        print(f"ask: 같은 id가 이미 있다 — 덮어쓰지 않는다: {data['id']}", file=sys.stderr)
        return 1

    atomic.write_json_atomic(ask_path, {**data, "createdAt": time.time()})
    return 0


def _pick_at_epoch(pick: dict):
    """pick의 'at'(ISO 문자열)을 epoch(float)로. 형식이 나쁘면 None."""
    at = pick.get("at")
    if not isinstance(at, str):
        return None
    try:
        return datetime.fromisoformat(at).timestamp()
    except ValueError:
        return None


def _repo_names() -> list:
    inbox_root = paths.desk_home_dir() / "inbox"
    if not inbox_root.exists():
        return []
    return sorted(p.name for p in inbox_root.iterdir() if p.is_dir())


def cmd_picks_new(repo, since) -> int:
    """반영 파일이 없는 선택만(필요하면 since 이후로 갱신된 것만) 한 줄씩 stdout에."""
    repos = [repo] if repo is not None else _repo_names()

    for r in repos:
        repo_dir = paths.inbox_dir(r)
        if not repo_dir.exists():
            continue
        for pick_path in sorted(repo_dir.glob("*.pick.json")):
            id_ = pick_path.name[: -len(".pick.json")]
            applied_path = repo_dir / f"{id_}.applied.json"
            if applied_path.exists():
                continue

            try:
                pick = json.loads(pick_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue

            if since is not None:
                at_epoch = _pick_at_epoch(pick)
                if at_epoch is None or not (at_epoch > since):
                    continue

            print(json.dumps({"repo": r, "id": id_, **pick}, ensure_ascii=False))

    return 0


def cmd_applied(repo: str, id: str, issue, follow_up) -> int:
    """반영 파일을 쓴다. 질문 파일이 없으면 stderr + 1(재반영은 덮어쓴다)."""
    ask_path = paths.inbox_dir(repo) / f"{id}.json"
    if not ask_path.exists():
        print(f"applied: 질문 파일이 없다(ask를 먼저 해야 한다): {repo}/{id}", file=sys.stderr)
        return 1

    applied_path = paths.inbox_dir(repo) / f"{id}.applied.json"
    atomic.write_json_atomic(
        applied_path,
        {"appliedAt": time.time(), "issue": issue, "followUp": list(follow_up or [])},
    )
    return 0


def cmd_prune(days: int = 7) -> int:
    """반영된 지 days일 지난 판정의 질문·선택·반영 세 파일을 지운다."""
    threshold_seconds = days * 86400
    now = time.time()
    pruned = 0

    for r in _repo_names():
        repo_dir = paths.inbox_dir(r)
        for applied_path in sorted(repo_dir.glob("*.applied.json")):
            id_ = applied_path.name[: -len(".applied.json")]
            try:
                applied = json.loads(applied_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue

            applied_at = applied.get("appliedAt")
            if not isinstance(applied_at, (int, float)):
                continue
            if now - applied_at <= threshold_seconds:
                continue

            for suffix in (".json", ".pick.json", ".applied.json"):
                try:
                    (repo_dir / f"{id_}{suffix}").unlink()
                except FileNotFoundError:
                    pass
            pruned += 1

    print(f"pruned {pruned}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="desk.py")
    sub = parser.add_subparsers(dest="command", required=True)

    ask_parser = sub.add_parser("ask")
    ask_parser.add_argument("repo")
    ask_parser.add_argument("raw")

    picks_parser = sub.add_parser("picks")
    picks_parser.add_argument("--new", action="store_true", required=True)
    picks_parser.add_argument("--repo", default=None)
    picks_parser.add_argument("--since", type=float, default=None)

    applied_parser = sub.add_parser("applied")
    applied_parser.add_argument("repo")
    applied_parser.add_argument("id")
    applied_parser.add_argument("--issue", default=None)
    applied_parser.add_argument(
        "--follow-up", dest="follow_up", action="append", default=[]
    )

    prune_parser = sub.add_parser("prune")
    prune_parser.add_argument("--days", type=int, default=7)

    return parser


def main(argv: list) -> int:
    """서브커맨드를 라우팅한다. 알 수 없는 커맨드·인자 오류는 argparse 기본 동작에 맡긴다."""
    parser = _build_parser()
    args = parser.parse_args(argv[1:])

    if args.command == "ask":
        return cmd_ask(args.repo, args.raw)
    if args.command == "picks":
        return cmd_picks_new(args.repo, args.since)
    if args.command == "applied":
        return cmd_applied(args.repo, args.id, args.issue, args.follow_up)
    if args.command == "prune":
        return cmd_prune(args.days)
    return 2  # pragma: no cover — required=True가 먼저 걸린다


if __name__ == "__main__":
    sys.exit(main(sys.argv))
