"""desk/trends.py 순수 함수 테스트. 픽스처는 전부 지어낸 글이다.

엣지 5축: 빈 값(빈 텍스트) · 비정상 입력(깨진 줄) · 실패 경로(해당 없음: 순수 함수)
 · 상태 전이(북마크 켬/끔) · 동시성(해당 없음: 순수 함수)
"""
import json
import unittest
from datetime import date, timedelta

from desk import trends

TODAY = date(2026, 11, 13)


def item(id_, d, title=None):
    return {"id": id_, "date": d, "title": title or f"샘플 글 {id_}",
            "url": f"https://example.com/{id_}", "summary": f"요약 {id_}"}


def jsonl(*rows):
    return "\n".join(r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)
                     for r in rows) + "\n"


def items_of(*rows):
    return {r["id"]: r for r in rows}


class 동향_파일을_읽을_때(unittest.TestCase):
    def test_정상_줄은_id_순서대로_파싱된다(self):
        text = jsonl(item("a", "2026-11-13"), item("b", "2026-11-13"))
        items, broken = trends.parse_items(text)
        self.assertEqual(list(items), ["a", "b"])
        self.assertEqual(items["a"]["title"], "샘플 글 a")
        self.assertEqual(broken, 0)

    def test_같은_id는_마지막_줄이_이긴다(self):
        text = jsonl(item("a", "2026-11-13", "처음"), item("b", "2026-11-13"),
                     item("a", "2026-11-13", "나중"))
        items, _ = trends.parse_items(text)
        self.assertEqual(items["a"]["title"], "나중")
        self.assertEqual(list(items), ["a", "b"])

    def test_빈_텍스트면_빈_결과다(self):
        self.assertEqual(trends.parse_items(""), ({}, 0))
        self.assertEqual(trends.parse_items("\n  \n"), ({}, 0))

    def test_JSON이_아닌_줄은_건너뛰고_센다(self):
        text = jsonl(item("a", "2026-11-13"), "이건 json 아님")
        items, broken = trends.parse_items(text)
        self.assertEqual(list(items), ["a"])
        self.assertEqual(broken, 1)

    def test_필드가_없거나_비어_있는_줄은_깨진_줄이다(self):
        no_url = {k: v for k, v in item("x", "2026-11-13").items() if k != "url"}
        empty_title = {**item("y", "2026-11-13"), "title": "  "}
        text = jsonl(no_url, empty_title, item("a", "2026-11-13"), [1, 2])
        items, broken = trends.parse_items(text)
        self.assertEqual(list(items), ["a"])
        self.assertEqual(broken, 3)

    def test_날짜_형식이_틀린_줄은_깨진_줄이다(self):
        text = jsonl(item("a", "2026/11/13"), item("b", "2026-13-40"),
                     item("c", 20261113), item("d", "2026-11-13"))
        items, broken = trends.parse_items(text)
        self.assertEqual(list(items), ["d"])
        self.assertEqual(broken, 3)

    def test_모르는_필드는_무시되고_줄은_정상이다(self):
        text = jsonl({**item("a", "2026-11-13"), "extra": 1})
        items, broken = trends.parse_items(text)
        self.assertEqual(list(items), ["a"])
        self.assertEqual(broken, 0)


class 읽음_파일을_읽을_때(unittest.TestCase):
    def test_읽은_id_집합과_깨진_줄_수를_준다(self):
        text = jsonl({"id": "a", "at": "2026-11-13T09:00:00"},
                     {"id": "b", "at": "2026-11-13T09:01:00"},
                     "깨짐", {"id": "c"}, {"id": "", "at": "x"})
        reads, broken = trends.parse_reads(text)
        self.assertEqual(reads, {"a", "b"})
        self.assertEqual(broken, 3)

    def test_같은_id가_여럿이어도_한_번이다(self):
        text = jsonl({"id": "a", "at": "t1"}, {"id": "a", "at": "t2"})
        self.assertEqual(trends.parse_reads(text), ({"a"}, 0))

    def test_빈_텍스트면_빈_집합이다(self):
        self.assertEqual(trends.parse_reads(""), (set(), 0))


