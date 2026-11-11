"""desk/ledger.py 중 observations · friction · score 관련 함수 (step 3). 픽스처는 전부 지어낸 것."""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from desk import ledger

OBS = """# 관찰 (지어낸 픽스처)

## 열린 것
| 패턴 | 종류 | 횟수 | 마지막 | 근거 |
|---|---|---|---|---|
| 샘플 패턴 A | 재지시 | 3 | 2026-01-05 | #1 #2 |
| 샘플 패턴 B | 수작업 | 1 | 2026-01-06 | #3 |
| 샘플 패턴 C | 재지시 | 많음 | 2026-01-07 | #4 |

## 닫힌 것
| 패턴 | 횟수 | 판정 | 어디로 |
|---|---|---|---|
| 닫힌 샘플 패턴 Z | 5 | 승격 | rules |
"""

FRICTION = """# 마찰 (지어낸 픽스처)

| 패턴 | 상태 | 횟수 |
|---|---|---|
| 샘플 패턴 F1 | 열림 | 4 |
| 샘플 패턴 F2 | 보류 | 2 |
| 샘플 패턴 F3 | 닫힘 | 9 |
"""


class TestParseObservations(unittest.TestCase):
    def test_열린것만_읽고_닫힌것은_무시한다(self):
        rows = ledger.parse_observations(OBS)
        self.assertEqual([r["pattern"] for r in rows],
                         ["샘플 패턴 A", "샘플 패턴 B", "샘플 패턴 C"])
        self.assertEqual(rows[0], {"pattern": "샘플 패턴 A", "kind": "재지시", "count": 3,
                                   "last": "2026-01-05", "evidence": "#1 #2"})

    def test_횟수가_정수가_아니면_None과_unparsed다(self):
        row = ledger.parse_observations(OBS)[2]
        self.assertIsNone(row["count"])
        self.assertTrue(row["unparsed"])

    def test_열린것_헤딩이_없으면_빈_목록이다(self):
        self.assertEqual(ledger.parse_observations("## 닫힌 것\n| a | b |\n"), [])
        self.assertEqual(ledger.parse_observations(""), [])


class TestParseFriction(unittest.TestCase):
    def test_열림_보류_행만_낸다(self):
        rows = ledger.parse_friction(FRICTION)
        self.assertEqual(rows, [
            {"pattern": "샘플 패턴 F1", "status": "열림", "count": 4},
            {"pattern": "샘플 패턴 F2", "status": "보류", "count": 2},
        ])

    def test_헤더가_없으면_unparsed_한_건이고_원문이_없다(self):
        text = "그냥 줄글 비밀문장 XYZ\n- 목록 비밀문장 XYZ\n"
        rows = ledger.parse_friction(text)
        self.assertEqual(rows, [{"unparsed": True}])
        self.assertNotIn("XYZ", json.dumps(rows, ensure_ascii=False))

    def test_칸_수가_헤더와_다른_행은_unparsed로_바뀐다(self):
        text = FRICTION + "| 비밀문장 QQQ | 열림 |\n"
        rows = ledger.parse_friction(text)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[2], {"unparsed": True})
        self.assertNotIn("QQQ", json.dumps(rows, ensure_ascii=False))


class TestWorkflowRows(unittest.TestCase):
    def test_3회_이상만_highlight다(self):
        rows = ledger.workflow_rows(
            [{"pattern": "a", "count": 3}, {"pattern": "b", "count": 2}],
            [{"pattern": "c", "status": "열림", "count": 4}])
        by = {r["pattern"]: r for r in rows}
        self.assertTrue(by["a"]["highlight"])
        self.assertFalse(by["b"]["highlight"])
        self.assertTrue(by["c"]["highlight"])
        self.assertEqual(by["a"]["source"], "observations")
        self.assertEqual(by["c"]["source"], "friction")

    def test_횟수_내림차순이고_None은_맨_뒤다(self):
        rows = ledger.workflow_rows(
            [{"pattern": "x", "count": 1}, {"pattern": "n", "count": None, "unparsed": True},
             {"pattern": "y", "count": 3}],
            [{"unparsed": True}, {"pattern": "z", "count": 3}])
        self.assertEqual([r.get("pattern") for r in rows], ["y", "z", "x", "n", None])
        self.assertFalse(rows[3]["highlight"])
        self.assertFalse(rows[4]["highlight"])

    def test_unparsed_행도_포함한다(self):
        rows = ledger.workflow_rows([], [{"unparsed": True}])
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["unparsed"])


class TestParseScore(unittest.TestCase):
    def test_total_grade만_꺼낸다(self):
        text = json.dumps({"total": 72, "grade": "B", "other": "x"})
        self.assertEqual(ledger.parse_score(text), {"total": 72, "grade": "B"})

    def test_깨진_JSON이면_None이다(self):
        self.assertIsNone(ledger.parse_score("{not json"))

    def test_키가_빠지면_None이다(self):
        self.assertIsNone(ledger.parse_score(json.dumps({"total": 1})))
        self.assertIsNone(ledger.parse_score(json.dumps([1, 2])))


class TestFindScoreFile(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def _put(self, rel):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("{}", encoding="utf-8")
        return p

    def test_아무_데도_없으면_None이다(self):
        self.assertIsNone(ledger.find_score_file(self.root))

    def test_reports는_최신_날짜_폴더가_이긴다(self):
        self._put(".claude/reports/2026-01-01/ai-readiness-score.json")
        newest = self._put(".claude/reports/2026-03-01/ai-readiness-score.json")
        self._put(".claude/reports/2026-02-01/ai-readiness-score.json")
        self._put("docs/ai-readiness-score.json")
        self.assertEqual(ledger.find_score_file(self.root), (newest, "2026-03-01"))

    def test_reports가_없으면_docs가_이긴다(self):
        docs = self._put("docs/ai-readiness-score.json")
        self._put(".claude/ai-readiness-score.json")
        self._put("ai-readiness-score.json")
        self.assertEqual(ledger.find_score_file(self.root), (docs, None))

    def test_docs가_없으면_dot_claude가_루트보다_먼저다(self):
        dot = self._put(".claude/ai-readiness-score.json")
        self._put("ai-readiness-score.json")
        self.assertEqual(ledger.find_score_file(self.root), (dot, None))

    def test_마지막은_레포_루트다(self):
        top = self._put("ai-readiness-score.json")
        self.assertEqual(ledger.find_score_file(self.root), (top, None))

    def test_날짜가_아닌_폴더_이름은_무시한다(self):
        self._put(".claude/reports/latest/ai-readiness-score.json")
        self.assertIsNone(ledger.find_score_file(self.root))


class TestAgeDays(unittest.TestCase):
    def test_일수_차를_센다(self):
        self.assertEqual(ledger.age_days(date(2026, 1, 1), date(2026, 1, 11)), 10)

    def test_같은_날은_0이다(self):
        self.assertEqual(ledger.age_days(date(2026, 1, 1), date(2026, 1, 1)), 0)

    def test_미래_날짜는_0이다(self):
        self.assertEqual(ledger.age_days(date(2026, 2, 1), date(2026, 1, 1)), 0)


if __name__ == "__main__":
    unittest.main()
