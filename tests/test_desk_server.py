"""page/server.py 단위 · 통합 테스트 — step 4 desk-server.

엣지 5축 커버리지:
- 빈 값·경계: GET /sessions 빈 상태 → [] · Host 헤더 없음
- 비정상 입력: 토큰 누락·불일치 · Origin 다름 · Host 다름 · 바디가 JSON이 아님 ·
  choice 없는 pick 바디
- 실패 경로: ask 파일 없음(404) · 반영된 판정에 pick(409) · 포트 충돌(bind_or_exit None)
- 상태 전이: ask만 있는 카드 → pick 붙은 카드 → applied 붙은 카드 · 반영 전 재선택(덮어씀)
- 동시성: 해당 없음 — pick 쓰기는 레포·id별로 분리된 파일에 write_json_atomic
  하나로 통일된다(ARCHITECTURE "모든 쓰기는 같은 폴더 임시 파일 + os.replace")

🔴 CRITICAL(step4 지시문 "pick의 at은 datetime.now().isoformat() 문자열,
time.time() 아님"): POST /pick이 실제로 쓰는 pick.json의 at이 문자열이고
desk.validate.validate_pick을 통과하며 scripts.desk.cmd_picks_new의 --since
필터를 실제로 통과하는지까지 확인한다(파일이 생겼다는 것만으로는 부족하다).
"""

import http.client
import io
import json
import os
import socket
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from desk import atomic, validate
from page import server
from scripts import desk as desk_script

VALID_ASK = {
    "id": "ask-1",
    "order": 1,
    "issue": None,
    "area": "test-area",
    "question": "선택지 중 뭐가 낫나?",
    "why": "테스트 이유",
    "options": [
        {"key": "a", "label": "선택 A", "recommended": True},
        {"key": "b", "label": "선택 B", "recommended": False},
    ],
    "see": [],
    "aiDecided": [],
    "premiseOpen": False,
}


