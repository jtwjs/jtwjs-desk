"""POST /trends/read · POST /trends/mark (step 5).

엣지 5축: 빈 값(빈 id) · 비정상 입력(타입 오류 · 없는 id · 깨진 JSON · 토큰) ·
실패 경로(설정 없음 · 쓰기 500) · 상태 전이(안 읽음 → 읽음 · 북마크 켬/끔) ·
동시성(같은 id 동시 POST 두 건, Barrier).
🔴 픽스처는 임시 폴더 안의 지어낸 글이다.
"""
import json
import sys
import threading
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_desk_server_review import _ReviewCase
from page import server

TODAY = date(2026, 3, 10)


def _item(id_, d="2026-03-10"):
    return {"id": id_, "date": d, "title": f"샘플 제목 {id_}", "url": f"https://example.com/{id_}",
            "summary": f"샘플 요약 {id_}"}


def _lines(rows):
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)


def _rows(path):
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


class 통합_trends_post(_ReviewCase):
    def setUp(self):
        super().setUp()
        p = patch.object(server, "_today", return_value=TODAY)
        p.start()
        self.addCleanup(p.stop)
        self.dir = Path(self._tmp.name) / "trends"
        self.dir.mkdir()
        self.items = self.dir / "items.jsonl"
        self.reads = self.dir / "reads.jsonl"
        self.marks = self.dir / "marks.jsonl"
        self.items.write_text(_lines([_item("a"), _item("b"), _item("c")]), encoding="utf-8")

    def _cfg(self, **over):
        cfg = {"trends_items": str(self.items), "trends_reads": str(self.reads),
               "trends_marks": str(self.marks)}
        cfg.update(over)
        self.cfg_path.write_text(json.dumps({k: v for k, v in cfg.items() if v is not None}),
                                 encoding="utf-8")

    def _read(self, payload, headers=None):
        return self._post("/trends/read", payload,
                          headers if headers is not None else self._pick_headers())

    def _mark(self, payload, headers=None):
        return self._post("/trends/mark", payload,
                          headers if headers is not None else self._pick_headers())

    def _raw(self, path, data: bytes):
        req = urllib.request.Request(self._url(path), data=data, method="POST",
                                     headers=self._pick_headers())
        try:
            return urllib.request.urlopen(req, timeout=1).status
        except urllib.error.HTTPError as e:
            e.read()
            return e.code

    def _today_by_id(self):
        _, body = self._get("/trends")
        return {g["id"]: g for g in body["today"]}


