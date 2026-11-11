"""desk/rollup.py (step 4). 픽스처는 전부 지어낸 것."""
import json
import unittest
from datetime import date

from desk import rollup


class WeekDatesTest(unittest.TestCase):
    def test_length_and_order(self):
        got = rollup.week_dates(date(2026, 1, 10))
        self.assertEqual(len(got), 7)
        self.assertEqual(got[0], "2026-01-04")
        self.assertEqual(got[-1], "2026-01-10")
        self.assertEqual(got, sorted(got))

    def test_month_boundary(self):
        got = rollup.week_dates(date(2026, 3, 2))
        self.assertEqual(got[0], "2026-02-24")
        self.assertIn("2026-02-28", got)
        self.assertIn("2026-03-01", got)

    def test_custom_n(self):
        self.assertEqual(rollup.week_dates(date(2026, 1, 1), 2), ["2025-12-31", "2026-01-01"])


class AggregateTest(unittest.TestCase):
    def test_sums(self):
        days = [
            ("2026-01-01", {"sessions": 2, "stuck": 1,
                            "repos": [{"name": "a", "commits": 3, "progress": ["p1"]}],
                            "cards": [{"summary": "x"}, {"summary": "y"}]}),
            ("2026-01-02", {"sessions": 4, "stuck": 0,
                            "repos": [{"name": "b", "commits": 5, "progress": []}],
                            "cards": [{"summary": "z"}]}),
        ]
        r = rollup.aggregate(days)
        self.assertEqual(r["days"], 2)
        self.assertEqual(r["present"], 2)
        self.assertEqual(r["missing"], [])
        self.assertEqual(r["sessions"], 6)
        self.assertEqual(r["stuck"], 1)
        self.assertEqual(r["commits"], 8)
        self.assertEqual(r["cards"], 3)
        self.assertEqual(r["projects"], 2)

    def test_missing_days(self):
        r = rollup.aggregate([("2026-01-01", None), ("2026-01-02", {"sessions": 1})])
        self.assertEqual(r["days"], 2)
        self.assertEqual(r["present"], 1)
        self.assertEqual(r["missing"], ["2026-01-01"])
        self.assertEqual(r["sessions"], 1)

    def test_all_none(self):
        r = rollup.aggregate([("2026-01-01", None), ("2026-01-02", None)])
        self.assertEqual(r["present"], 0)
        self.assertEqual(r["missing"], ["2026-01-01", "2026-01-02"])
        for k in ("sessions", "stuck", "commits", "cards", "projects"):
            self.assertEqual(r[k], 0)
        self.assertEqual(r["repos"], [])

    def test_merge_same_repo(self):
        days = [
            ("2026-01-01", {"repos": [{"name": "a", "commits": 2, "progress": ["p1", "p2"]}]}),
            ("2026-01-02", {"repos": [{"name": "a", "commits": 3, "progress": ["p2", "p3"]}]}),
        ]
        r = rollup.aggregate(days)
        self.assertEqual(r["projects"], 1)
        self.assertEqual(r["commits"], 5)
        self.assertEqual(r["repos"], [{"name": "a", "commits": 5, "progress": ["p1", "p2", "p3"]}])

    def test_wrong_types_ignored(self):
        days = [
            ("2026-01-01", {"sessions": "많음", "stuck": None, "repos": "x", "cards": 7}),
            ("2026-01-02", {"sessions": 2, "repos": [{"name": "a", "commits": "3", "progress": "p"},
                                                      "junk", {"commits": 4}, 5]}),
            ("2026-01-03", ["not a dict"]),
        ]
        r = rollup.aggregate(days)
        self.assertEqual(r["sessions"], 2)
        self.assertEqual(r["stuck"], 0)
        self.assertEqual(r["cards"], 0)
        self.assertEqual(r["commits"], 0)
        self.assertEqual(r["repos"], [{"name": "a", "commits": 0, "progress": []}])

    def test_raw_keys_not_passed_through(self):
        days = [("2026-01-01", {
            "sessions": 1, "prompts": ["SECRET-PROMPT-TEXT"], "title": "SECRET-TITLE-TEXT",
            "cwd": "/SECRET/CWD",
            "repos": [{"name": "a", "commits": 1, "progress": [], "title": "SECRET-TITLE-TEXT",
                       "cwd": "/SECRET/CWD"}],
            "cards": [{"summary": "SECRET-SUMMARY-TEXT"}],
        })]
        r = rollup.aggregate(days)
        dumped = json.dumps(r, ensure_ascii=False)
        for s in ("SECRET-PROMPT-TEXT", "SECRET-TITLE-TEXT", "/SECRET/CWD", "SECRET-SUMMARY-TEXT"):
            self.assertNotIn(s, dumped)
        self.assertEqual(set(r), {"days", "present", "missing", "sessions", "stuck",
                                  "commits", "cards", "projects", "repos"})
        self.assertEqual(set(r["repos"][0]), {"name", "commits", "progress"})


if __name__ == "__main__":
    unittest.main()
