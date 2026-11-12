"""desk/trends.py 쓰기 껍질(record_read · record_mark) — step 3 trends-write. 픽스처는 지어낸 글이다.

엣지 5축: 빈 값(빈 파일) · 비정상 입력(없는 id) · 실패 경로(OSError)
· 상태 전이(북마크 켬/끔) · 동시성(Barrier).
"""
import json
import tempfile
import threading
import unittest
from datetime import datetime
from pathlib import Path

from desk import trends

NOW = datetime(2026, 11, 12, 21, 0, 0)


def item(id_, d="2026-11-12"):
    return {"id": id_, "date": d, "title": "샘플 글", "url": "https://example.com/a",
            "summary": "샘플 요약"}


def write_lines(path: Path, *rows):
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                    encoding="utf-8")


def read_rows(path: Path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.items = self.tmp / "items.jsonl"
        self.reads = self.tmp / "reads.jsonl"
        self.marks = self.tmp / "marks.jsonl"
        write_lines(self.items, item("a1"), item("a2"))


class 읽음_기록(Base):
    def test_ok면_한_줄을_덧붙인다(self):
        self.assertEqual(trends.record_read(self.items, self.reads, "a1", NOW), "ok")
        self.assertEqual(read_rows(self.reads), [{"id": "a1", "at": NOW.isoformat()}])

    def test_같은_id_두번째는_duplicate이고_줄이_안_늘어난다(self):
        trends.record_read(self.items, self.reads, "a1", NOW)
        self.assertEqual(trends.record_read(self.items, self.reads, "a1", NOW), "duplicate")
        self.assertEqual(len(read_rows(self.reads)), 1)

    def test_동향에_없는_id는_unknown_id이고_파일이_안_바뀐다(self):
        self.assertEqual(trends.record_read(self.items, self.reads, "zz", NOW), "unknown_id")
        self.assertFalse(self.reads.exists())
        write_lines(self.reads, {"id": "a1", "at": "t"})
        before = self.reads.read_text(encoding="utf-8")
        self.assertEqual(trends.record_read(self.items, self.reads, "zz", NOW), "unknown_id")
        self.assertEqual(self.reads.read_text(encoding="utf-8"), before)

    def test_읽음_파일이_없으면_디렉터리까지_만든다(self):
        deep = self.tmp / "no" / "dir" / "reads.jsonl"
        self.assertEqual(trends.record_read(self.items, deep, "a2", NOW), "ok")
        self.assertEqual(read_rows(deep)[0]["id"], "a2")

    def test_빈_읽음_파일에도_쓴다(self):
        self.reads.write_text("", encoding="utf-8")
        self.assertEqual(trends.record_read(self.items, self.reads, "a1", NOW), "ok")
        self.assertEqual(len(read_rows(self.reads)), 1)

    def test_동향_파일이_없으면_unknown_id(self):
        self.assertEqual(
            trends.record_read(self.tmp / "none.jsonl", self.reads, "a1", NOW), "unknown_id")

    def test_끝_개행_없는_파일에서도_줄이_안_붙는다(self):
        self.reads.write_text(json.dumps({"id": "a2", "at": "t"}), encoding="utf-8")
        self.assertEqual(trends.record_read(self.items, self.reads, "a1", NOW), "ok")
        self.assertEqual([r["id"] for r in read_rows(self.reads)], ["a2", "a1"])

    def test_쓸_수_없는_경로는_OSError가_올라온다(self):
        self.reads.mkdir()
        with self.assertRaises(OSError):
            trends.record_read(self.items, self.reads, "a1", NOW)

    def test_동향_파일에는_쓰지_않는다(self):
        before = self.items.read_text(encoding="utf-8")
        trends.record_read(self.items, self.reads, "a1", NOW)
        self.assertEqual(self.items.read_text(encoding="utf-8"), before)


class 북마크_기록(Base):
    def test_켬_같은켬_끔_켬이_줄_세_개(self):
        self.assertEqual(trends.record_mark(self.items, self.marks, "a1", True, NOW), "ok")
        self.assertEqual(trends.record_mark(self.items, self.marks, "a1", True, NOW), "same")
        self.assertEqual(trends.record_mark(self.items, self.marks, "a1", False, NOW), "ok")
        self.assertEqual(trends.record_mark(self.items, self.marks, "a1", True, NOW), "ok")
        rows = read_rows(self.marks)
        self.assertEqual([r["on"] for r in rows], [True, False, True])
        self.assertEqual(rows[0], {"id": "a1", "on": True, "at": NOW.isoformat()})

    def test_없던_글을_끄는_건_same이다(self):
        self.assertEqual(trends.record_mark(self.items, self.marks, "a1", False, NOW), "same")
        self.assertFalse(self.marks.exists())

    def test_동향에_없는_id는_unknown_id(self):
        self.assertEqual(trends.record_mark(self.items, self.marks, "zz", True, NOW), "unknown_id")
        self.assertFalse(self.marks.exists())

    def test_쓸_수_없는_경로는_OSError가_올라온다(self):
        self.marks.mkdir()
        with self.assertRaises(OSError):
            trends.record_mark(self.items, self.marks, "a1", True, NOW)


class 두_파일의_독립(Base):
    def test_북마크는_읽음_파일을_안_바꾼다(self):
        trends.record_read(self.items, self.reads, "a1", NOW)
        before = self.reads.read_text(encoding="utf-8")
        trends.record_mark(self.items, self.marks, "a1", True, NOW)
        self.assertEqual(self.reads.read_text(encoding="utf-8"), before)

    def test_읽음은_북마크_파일을_안_바꾼다(self):
        trends.record_mark(self.items, self.marks, "a1", True, NOW)
        before = self.marks.read_text(encoding="utf-8")
        trends.record_read(self.items, self.reads, "a1", NOW)
        self.assertEqual(self.marks.read_text(encoding="utf-8"), before)


class 동시성(Base):
    def test_같은_id_동시_읽음은_줄_하나_ok_하나(self):
        n = 8
        barrier = threading.Barrier(n)
        results = []

        def work():
            barrier.wait()
            results.append(trends.record_read(self.items, self.reads, "a1", NOW))

        threads = [threading.Thread(target=work) for _ in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(results.count("ok"), 1)
        self.assertEqual(results.count("duplicate"), n - 1)
        self.assertEqual([r["id"] for r in read_rows(self.reads)].count("a1"), 1)


if __name__ == "__main__":
    unittest.main()