class 읽음_POST(통합_trends_post):
    def test_성공하면_200이고_한_줄이_쌓이고_GET에서_read가_true다(self):
        self._cfg()
        self.assertIs(self._today_by_id()["a"]["read"], False)
        status, body = self._read({"id": "a"})
        self.assertEqual((status, body), (200, {"ok": True, "changed": True}))
        rows = _rows(self.reads)
        self.assertEqual([r["id"] for r in rows], ["a"])
        self.assertIsInstance(rows[0]["at"], str)
        got = self._today_by_id()
        self.assertIs(got["a"]["read"], True)
        self.assertIs(got["b"]["read"], False)

    def test_같은_id를_두_번_보내면_줄이_하나고_둘_다_200이다(self):
        self._cfg()
        first = self._read({"id": "a"})
        second = self._read({"id": "a"})
        self.assertEqual(first, (200, {"ok": True, "changed": True}))
        self.assertEqual(second, (200, {"ok": True, "changed": False}))
        self.assertEqual(len(_rows(self.reads)), 1)

    def test_동향에_없는_id는_400이고_파일이_안_바뀐다(self):
        self._cfg()
        status, body = self._read({"id": "zzz"})
        self.assertEqual((status, body), (400, {"error": "unknown id"}))
        self.assertFalse(self.reads.exists())

    def test_빈_id와_타입_오류는_400이다(self):
        self._cfg()
        for payload in ({"id": ""}, {"id": 3}, {"id": None}, {}, ["a"], "a"):
            with self.subTest(payload=payload):
                self.assertEqual(self._read(payload)[0], 400)
        self.assertFalse(self.reads.exists())

    def test_깨진_JSON은_400이다(self):
        self._cfg()
        self.assertEqual(self._raw("/trends/read", b"{not json"), 400)
        self.assertFalse(self.reads.exists())

    def test_토큰이_없거나_틀리면_403이고_파일이_안_바뀐다(self):
        self._cfg()
        h = self._pick_headers()
        del h["X-Desk-Token"]
        self.assertEqual(self._read({"id": "a"}, h)[0], 403)
        self.assertEqual(self._read({"id": "a"}, self._pick_headers(**{"X-Desk-Token": "wrong"}))[0],
                         403)
        self.assertFalse(self.reads.exists())

    def test_trends_reads가_비면_400이다(self):
        self._cfg(trends_reads=None)
        status, body = self._read({"id": "a"})
        self.assertEqual((status, body), (400, {"error": "not configured"}))

    def test_trends_items가_비면_400이다(self):
        self._cfg(trends_items=None)
        self.assertEqual(self._read({"id": "a"})[0], 400)

    def test_읽음_경로가_디렉터리면_500이고_GET에서_안_읽음으로_남는다(self):
        self.reads.mkdir()
        self._cfg()
        status, body = self._read({"id": "a"})
        self.assertEqual(status, 500)
        self.assertEqual(body, {"error": "write failed"})
        self.assertNotIn(str(self.reads), json.dumps(body))
        self.assertIs(self._today_by_id()["a"]["read"], False)

    def test_같은_id_동시_POST_두_건이어도_줄은_하나다(self):
        self._cfg()
        results = []
        start = threading.Barrier(2)

        def go():
            start.wait()
            results.append(self._read({"id": "b"}))

        ts = [threading.Thread(target=go) for _ in range(2)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        self.assertEqual([r[0] for r in results], [200, 200])
        self.assertEqual(sorted(r[1]["changed"] for r in results), [False, True])
        self.assertEqual(len(_rows(self.reads)), 1)


class 북마크_POST(통합_trends_post):
    def test_켜면_GET의_bookmarked가_true고_북마크_목록에_온다(self):
        self._cfg()
        status, body = self._mark({"id": "a", "on": True})
        self.assertEqual((status, body), (200, {"ok": True, "changed": True}))
        rows = _rows(self.marks)
        self.assertEqual([(r["id"], r["on"]) for r in rows], [("a", True)])
        _, got = self._get("/trends")
        self.assertIs({g["id"]: g for g in got["today"]}["a"]["bookmarked"], True)
        self.assertEqual([b["id"] for b in got["bookmarks"]], ["a"])

    def test_같은_켬_재전송은_changed_false고_줄이_안_늘어난다(self):
        self._cfg()
        self._mark({"id": "a", "on": True})
        status, body = self._mark({"id": "a", "on": True})
        self.assertEqual((status, body), (200, {"ok": True, "changed": False}))
        self.assertEqual(len(_rows(self.marks)), 1)

    def test_끄면_bookmarked가_false고_목록에서_빠진다(self):
        self._cfg()
        self._mark({"id": "a", "on": True})
        status, body = self._mark({"id": "a", "on": False})
        self.assertEqual((status, body), (200, {"ok": True, "changed": True}))
        _, got = self._get("/trends")
        self.assertIs({g["id"]: g for g in got["today"]}["a"]["bookmarked"], False)
        self.assertEqual(got["bookmarks"], [])
        self.assertEqual(len(_rows(self.marks)), 2)

    def test_북마크를_켜도_읽음_파일이_안_바뀐다(self):
        self._cfg()
        self._read({"id": "b"})
        before = self.reads.read_text(encoding="utf-8")
        self._mark({"id": "a", "on": True})
        self.assertEqual(self.reads.read_text(encoding="utf-8"), before)
        self.assertIs(self._today_by_id()["a"]["read"], False)

    def test_북마크한_글을_읽어도_북마크는_그대로다(self):
        self._cfg()
        self._mark({"id": "a", "on": True})
        self._read({"id": "a"})
        got = self._today_by_id()["a"]
        self.assertIs(got["bookmarked"], True)
        self.assertIs(got["read"], True)

    def test_trends_marks가_비면_400이다(self):
        self._cfg(trends_marks=None)
        status, body = self._mark({"id": "a", "on": True})
        self.assertEqual((status, body), (400, {"error": "not configured"}))

    def test_동향에_없는_id는_400이다(self):
        self._cfg()
        status, body = self._mark({"id": "zzz", "on": True})
        self.assertEqual((status, body), (400, {"error": "unknown id"}))
        self.assertFalse(self.marks.exists())

    def test_on이_bool이_아니면_400이다(self):
        self._cfg()
        for on in ("true", 1, None):
            with self.subTest(on=on):
                self.assertEqual(self._mark({"id": "a", "on": on})[0], 400)
        self.assertEqual(self._mark({"id": "a"})[0], 400)
        self.assertEqual(self._mark({"id": "", "on": True})[0], 400)
        self.assertFalse(self.marks.exists())

    def test_깨진_JSON은_400이다(self):
        self._cfg()
        self.assertEqual(self._raw("/trends/mark", b"{not json"), 400)

    def test_토큰이_없으면_403이다(self):
        self._cfg()
        h = self._pick_headers()
        del h["X-Desk-Token"]
        self.assertEqual(self._mark({"id": "a", "on": True}, h)[0], 403)
        self.assertFalse(self.marks.exists())

    def test_북마크_쓰기가_실패하면_500이고_읽음_상태는_안_바뀐다(self):
        self.marks.mkdir()
        self._cfg()
        self._read({"id": "a"})
        status, body = self._mark({"id": "b", "on": True})
        self.assertEqual((status, body), (500, {"error": "write failed"}))
        got = self._today_by_id()
        self.assertEqual([got[i]["read"] for i in "abc"], [True, False, False])
        self.assertEqual([r["id"] for r in _rows(self.reads)], ["a"])

    def test_읽음_쓰기가_실패해도_북마크_상태는_안_바뀐다(self):
        self.reads.mkdir()
        self._cfg()
        self._mark({"id": "a", "on": True})
        self.assertEqual(self._read({"id": "a"})[0], 500)
        self.assertIs(self._today_by_id()["a"]["bookmarked"], True)
        self.assertEqual(len(_rows(self.marks)), 1)