def _free_port() -> int:
    """지금 비어 있는 127.0.0.1 포트 하나. 아주 짧은 경쟁 창이 있지만 테스트용으로 충분하다."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class 순수_함수_check_host(unittest.TestCase):
    def test_정확히_일치하면_참이다(self):
        self.assertTrue(server.check_host({"Host": "127.0.0.1:47615"}, 47615))

    def test_포트가_다르면_거짓이다(self):
        self.assertFalse(server.check_host({"Host": "127.0.0.1:9999"}, 47615))

    def test_호스트이름이_다르면_거짓이다(self):
        self.assertFalse(server.check_host({"Host": "localhost:47615"}, 47615))

    def test_Host_헤더가_없으면_거짓이다(self):
        self.assertFalse(server.check_host({}, 47615))


class 순수_함수_bind_or_exit(unittest.TestCase):
    def test_비어있는_포트는_소켓을_돌려준다(self):
        port = _free_port()
        sock = server.bind_or_exit(port)
        try:
            self.assertIsNotNone(sock)
        finally:
            if sock is not None:
                sock.close()

    def test_이미_bind된_포트는_None이다(self):
        port = _free_port()
        holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        holder.bind(("127.0.0.1", port))
        holder.listen(1)
        try:
            self.assertIsNone(server.bind_or_exit(port))
        finally:
            holder.close()


class 순수_함수_write_server_meta(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home_dir = Path(self._tmp.name) / "home"
        env_patch = patch.dict(os.environ, {"DESK_HOME": str(self.home_dir)})
        env_patch.start()
        self.addCleanup(env_patch.stop)

    def test_server_json에_포트_pid_버전_토큰을_쓰고_권한을_0600으로_한다(self):
        server.write_server_meta(47615, 4242, "0.1.0", "abc123")

        meta_path = self.home_dir / "server.json"
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        self.assertEqual(data["port"], 47615)
        self.assertEqual(data["pid"], 4242)
        self.assertEqual(data["version"], "0.1.0")
        self.assertEqual(data["token"], "abc123")
        mode = meta_path.stat().st_mode & 0o777
        self.assertEqual(mode, 0o600)


class 순수_함수_read_plugin_version(unittest.TestCase):
    def test_CLAUDE_PLUGIN_ROOT가_없으면_레포_plugin_json을_읽는다(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_PLUGIN_ROOT", None)
            self.assertEqual(server.read_plugin_version(), "0.1.0")


class _ServerTestCase(unittest.TestCase):
    """임시 DESK_HOME·DESK_RUN·임시 포트로 실제 서버를 스레드로 띄우는 공용 셋업."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        tmp_path = Path(self._tmp.name)
        self.home_dir = tmp_path / "home"
        self.run_dir = tmp_path / "run"

        env_patch = patch.dict(
            os.environ,
            {"DESK_HOME": str(self.home_dir), "DESK_RUN": str(self.run_dir)},
        )
        env_patch.start()
        self.addCleanup(env_patch.stop)
        os.environ.pop("CLAUDE_PLUGIN_ROOT", None)

        self.port = _free_port()
        self.thread = threading.Thread(
            target=server.serve_forever, args=(self.port,), daemon=True
        )
        self.thread.start()
        self._wait_until_up()
        self.token = json.loads(
            (self.home_dir / "server.json").read_text(encoding="utf-8")
        )["token"]
        self.addCleanup(self._shutdown)

    def _wait_until_up(self, timeout=2.0):
        deadline = time.time() + timeout
        last_error = None
        while time.time() < deadline:
            try:
                urllib.request.urlopen(
                    f"http://127.0.0.1:{self.port}/version", timeout=0.2
                )
                return
            except Exception as e:  # noqa: BLE001 — 재시도용, 마지막 에러만 보고
                last_error = e
                time.sleep(0.02)
        raise AssertionError(f"서버가 뜨지 않았다: {last_error}")

    def _shutdown(self):
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{self.port}/shutdown",
                data=b"{}",
                method="POST",
                headers={"X-Desk-Token": self.token},
            )
            urllib.request.urlopen(req, timeout=1)
        except Exception:
            pass
        self.thread.join(timeout=2)

    def _url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def _get(self, path, headers=None):
        req = urllib.request.Request(self._url(path), headers=headers or {})
        try:
            resp = urllib.request.urlopen(req, timeout=1)
            body = resp.read()
            return resp.status, (json.loads(body.decode("utf-8")) if body else None)
        except urllib.error.HTTPError as e:
            body = e.read()
            return e.code, (json.loads(body.decode("utf-8")) if body else None)

    def _get_raw_host(self, path, host_value):
        """Host 헤더를 강제로 바꿔 보낸다(urllib은 자동으로 올바른 Host를 또 붙인다)."""
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=1)
        try:
            conn.putrequest("GET", path, skip_host=True)
            conn.putheader("Host", host_value)
            conn.endheaders()
            resp = conn.getresponse()
            body = resp.read()
            return resp.status, (json.loads(body.decode("utf-8")) if body else None)
        finally:
            conn.close()

    def _post(self, path, payload, headers=None):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            self._url(path), data=data, method="POST", headers=headers or {}
        )
        try:
            resp = urllib.request.urlopen(req, timeout=1)
            body = resp.read()
            return resp.status, (json.loads(body.decode("utf-8")) if body else None)
        except urllib.error.HTTPError as e:
            body = e.read()
            return e.code, (json.loads(body.decode("utf-8")) if body else None)

    def _pick_headers(self, **overrides):
        base = {
            "Content-Type": "application/json",
            "X-Desk-Token": self.token,
            "Origin": f"http://127.0.0.1:{self.port}",
        }
        base.update(overrides)
        return base

    def _inbox(self, repo):
        return self.home_dir / "inbox" / repo

    def _write_ask(self, repo, id_, **overrides):
        data = {**VALID_ASK, "id": id_, **overrides}
        atomic.write_json_atomic(self._inbox(repo) / f"{id_}.json", data)
        return data

    def _write_applied(self, repo, id_):
        atomic.write_json_atomic(
            self._inbox(repo) / f"{id_}.applied.json",
            {"appliedAt": time.time(), "issue": None, "followUp": []},
        )


class 통합_GET_version(_ServerTestCase):
    def test_플러그인_버전을_돌려준다(self):
        status, body = self._get("/version")
        self.assertEqual(status, 200)
        self.assertEqual(body["version"], "0.1.0")


class 통합_GET_sessions(_ServerTestCase):
    def test_세션이_없으면_빈_배열이다(self):
        status, body = self._get("/sessions")
        self.assertEqual(status, 200)
        self.assertEqual(body, [])

    def test_Host가_다르면_403이다(self):
        status, _ = self._get_raw_host("/sessions", "evil.example:1234")
        self.assertEqual(status, 403)