class 북마크_파일을_읽을_때(unittest.TestCase):
    def test_켬_끔_켬이면_마지막_줄인_켬이_이긴다(self):
        text = jsonl({"id": "a", "on": True, "at": "t1"},
                     {"id": "a", "on": False, "at": "t2"})
        marks, _ = trends.parse_marks(text)
        self.assertFalse(marks["a"])
        text += jsonl({"id": "a", "on": True, "at": "t3"})
        marks, _ = trends.parse_marks(text)
        self.assertTrue(marks["a"])

    def test_on이_bool이_아니거나_id가_없는_줄은_깨진_줄이다(self):
        text = jsonl({"id": "a", "on": "yes", "at": "t"}, {"on": True, "at": "t"},
                     {"id": "b", "on": True, "at": "t"}, "깨짐")
        marks, broken = trends.parse_marks(text)
        self.assertEqual(marks, {"b": True})
        self.assertEqual(broken, 3)

    def test_빈_텍스트면_빈_결과다(self):
        self.assertEqual(trends.parse_marks(""), ({}, 0))


class 오늘과_지난_글을_나눌_때(unittest.TestCase):
    def setUp(self):
        self.items = items_of(
            item("t1", "2026-11-13"), item("t2", "2026-11-13"), item("t3", "2026-11-13"),
            item("p1", "2026-11-10"), item("p2", "2026-11-12"), item("p3", "2026-11-10"),
            item("f1", "2026-11-14"))

    def test_오늘_글은_파일_순서로_읽음_여부와_함께_온다(self):
        out = trends.split_items(self.items, {"t2"}, {}, TODAY)
        self.assertEqual([g["id"] for g in out["today"]], ["t1", "t2", "t3"])
        self.assertEqual([g["read"] for g in out["today"]], [False, True, False])

    def test_글_모양은_계약_필드를_가진다(self):
        out = trends.split_items(self.items, set(), {"t1": True}, TODAY)
        self.assertEqual(set(out["today"][0]),
                         {"id", "date", "title", "url", "summary", "read", "bookmarked"})
        self.assertTrue(out["today"][0]["bookmarked"])
        self.assertFalse(out["today"][1]["bookmarked"])

    def test_지난_안_읽은_글은_날짜_내림차순이고_같은_날은_파일_순서다(self):
        out = trends.split_items(self.items, set(), {}, TODAY)
        self.assertEqual([g["id"] for g in out["past_unread"]], ["p2", "p1", "p3"])

    def test_읽은_지난_글은_안_읽은_목록에서_빠진다(self):
        out = trends.split_items(self.items, {"p2"}, {}, TODAY)
        self.assertEqual([g["id"] for g in out["past_unread"]], ["p1", "p3"])

    def test_미래_글은_어디에도_없다(self):
        out = trends.split_items(self.items, set(), {}, TODAY)
        ids = [g["id"] for g in out["today"] + out["past_unread"]]
        self.assertNotIn("f1", ids)

    def test_동향이_비면_둘_다_빈_목록이다(self):
        self.assertEqual(trends.split_items({}, set(), {}, TODAY),
                         {"today": [], "past_unread": []})


class 잔디를_계산할_때(unittest.TestCase):
    def test_365칸이고_끝_날짜가_today이고_오래된_날부터다(self):
        cells = trends.heatmap({}, set(), TODAY)
        self.assertEqual(len(cells), 365)
        self.assertEqual(cells[-1]["date"], "2026-11-13")
        self.assertEqual(cells[0]["date"], (TODAY - timedelta(days=364)).isoformat())
        self.assertEqual(cells[-2]["date"], "2026-11-12")
        self.assertEqual(cells[0], {"date": cells[0]["date"], "total": 0, "read": 0})

    def test_days를_넘기면_그_길이다(self):
        self.assertEqual(len(trends.heatmap({}, set(), TODAY, days=7)), 7)

    def test_지난_날_글을_읽으면_그_글_날짜_칸의_read가_오른다(self):
        items = items_of(item("p1", "2026-11-10"), item("t1", "2026-11-13"))
        before = {c["date"]: c for c in trends.heatmap(items, set(), TODAY)}
        after = {c["date"]: c for c in trends.heatmap(items, {"p1"}, TODAY)}
        self.assertEqual(before["2026-11-10"]["read"], 0)
        self.assertEqual(after["2026-11-10"]["read"], 1)
        self.assertEqual(after["2026-11-13"]["read"], 0)
        self.assertEqual(after["2026-11-10"]["total"], 1)

    def test_읽음_집합은_집합이라_같은_id_중복이_1로_센다(self):
        items = items_of(item("a", "2026-11-13"))
        reads, _ = trends.parse_reads(jsonl({"id": "a", "at": "1"}, {"id": "a", "at": "2"}))
        cell = trends.heatmap(items, reads, TODAY)[-1]
        self.assertEqual(cell["read"], 1)

    def test_동향에_없는_id는_세지_않는다(self):
        items = items_of(item("a", "2026-11-13"))
        cell = trends.heatmap(items, {"a", "ghost"}, TODAY)[-1]
        self.assertEqual(cell["read"], 1)

    def test_4건_읽어도_read는_3이고_total은_자르지_않는다(self):
        items = items_of(*[item(f"n{i}", "2026-11-13") for i in range(4)])
        cell = trends.heatmap(items, {f"n{i}" for i in range(4)}, TODAY)[-1]
        self.assertEqual(cell["read"], 3)
        self.assertEqual(cell["total"], 4)

    def test_오늘_글이_4건이면_split은_4건을_다_준다(self):
        items = items_of(*[item(f"n{i}", "2026-11-13") for i in range(4)])
        out = trends.split_items(items, set(), {}, TODAY)
        self.assertEqual(len(out["today"]), 4)

    def test_기간_밖_날짜와_미래_글은_칸에_안_들어간다(self):
        items = items_of(item("old", "2020-01-01"), item("fut", "2026-11-14"))
        cells = trends.heatmap(items, {"old", "fut"}, TODAY)
        self.assertEqual(sum(c["total"] for c in cells), 0)
        self.assertEqual(sum(c["read"] for c in cells), 0)

    def test_북마크는_잔디_건수를_바꾸지_않는다(self):
        items = items_of(item("a", "2026-11-13"), item("b", "2026-11-13"))
        with_marks = trends.heatmap(items, {"a"}, TODAY)
        self.assertEqual(with_marks[-1], {"date": "2026-11-13", "total": 2, "read": 1})
        # 북마크 인자를 받지 않는다 — 읽음만으로 결정된다
        self.assertEqual(with_marks, trends.heatmap(items, {"a"}, TODAY))


