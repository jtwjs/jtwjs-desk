"""Claude Code 훅: 세션 이벤트 → 상태 파일 (ADR-002).

진입점 하나 `desk_hook.py <이벤트명>`이 SessionStart·UserPromptSubmit·
PostToolUse·Notification·PreCompact·Stop·SessionEnd마다 불린다
(실제 등록은 `hooks/hooks.json`).

🔴 CRITICAL(ADR-002 · CLAUDE.md): stdout·stderr에는 아무것도 쓰지 않고
항상 exit 0 — 모델 토큰 0. 어떤 예외든 세션을 막지 않는다(에러 로그 한 줄만).

함수형 코어(순수 — map_status·needs_server_check·needs_ntfy)와
가변 쉘(부수효과 — derive_repo·derive_branch·check_server_version·
spawn_server·send_ntfy·ensure_server)을 가른다
(`.claude/references/implementation-patterns.md` 패턴 1).

`hooks/`는 `desk/`만 import한다 — `page/`·`scripts/`는 import하지 않는다
(ARCHITECTURE 경계). 페이지 서버는 서브프로세스로 띄우지, import하지 않는다
(파일 경로만 안다).
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from desk import atomic, paths  # noqa: E402

_DEFAULT_PORT = 47615

_STATUS_MAP = {
    "SessionStart": "입력 대기",
    "UserPromptSubmit": "작업 중",
    "PostToolUse": "작업 중",
    "PreCompact": "작업 중",
    "Stop": "입력 대기",
}


# ---- 코어(순수) ----


def map_status(event_name: str, notification_type: str | None) -> str | None:
    """ADR-002 이벤트→상태 표 그대로. 모르는 이벤트(SessionEnd 포함)는 None."""
    if event_name == "Notification":
        if notification_type == "permission_prompt":
            return "승인 대기"
        if notification_type == "idle_prompt":
            return "입력 대기"
        return None
    return _STATUS_MAP.get(event_name)


def needs_server_check(event_name: str) -> bool:
    """SessionStart만 페이지 서버 확인이 필요하다(ADR-003)."""
    return event_name == "SessionStart"


def needs_ntfy(event_name: str, notification_type: str | None) -> bool:
    """Notification + permission_prompt만 ntfy가 필요하다(ADR-005)."""
    return event_name == "Notification" and notification_type == "permission_prompt"


# ---- 쉘(부수효과, 의존성은 인자로 주입) ----


def derive_repo(cwd: str) -> str:
    """git 최상위 폴더 이름. git이 없거나 레포가 아니면 cwd의 basename(ADR-001).

    예외를 올리지 않는다.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            top = result.stdout.strip()
            if top:
                return os.path.basename(top)
    except Exception:
        pass
    return os.path.basename(cwd)


def derive_branch(cwd: str) -> str:
    """현재 브랜치 이름. 실패하면 빈 문자열. 예외를 올리지 않는다."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def _resolve_port() -> int:
    """서버 포트: server.json에 적힌 값, 없으면 DESK_PORT·기본 47615(ADR-003)."""
    try:
        meta = json.loads(paths.server_meta_path().read_text(encoding="utf-8"))
        return int(meta.get("port", _DEFAULT_PORT))
    except Exception:
        return int(os.environ.get("DESK_PORT", _DEFAULT_PORT))


def _read_plugin_version() -> str:
    """이 플러그인의 현재 버전. CLAUDE_PLUGIN_ROOT가 없으면 이 파일 기준 상대 경로."""
    root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    base = Path(root) if root else _REPO_ROOT
    data = json.loads(
        (base / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    return data.get("version", "")


def check_server_version(timeout: float = 0.3) -> bool:
    """페이지 서버가 떠 있고 버전이 맞는가. 예외(연결 거부·타임아웃)는 False(ADR-003)."""
    try:
        port = _resolve_port()
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/version", timeout=timeout
        ) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("version") == _read_plugin_version()
    except Exception:
        return False


def spawn_server() -> None:
    """`page/server.py`를 서브프로세스로 띄운다 — import하지 않는다(ARCHITECTURE 경계).

    이 step 시점에는 `page/server.py`가 아직 없어도 된다(step 4가 만든다).
    """
    server_path = _REPO_ROOT / "page" / "server.py"
    subprocess.Popen(
        [sys.executable, str(server_path)],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )


def send_ntfy(topic: str, repo: str, status: str) -> None:
    """ntfy 알림을 떼어 낸 자식 프로세스로 보낸다.

    본문은 레포·상태만(`f"{repo} · {status}"`) — 브랜치·대화 내용 금지(ADR-005).
    자식 프로세스 안에서 urlopen에 5초 상한을 건다.
    """
    body = f"{repo} · {status}"
    code = (
        "import sys,urllib.request\n"
        "urllib.request.urlopen(\n"
        "    urllib.request.Request(sys.argv[1], data=sys.argv[2].encode('utf-8'), method='POST'),\n"
        "    timeout=5,\n"
        ")\n"
    )
    subprocess.Popen(
        [sys.executable, "-c", code, f"https://ntfy.sh/{topic}", body],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )


def ensure_server(check_fn=check_server_version, spawn_fn=spawn_server) -> None:
    """check_fn()이 False면 spawn_fn()을 부른다.

    테스트는 check_fn·spawn_fn을 가짜로 직접 주입한다(패턴 2 — 암묵적 입력 승격).
    """
    if not check_fn():
        spawn_fn()


# ---- 에러 로그 ----


def _log_hook_error(event_name, error: Exception) -> None:
    """예외를 한 줄로 기록한다. 로그 쓰기 자체가 실패해도 조용히 넘어간다."""
    try:
        log_path = paths.hook_error_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{time.time()} {event_name} {type(error).__name__}: {error}\n")
    except Exception:
        pass


def _delete_session_file(session_id) -> None:
    """상태 파일이 있으면 지운다. 없으면 조용히 넘어간다."""
    if not session_id:
        return
    path = paths.sessions_dir() / f"{session_id}.json"
    try:
        path.unlink()
    except FileNotFoundError:
        pass


# ---- 진입점 ----


def main(argv: list) -> int:
    """이벤트 하나를 처리한다. 어떤 예외든 삼키고 항상 0을 반환한다(ADR-002)."""
    event_name = None
    try:
        event_name = argv[1]
        payload = json.load(sys.stdin)

        if event_name == "SessionEnd":
            _delete_session_file(payload.get("session_id"))
            return 0

        notification_type = payload.get("notification_type")
        status = map_status(event_name, notification_type)
        if status is None:
            return 0

        session_id = payload.get("session_id")
        cwd = payload.get("cwd") or os.getcwd()
        repo = derive_repo(cwd)
        branch = derive_branch(cwd)

        session_data = {
            "repo": repo,
            "branch": branch,
            "status": status,
            "lastAt": time.time(),
        }
        session_path = paths.sessions_dir() / f"{session_id}.json"
        atomic.write_json_atomic(session_path, session_data)

        if needs_server_check(event_name):
            ensure_server()

        if needs_ntfy(event_name, notification_type):
            topic_path = paths.ntfy_topic_path()
            if topic_path.exists():
                topic = topic_path.read_text(encoding="utf-8").strip()
                if topic:
                    send_ntfy(topic, repo, status)

        return 0
    except Exception as e:  # noqa: BLE001 — ADR-002 "예외가 나도 세션을 막지 않는다"
        _log_hook_error(event_name, e)
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