class 통합_GET_index(_ServerTestCase):
    def test_토큰이_치환된_index_html을_돌려준다(self):
        req = urllib.request.Request(self._url("/"))
        resp = urllib.request.urlopen(req, timeout=1)
        html = resp.read().decode("utf-8")
        self.assertIn(self.token, html)
        self.assertNotIn("__DESK_TOKEN__", html)


class 통합_CORS_헤더없음(_ServerTestCase):
    def test_응답에_Access_Control_헤더가_없다(self):
        req = urllib.request.Request(self._url("/version"))
        resp = urllib.request.urlopen(req, timeout=1)
        self.assertIsNone(resp.headers.get("Access-Control-Allow-Origin"))


class 통합_POST_pick(_ServerTestCase):
    def test_토큰이_없으면_403이고_아무것도_저장되지_않는다(self):
        self._write_ask("repo-a", "ask-1")
        headers = self._pick_headers()
        del headers["X-Desk-Token"]

        status, _ = self._post(
            "/pick", {"repo": "repo-a", "id": "ask-1", "choice": "a"}, headers
        )

        self.assertEqual(status, 403)
        self.assertFalse((self._inbox("repo-a") / "ask-1.pick.json").exists())

    def test_토큰이_틀리면_403이다(self):
        self._write_ask("repo-a", "ask-1")

        status, _ = self._post(
            "/pick",
            {"repo": "repo-a", "id": "ask-1", "choice": "a"},
            self._pick_headers(**{"X-Desk-Token": "wrong-token"}),
        )

        self.assertEqual(status, 403)

    def test_Origin이_다르면_403이고_아무것도_저장되지_않는다(self):
        self._write_ask("repo-a", "ask-1")

        status, _ = self._post(
            "/pick",
            {"repo": "repo-a", "id": "ask-1", "choice": "a"},
            self._pick_headers(Origin="http://evil.example"),
        )

        self.assertEqual(status, 403)
        self.assertFalse((self._inbox("repo-a") / "ask-1.pick.json").exists())

    def test_ask파일이_없으면_404다(self):
        status, _ = self._post(
            "/pick",
            {"repo": "repo-a", "id": "no-such-id", "choice": "a"},
            self._pick_headers(),
        )

        self.assertEqual(status, 404)

    def test_검증을_어기면_400과_위반필드목록이다(self):
        self._write_ask("repo-a", "ask-1")

        status, body = self._post(
            "/pick", {"repo": "repo-a", "id": "ask-1"}, self._pick_headers()
        )  # choice 없음

        self.assertEqual(status, 400)
        self.assertIn("choice", body.get("violations", []))

    def test_repo나_id_형식이_틀리면_400이고_파일을_쓰지_않는다(self):
        self._write_ask("repo-a", "ask-1")
        bad = [
            {"repo": "..", "id": "ask-1"},
            {"repo": "a/b", "id": "ask-1"},
            {"repo": "repo-a", "id": "../ask-1"},
            {"repo": "repo-a", "id": "a/b"},
            {"repo": 1, "id": "ask-1"},
            {"repo": "repo-a", "id": ["ask-1"]},
        ]
        for extra in bad:
            with self.subTest(extra=extra):
                status, _ = self._post(
                    "/pick", {**extra, "choice": "a"}, self._pick_headers()
                )
                self.assertEqual(status, 400)
        self.assertFalse((self._inbox("repo-a") / "ask-1.pick.json").exists())

    def test_바디가_올바른_JSON이_아니면_400이다(self):
        self._write_ask("repo-a", "ask-1")
        req = urllib.request.Request(
            self._url("/pick"),
            data=b"not-json",
            method="POST",
            headers=self._pick_headers(),
        )
        try:
            resp = urllib.request.urlopen(req, timeout=1)
            status = resp.status
        except urllib.error.HTTPError as e:
            status = e.code
        self.assertEqual(status, 400)

    def test_정상이면_200이고_pick_json이_생긴다(self):
        self._write_ask("repo-a", "ask-1")

        status, _ = self._post(
            "/pick",
            {
                "repo": "repo-a",
                "id": "ask-1",
                "choice": "a",
                "note": "메모",
                "noteKind": "reason",
            },
            self._pick_headers(),
        )

        self.assertEqual(status, 200)
        pick_path = self._inbox("repo-a") / "ask-1.pick.json"
        self.assertTrue(pick_path.exists())
        data = json.loads(pick_path.read_text(encoding="utf-8"))
        self.assertEqual(data["choice"], "a")
        self.assertEqual(data["note"], "메모")
        self.assertEqual(data["noteKind"], "reason")
        self.assertNotIn("repo", data)
        self.assertNotIn("id", data)

    def test_반영된_판정에_pick하면_409다(self):
        self._write_ask("repo-a", "ask-1")
        self._write_applied("repo-a", "ask-1")

        status, _ = self._post(
            "/pick",
            {"repo": "repo-a", "id": "ask-1", "choice": "a"},
            self._pick_headers(),
        )

        self.assertEqual(status, 409)

    def test_반영전이면_다시_골라도_덮어쓴다(self):
        self._write_ask("repo-a", "ask-1")
        self._post(
            "/pick",
            {"repo": "repo-a", "id": "ask-1", "choice": "a"},
            self._pick_headers(),
        )

        status, _ = self._post(
            "/pick",
            {"repo": "repo-a", "id": "ask-1", "choice": "b"},
            self._pick_headers(),
        )

        self.assertEqual(status, 200)
        data = json.loads(
            (self._inbox("repo-a") / "ask-1.pick.json").read_text(encoding="utf-8")
        )
        self.assertEqual(data["choice"], "b")


