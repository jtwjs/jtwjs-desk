"""GET /trends · GET /nav-counts 의 trends 항목 (step 4).

엣지 5축: 빈 값(빈 파일 · 오늘 0건) · 비정상 입력(깨진 줄) · 실패 경로(파일 없음 · 설정 없음) ·
상태 전이(읽음 전 → 후 응답 변화) · 동시성(해당 없음 — 읽기 전용).
🔴 픽스처는 임시 폴더 안의 지어낸 글이다.
"""
import json
import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_desk_server_review import _ReviewCase
from page import server

TODAY = date(2026, 3, 10)


def _item(id_, d, **extra):
    return {"id": id_, "date": d, "title": f"샘플 제목 {id_}", "url": f"https://example.com/{id_}",
            "summary": f"샘플 요약 {id_}", **extra}


def _lines(rows):
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)


class 통합_trends(_ReviewCase):
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

    def _cfg(self, **over):
        cfg = {"trends_items": str(self.items), "trends_reads": str(self.reads),
               "trends_marks": str(self.marks)}
        cfg.update(over)
        self.cfg_path.write_text(json.dumps({k: v for k, v in cfg.items() if v is not None}),
                                 encoding="utf-8")

    def _write_items(self, rows, raw=""):
        self.items.write_text(_lines(rows) + raw, encoding="utf-8")

    def _three_today(self):
        self._write_items([_item("a", "2026-03-10"), _item("b", "2026-03-10"),
                           _item("c", "2026-03-10")])

    # 수용 조건 1
    def test_오늘_3건이_제목_요약_링크_읽음과_함께_온다(self):
        self._three_today()
        self._cfg()
        status, body = self._get("/trends")
        self.assertEqual(status, 200)
        self.assertEqual(body["date"], "2026-03-10")
        self.assertEqual([g["id"] for g in body["today"]], ["a", "b", "c"])
        first = body["today"][0]
        self.assertEqual(first["title"], "샘플 제목 a")
        self.assertEqual(first["summary"], "샘플 요약 a")
        self.assertEqual(first["url"], "https://example.com/a")
        self.assertIs(first["read"], False)
        self.assertEqual(body["missing"], [])
        self.assertIn("config", body)

    def test_읽음_파일에_id가_있으면_그_글_read가_true다(self):
        self._three_today()
        self.reads.write_text(_lines([{"id": "b", "at": "t"}]), encoding="utf-8")
        self._cfg()
        _, body = self._get("/trends")
        self.assertEqual([g["read"] for g in body["today"]], [False, True, False])

    def test_읽음_전후로_응답이_바뀐다(self):
        self._three_today()
        self._cfg()
        _, before = self._get("/trends")
        self.reads.write_text(_lines([{"id": "a", "at": "t"}]), encoding="utf-8")
        _, after = self._get("/trends")
        self.assertIs(before["today"][0]["read"], False)
        self.assertIs(after["today"][0]["read"], True)

    # 수용 조건 14 · 6
    def test_지난_안_읽은_글이_날짜_내림차순이다(self):
        self._write_items([_item("old", "2026-03-01"), _item("mid", "2026-03-05"),
                           _item("new", "2026-03-09"), _item("t", "2026-03-10"),
                           _item("fut", "2026-03-11")])
        self._cfg()
        _, body = self._get("/trends")
        self.assertEqual([g["id"] for g in body["past_unread"]], ["new", "mid", "old"])

    def test_잔디는_365칸이고_지난_날_글을_읽으면_그_글_날짜_칸이_오른다(self):
        self._write_items([_item("old", "2026-03-05"), _item("t", "2026-03-10")])
        self._cfg()
        _, before = self._get("/trends")
        self.assertEqual(len(before["heatmap"]), 365)
        self.assertEqual(before["heatmap"][-1]["date"], "2026-03-10")
        self.assertEqual(before["heatmap"][0]["date"], "2025-03-11")
        self.reads.write_text(_lines([{"id": "old", "at": "t"}]), encoding="utf-8")
        _, after = self._get("/trends")
        cell = {c["date"]: c for c in after["heatmap"]}
        self.assertEqual(cell["2026-03-05"], {"date": "2026-03-05", "total": 1, "read": 1})
        self.assertEqual(cell["2026-03-10"], {"date": "2026-03-10", "total": 1, "read": 0})
        self.assertEqual([g["id"] for g in after["past_unread"]], [])

    # 수용 조건 7: 이유 구분
    def test_설정_없음_파일_없음_형식_확인_필요_오늘_0건이_서로_다르고_모두_200이다(self):
        self._cfg(trends_items=None)
        s1, no_cfg = self._get("/trends")
        self._cfg()
        s2, no_file = self._get("/trends")
        self.items.write_text("{깨짐\n", encoding="utf-8")
        s3, bad = self._get("/trends")
        self._write_items([_item("old", "2026-03-01")])
        s4, zero = self._get("/trends")
        self.assertEqual((s1, s2, s3, s4), (200, 200, 200, 200))
        self.assertEqual(no_cfg["missing"], [{"what": "동향", "reason": "설정 없음"}])
        self.assertEqual(no_file["missing"], [{"what": "동향", "reason": "파일 없음"}])
        self.assertEqual(bad["missing"], [{"what": "동향", "reason": "형식 확인 필요"}])
        self.assertEqual(zero["missing"], [])
        self.assertEqual(zero["today"], [])
        for body in (no_cfg, no_file, bad):
            self.assertEqual(body["today"], [])
            self.assertEqual(len(body["heatmap"]), 365)

    def test_빈_파일은_이유_없이_오늘_0건이다(self):
        self.items.write_text("", encoding="utf-8")
        self._cfg()
        status, body = self._get("/trends")
        self.assertEqual(status, 200)
        self.assertEqual((body["missing"], body["today"], body["broken"]), ([], [], 0))

    def test_깨진_줄은_건너뛰고_개수를_broken에_합친다(self):
        self._write_items([_item("a", "2026-03-10")], raw="{깨짐\n" + '{"id": "x"}\n')
        self.reads.write_text("깨짐\n", encoding="utf-8")
        self.marks.write_text("깨짐\n", encoding="utf-8")
        self._cfg()
        _, body = self._get("/trends")
        self.assertEqual([g["id"] for g in body["today"]], ["a"])
        self.assertEqual(body["broken"], 4)

    # 수용 조건 11 · 18
    def test_trends_reads가_비면_can_record_read가_false다(self):
        self._three_today()
        self._cfg(trends_reads=None)
        _, body = self._get("/trends")
        self.assertIs(body["can_record_read"], False)
        self.assertIs(body["can_bookmark"], True)
        self.assertEqual(len(body["today"]), 3)

    def test_trends_marks가_비면_can_bookmark가_false다(self):
        self._three_today()
        self._cfg(trends_marks=None)
        _, body = self._get("/trends")
        self.assertIs(body["can_bookmark"], False)
        self.assertIs(body["can_record_read"], True)

    def test_읽음_북마크_파일이_없을_뿐이면_can이_true다(self):
        self._three_today()
        self._cfg()
        _, body = self._get("/trends")
        self.assertIs(body["can_record_read"], True)
        self.assertIs(body["can_bookmark"], True)

    # 수용 조건 16
    def test_북마크_목록과_글의_bookmarked가_온다(self):
        self._write_items([_item("a", "2026-03-10"), _item("b", "2026-03-04"),
                           _item("c", "2026-03-08")])
        self.marks.write_text(_lines([
            {"id": "a", "on": True, "at": "t"}, {"id": "b", "on": True, "at": "t"},
            {"id": "c", "on": True, "at": "t"}, {"id": "c", "on": False, "at": "t2"}]),
            encoding="utf-8")
        self.reads.write_text(_lines([{"id": "b", "at": "t"}]), encoding="utf-8")
        self._cfg()
        _, body = self._get("/trends")
        self.assertEqual([g["id"] for g in body["bookmarks"]], ["a", "b"])
        self.assertEqual([g["read"] for g in body["bookmarks"]], [False, True])
        self.assertIs(body["today"][0]["bookmarked"], True)
        self.assertEqual([g["bookmarked"] for g in body["past_unread"]], [False])

    # ADR-009
    def test_GET은_세_파일을_바꾸지_않는다(self):
        self._three_today()
        self.reads.write_text(_lines([{"id": "a", "at": "t"}]), encoding="utf-8")
        self.marks.write_text(_lines([{"id": "a", "on": True, "at": "t"}]), encoding="utf-8")
        self._cfg()
        before = [p.read_bytes() for p in (self.items, self.reads, self.marks)]
        self._get("/trends")
        self._get("/nav-counts")
        after = [p.read_bytes() for p in (self.items, self.reads, self.marks)]
        self.assertEqual(before, after)

    def test_응답에_가짜_경로_문자열이_없다(self):
        self._three_today()
        self._cfg()
        import urllib.request
        raw = urllib.request.urlopen(self._url("/trends"), timeout=2).read().decode("utf-8")
        self.assertNotIn(str(self.dir), raw)
        self.assertNotIn("items.jsonl", raw)

    def test_Host가_다르면_403이다(self):
        status, _ = self._get_raw_host("/trends", "evil.example:80")
        self.assertEqual(status, 403)

    # 수용 조건 13: nav-counts
    def test_nav_counts_trends는_안_읽은_건수이고_지난_날을_포함하며_미래는_뺀다(self):
        self._write_items([_item("a", "2026-03-10"), _item("b", "2026-03-10"),
                           _item("old", "2026-03-01"), _item("fut", "2026-03-11")])
        self.reads.write_text(_lines([{"id": "a", "at": "t"}]), encoding="utf-8")
        self._cfg()
        _, body = self._get("/nav-counts")
        self.assertEqual(body["trends"], 2)
        self.assertEqual(body["errors"], {})

    def test_설정이_없으면_nav_counts_trends는_0이다(self):
        _, body = self._get("/nav-counts")
        self.assertEqual(body["trends"], 0)

    def test_동향을_못_읽어_trends가_null이어도_다른_배지는_그대로다(self):
        self._three_today()
        self._cfg()
        self._write_ask("repo-a", "ask-1")
        with patch("desk.trends.unread_count", side_effect=ValueError("/비밀/경로")):
            status, body = self._get("/nav-counts")
        self.assertEqual(status, 200)
        self.assertIsNone(body["trends"])
        self.assertEqual(body["errors"], {"trends": "ValueError"})
        self.assertEqual(body["judge"], 1)
        self.assertEqual(body["review"], 0)
        self.assertEqual(body["routine"], 0)
