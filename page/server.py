"""127.0.0.1 페이지 서버 — 상태 JSON 제공·pick 저장·버전 응답 (ADR-003·ADR-004).

`page/`는 `desk/`만 import한다 — `hooks/`·`scripts/`는 import하지 않는다
(ARCHITECTURE 경계). 외부 패키지 없음 — `http.server` 표준 라이브러리만 쓴다.

🔴 CRITICAL(CLAUDE.md·ADR-004): 사람 이름·vault 원문·세션 대화 원문을 응답
JSON에 넣지 않는다 — `GET /judgments`·`GET /sessions`는 inbox·세션 파일에
있는 그대로를 돌려줄 뿐 추가 정보를 만들어내지 않는다.

🔴 CRITICAL(step4 지시문): `POST /pick`이 pick.json에 쓰는 `at`은
`datetime.now().isoformat()` **문자열**이다. `time.time()` float을 쓰면
`desk/validate.py`의 `validate_pick`과 `scripts/desk.py`의
`cmd_picks_new`(`datetime.fromisoformat(at)`로 파싱)가 깨진다.
"""

import json
import os
import secrets
import socket
import sys
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from desk import atomic, paths, sort, validate  # noqa: E402

_DEFAULT_PORT = 47615
_INDEX_HTML_PATH = Path(__file__).resolve().parent / "index.html"
_TOKEN_PLACEHOLDER = "__DESK_TOKEN__"


# ---- 코어(순수) ----


def check_host(headers, port: int) -> bool:
    """Host 헤더가 정확히 127.0.0.1:<port>인지(ADR-004). headers는 .get()을 지원하면 된다."""
    host = headers.get("Host") if hasattr(headers, "get") else None
    return host == f"127.0.0.1:{port}"


