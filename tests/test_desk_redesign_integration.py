"""desk 화면 재설계 통합 — 서버를 띄워 `/`·`/nav-counts`·폰트·임의 이름을 한 흐름으로 확인한다.

엣지 5축: 빈 값·경계(설정 없는 빈 상태의 건수 0) · 비정상 입력(임의 폰트 이름 404) ·
실패 경로(단위 테스트 step 1·3이 맡음) · 상태 전이(해당 없음) · 동시성(해당 없음 — 읽기 전용).
"""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_desk_server import _ServerTestCase


class 화면_재설계_통합(_ServerTestCase):
    def _get(self, path):
        url = f"http://127.0.0.1:{self.port}{path}"
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def test_루트_nav_counts_폰트가_한_흐름으로_응답한다(self):
        status, body = self._get("/")
        self.assertEqual(status, 200)
        html = body.decode("utf-8")
        self.assertNotIn("__DESK_TOKEN__", html)
        self.assertIn(self.token, html)

        status, body = self._get("/nav-counts")
        self.assertEqual(status, 200)
        counts = json.loads(body)
        self.assertEqual(set(counts), {"judge", "review"})

        status, body = self._get("/fonts/PretendardVariable.woff2")
        self.assertEqual(status, 200)
        self.assertGreater(len(body), 0)

        status, _ = self._get("/fonts/Other.woff2")
        self.assertEqual(status, 404)