class 통합_POST_pick_이후_step3_계약(_ServerTestCase):
    def test_pick_at이_validate_pick을_통과하는_문자열이고_cmd_picks_new의_since필터를_통과한다(
        self,
    ):
        self._write_ask("repo-a", "ask-1")
        before = time.time()

        status, _ = self._post(
            "/pick",
            {"repo": "repo-a", "id": "ask-1", "choice": "a"},
            self._pick_headers(),
        )
        self.assertEqual(status, 200)

        pick_data = json.loads(
            (self._inbox("repo-a") / "ask-1.pick.json").read_text(encoding="utf-8")
        )
        self.assertIsInstance(pick_data["at"], str)
        self.assertEqual(validate.validate_pick(pick_data), [])

        out = io.StringIO()
        with redirect_stdout(out):
            result = desk_script.main(
                ["desk.py", "picks", "--new", "--since", str(before)]
            )
        self.assertEqual(result, 0)
        lines = [json.loads(line) for line in out.getvalue().splitlines() if line]
        self.assertEqual([line["id"] for line in lines], ["ask-1"])


class 통합_GET_judgments(_ServerTestCase):
    def test_ask만_있어도_카드로_보인다(self):
        self._write_ask("repo-a", "ask-1")

        status, body = self._get("/judgments")

        self.assertEqual(status, 200)
        self.assertEqual(len(body), 1)
        card = body[0]
        self.assertEqual(card["id"], "ask-1")
        self.assertEqual(card["repo"], "repo-a")
        self.assertNotIn("pick", card)
        self.assertNotIn("applied", card)

    def test_pick과_applied가_있으면_카드에_포함된다(self):
        self._write_ask("repo-a", "ask-2")
        self._post(
            "/pick",
            {"repo": "repo-a", "id": "ask-2", "choice": "a"},
            self._pick_headers(),
        )
        self._write_applied("repo-a", "ask-2")

        status, body = self._get("/judgments")

        self.assertEqual(status, 200)
        card = next(c for c in body if c["id"] == "ask-2")
        self.assertIn("pick", card)
        self.assertEqual(card["pick"]["choice"], "a")
        self.assertIn("applied", card)

    def test_repo로_필터링한다(self):
        self._write_ask("repo-a", "ask-3")
        self._write_ask("repo-b", "ask-4")

        status, body = self._get("/judgments?repo=repo-a")

        self.assertEqual(status, 200)
        self.assertEqual({c["id"] for c in body}, {"ask-3"})


class 통합_POST_shutdown(_ServerTestCase):
    def test_토큰이_틀리면_403이고_서버는_계속_돈다(self):
        status, _ = self._post("/shutdown", {}, {"X-Desk-Token": "wrong"})

        self.assertEqual(status, 403)
        status2, _ = self._get("/version")
        self.assertEqual(status2, 200)


if __name__ == "__main__":
    unittest.main()