def read_plugin_version() -> str:
    """플러그인 버전. CLAUDE_PLUGIN_ROOT가 없으면 이 파일 기준 상대 경로로 폴백."""
    root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    base = Path(root) if root else _REPO_ROOT
    data = json.loads(
        (base / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    return data.get("version", "")


def generate_token() -> str:
    """페이지 토큰(ADR-004) — 무작위 32자 16진수."""
    return secrets.token_hex(16)


# ---- 쉘(부수효과) ----


def write_server_meta(port: int, pid: int, version: str, token: str) -> None:
    """server.json에 원자적으로 쓰고 권한을 0600으로 한다(ADR-004)."""
    path = paths.server_meta_path()
    atomic.write_json_atomic(
        path, {"port": port, "pid": pid, "version": version, "token": token}
    )
    os.chmod(path, 0o600)


def bind_or_exit(port: int):
    """127.0.0.1:port에 bind를 시도한다.

    성공하면 bind된 소켓을 돌려준다. OSError(포트 사용 중)면 이미 떠 있는
    것으로 보고 None을 돌려준다(ADR-003) — 호출부가 즉시 종료해야 한다.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
    except OSError:
        sock.close()
        return None
    return sock


def _repo_names(repo: str | None) -> list:
    """inbox의 레포 이름 목록. repo가 주어지면 그 레포 디렉터리가 있을 때만 하나."""
    inbox_root = paths.desk_home_dir() / "inbox"
    if repo is not None:
        return [repo] if (inbox_root / repo).exists() else []
    if not inbox_root.exists():
        return []
    return sorted(p.name for p in inbox_root.iterdir() if p.is_dir())


def _read_json_or_none(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def list_sessions() -> list:
    """세션 상태 디렉터리의 모든 *.json을 정렬해 돌려준다(desk.sort.sort_sessions)."""
    sdir = paths.sessions_dir()
    sessions = []
    if sdir.exists():
        for f in sorted(sdir.glob("*.json")):
            data = _read_json_or_none(f)
            if data is not None:
                sessions.append(data)
    return sort.sort_sessions(sessions, now=time.time())


def list_judgments(repo: str | None = None) -> list:
    """레포별 판정 카드 목록 — ask 내용 + 있으면 pick + 있으면 applied.

    반영 여부로 목록에서 빼지 않는다(PRD "반영된 것도 화면에 반영됨으로 보인다").
    """
    cards = []
    for r in _repo_names(repo):
        repo_dir = paths.inbox_dir(r)
        for f in sorted(repo_dir.glob("*.json")):
            name = f.name
            if name.endswith(".pick.json") or name.endswith(".applied.json"):
                continue
            id_ = name[: -len(".json")]
            ask_data = _read_json_or_none(f)
            if ask_data is None:
                continue
            card = {**ask_data, "repo": r}

            pick_data = _read_json_or_none(repo_dir / f"{id_}.pick.json")
            if pick_data is not None:
                card["pick"] = pick_data

            applied_data = _read_json_or_none(repo_dir / f"{id_}.applied.json")
            if applied_data is not None:
                card["applied"] = applied_data

            cards.append(card)
    return cards


def spawn_pick_candidate(body: dict) -> dict:
    """요청 바디에서 repo·id를 뺀 나머지 + at(ISO 문자열)을 더한 pick 후보.

    at은 datetime.now().isoformat() 문자열이다 — time.time() float이 아니다
    (step4 지시문 CRITICAL, scripts.desk.cmd_picks_new와의 계약).
    """
    pick_fields = {k: v for k, v in body.items() if k not in ("repo", "id")}
    return {**pick_fields, "at": datetime.now().isoformat()}


# ---- 요청 핸들러 ----


class _DeskRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):  # noqa: A002 — BaseHTTPRequestHandler 시그니처
        pass  # 접속 로그를 stdout에 내지 않는다

    def _port(self) -> int:
        return self.server.desk_port

    def _token(self) -> str:
        return self.server.desk_token

    def _send_json(self, status: int, payload) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, status: int, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # -- GET --

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/version":
            self._send_json(200, {"version": read_plugin_version()})
            return

        if parsed.path == "/sessions":
            if not check_host(self.headers, self._port()):
                self._send_json(403, {"error": "bad host"})
                return
            self._send_json(200, list_sessions())
            return

        if parsed.path == "/judgments":
            if not check_host(self.headers, self._port()):
                self._send_json(403, {"error": "bad host"})
                return
            qs = parse_qs(parsed.query)
            repo = qs.get("repo", [None])[0]
            self._send_json(200, list_judgments(repo))
            return

        if parsed.path == "/":
            html = _INDEX_HTML_PATH.read_text(encoding="utf-8").replace(
                _TOKEN_PLACEHOLDER, self._token()
            )
            self._send_html(200, html)
            return

        self._send_json(404, {"error": "not found"})

    # -- POST --

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/pick":
            self._handle_pick()
            return

        if parsed.path == "/shutdown":
            self._handle_shutdown()
            return

        self._send_json(404, {"error": "not found"})

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _handle_pick(self):
        if self.headers.get("X-Desk-Token") != self._token():
            self._send_json(403, {"error": "bad token"})
            return

        if self.headers.get("Origin") != f"http://127.0.0.1:{self._port()}":
            self._send_json(403, {"error": "bad origin"})
            return

        if not check_host(self.headers, self._port()):
            self._send_json(403, {"error": "bad host"})
            return

        try:
            body = self._read_json_body()
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(400, {"error": "bad json"})
            return

        repo = body.get("repo")
        id_ = body.get("id")
        if not repo or not id_:
            self._send_json(400, {"error": "repo/id required"})
            return

        ask_path = paths.inbox_dir(repo) / f"{id_}.json"
        if not ask_path.exists():
            self._send_json(404, {"error": "ask not found"})
            return

        applied_path = paths.inbox_dir(repo) / f"{id_}.applied.json"
        if applied_path.exists():
            self._send_json(409, {"error": "already applied"})
            return

        candidate = spawn_pick_candidate(body)
        violations = validate.validate_pick(candidate)
        if violations:
            self._send_json(400, {"violations": violations})
            return

        pick_path = paths.inbox_dir(repo) / f"{id_}.pick.json"
        atomic.write_json_atomic(pick_path, candidate)
        self._send_json(200, {"ok": True})

    def _handle_shutdown(self):
        if self.headers.get("X-Desk-Token") != self._token():
            self._send_json(403, {"error": "bad token"})
            return
        self._send_json(200, {"ok": True})
        self.server.shutdown()


class _DeskHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False


# ---- 진입점 ----


def serve_forever(port: int | None = None) -> None:
    """포트에 bind → 토큰 생성 → server.json 쓰기 → HTTP 서버 루프(ADR-003).

    bind_or_exit가 None(이미 떠 있음)이면 즉시 돌아온다 — 아무것도 더 하지 않는다.
    """
    if port is None:
        port = int(os.environ.get("DESK_PORT", _DEFAULT_PORT))

    sock = bind_or_exit(port)
    if sock is None:
        return

    sock.listen(5)
    token = generate_token()
    version = read_plugin_version()
    write_server_meta(port, os.getpid(), version, token)

    httpd = _DeskHTTPServer(
        ("127.0.0.1", port), _DeskRequestHandler, bind_and_activate=False
    )
    httpd.socket.close()  # bind_and_activate=False라 자기가 만든 소켓은 안 쓴다
    httpd.socket = sock
    httpd.server_address = sock.getsockname()
    httpd.desk_token = token
    httpd.desk_port = port

    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()


if __name__ == "__main__":
    serve_forever()
