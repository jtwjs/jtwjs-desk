"""GET /fonts/PretendardVariable.woff2 — 허용 이름 하나만 여는 경계 (ADR-016).

엣지 5축: 빈 값·경계(디렉터리 요청) · 비정상 입력(다른 이름 · `..` · 인코딩 슬래시 · Host 다름) ·
실패 경로(파일 없음 → 404) · 상태 전이(해당 없음) · 동시성(해당 없음 — 읽기 전용).
"""
import http.client
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from page import server
from test_desk_server import _ServerTestCase

_FONT = Path(__file__).resolve().parent.parent / "page" / "fonts" / "PretendardVariable.woff2"
_NAME = "/fonts/PretendardVariable.woff2"


class 통합_GET_fonts(_ServerTestCase):
    def _raw(self, path, host=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
        try:
            conn.putrequest("GET", path, skip_host=True)
            conn.putheader("Host", host or f"127.0.0.1:{self.port}")
            conn.endheaders()
            resp = conn.getresponse()
            return resp.status, resp.getheader("Content-Type"), resp.read()
        finally:
            conn.close()

    def test_허용_이름이면_woff2_바이트를_준다(self):
        status, ctype, body = self._raw(_NAME)
        self.assertEqual(status, 200)
        self.assertEqual(ctype, "font/woff2")
        self.assertEqual(body, _FONT.read_bytes())

    def test_다른_이름이면_404다(self):
        status, _, _ = self._raw("/fonts/Other.woff2")
        self.assertEqual(status, 404)

    def test_디렉터리_요청이면_404다(self):
        for p in ("/fonts/", "/fonts"):
            status, _, _ = self._raw(p)
            self.assertEqual(status, 404, p)

    def test_점점_조작이면_404다(self):
        for p in ("/fonts/../server.py", "/fonts/../fonts/PretendardVariable.woff2",
                  "/fonts/%2e%2e/server.py", "/fonts/..%2fserver.py",
                  "/fonts/PretendardVariable.woff2/../../server.py"):
            status, _, _ = self._raw(p)
            self.assertEqual(status, 404, p)

    def test_Host가_다르면_403이다(self):
        status, _, _ = self._raw(_NAME, host="evil.example")
        self.assertEqual(status, 403)

    def test_파일이_없으면_404다(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(server, "_FONT_PATH", Path(d) / "nope.woff2"):
                status, _, _ = self._raw(_NAME)
        self.assertEqual(status, 404)