class 북마크_목록을_만들_때(unittest.TestCase):
    def setUp(self):
        self.items = items_of(item("a", "2026-11-10"), item("b", "2026-11-12"),
                              item("c", "2026-11-11"))

    def test_켜진_글만_날짜_내림차순으로_온다(self):
        out = trends.bookmark_list(self.items, set(), {"a": True, "b": True, "c": False})
        self.assertEqual([g["id"] for g in out], ["b", "a"])
        self.assertTrue(all(g["bookmarked"] for g in out))

    def test_동향에_없는_id는_뺀다(self):
        out = trends.bookmark_list(self.items, set(), {"ghost": True, "a": True})
        self.assertEqual([g["id"] for g in out], ["a"])

    def test_읽음_여부가_함께_오고_읽어도_북마크는_그대로다(self):
        out = trends.bookmark_list(self.items, {"a"}, {"a": True, "b": True})
        by_id = {g["id"]: g for g in out}
        self.assertTrue(by_id["a"]["read"])
        self.assertFalse(by_id["b"]["read"])
        self.assertTrue(by_id["a"]["bookmarked"])

    def test_북마크가_없으면_빈_목록이다(self):
        self.assertEqual(trends.bookmark_list(self.items, set(), {}), [])
        self.assertEqual(trends.bookmark_list({}, set(), {"a": True}), [])

    def test_북마크는_읽음에_영향을_주지_않는다(self):
        marks = {"a": True}
        before = trends.split_items(self.items, set(), {}, TODAY)
        after = trends.split_items(self.items, set(), marks, TODAY)
        self.assertEqual([g["read"] for g in before["past_unread"]],
                         [g["read"] for g in after["past_unread"]])
        self.assertEqual(trends.unread_count(self.items, set(), TODAY), 3)


class 안_읽은_건수를_셀_때(unittest.TestCase):
    def test_지난_날_포함_읽음_집합에_없는_글_수다(self):
        items = items_of(item("t1", "2026-11-13"), item("p1", "2026-11-10"),
                         item("p2", "2026-11-09"))
        self.assertEqual(trends.unread_count(items, {"p1"}, TODAY), 2)

    def test_미래_글은_뺀다(self):
        items = items_of(item("t1", "2026-11-13"), item("f1", "2026-11-20"))
        self.assertEqual(trends.unread_count(items, set(), TODAY), 1)

    def test_동향에_없는_읽음_id는_영향이_없다(self):
        items = items_of(item("t1", "2026-11-13"))
        self.assertEqual(trends.unread_count(items, {"ghost"}, TODAY), 1)

    def test_빈_동향이면_0이다(self):
        self.assertEqual(trends.unread_count({}, set(), TODAY), 0)


class 상수(unittest.TestCase):
    def test_계약_상수가_있다(self):
        self.assertEqual(trends.HEATMAP_DAYS, 365)
        self.assertEqual(trends.HEATMAP_MAX, 3)


if __name__ == "__main__":
    unittest.main()
