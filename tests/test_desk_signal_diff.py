"""난이도 × 상태 건수 표 diff_table (step 11). 🔴 픽스처는 지어낸 값(repo-a · task-1 · t01)뿐이다.

엣지 5축: 빈 값(빈 원장 · diff 칸 없음) · 비정상 입력(null · 집합 밖 값) ·
상태 전이(보정으로 의미 없는 줄 · 같은 ref 적중 둘) · 실패 경로(해당 없음) · 동시성(해당 없음 — 순수 함수).
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from desk import signal

ZERO = {"right": 0, "partial": 0, "wrong": 0, "pending": 0}


def _row(ts, **over):
    base = {"ts": ts, "repo": "repo-a", "task": "task-1", "gate": "설계", "area": "BE", "diff": "easy",
            "hyp": True, "rec": True, "acc": True, "why": False, "rebut": False, "skip": False}
    base.update(over)
    return base


def _hit(ref, hit="right"):
    return {"ref": ref, "hit": hit, "by": "model"}


def _cell(**over):
    return {**ZERO, **over}


class diff_table_건수(unittest.TestCase):
    def test_빈_원장은_네_키_모두_0이다(self):
        self.assertEqual(signal.diff_table([]),
                         {"easy": _cell(), "mid": _cell(), "hard": _cell(), "none": _cell()})

    def test_쉬움_보통_어려움이_섞이면_칸마다_예상_건수다(self):
        rows = [_row("t01", diff="easy"), _row("t02", diff="easy"), _row("t03", diff="mid"),
                _row("t04", diff="hard"), _row("t05", diff="hard"), _row("t06", diff="hard"),
                _hit("t01", "right"), _hit("t02", "wrong"), _hit("t03", "partial"),
                _hit("t04", "right"), _hit("t05", "right")]
        self.assertEqual(signal.diff_table(rows), {
            "easy": _cell(right=1, wrong=1),
            "mid": _cell(partial=1),
            "hard": _cell(right=2, pending=1),
            "none": _cell(),
        })

    def test_diff_칸_없음_null_집합_밖은_전부_none이다(self):
        no_key = _row("t01")
        del no_key["diff"]
        rows = [no_key, _row("t02", diff=None), _row("t03", diff="x"), _row("t04", diff=3),
                _hit("t01", "right")]
        table = signal.diff_table(rows)
        self.assertEqual(table["none"], _cell(right=1, pending=3))
        for key in ("easy", "mid", "hard"):
            self.assertEqual(table[key], _cell())

    def test_같은_ref_적중_둘은_마지막_값만_센다(self):
        rows = [_row("t01"), _hit("t01", "wrong"), _hit("t01", "partial")]
        self.assertEqual(signal.diff_table(rows)["easy"], _cell(partial=1))

    def test_적중_줄_없고_hyp만_있으면_pending이다(self):
        self.assertEqual(signal.diff_table([_row("t01", hyp=True)])["easy"], _cell(pending=1))

    def test_적중도_가설도_없는_줄은_어느_칸에도_안_센다(self):
        rows = [_row("t01", hyp=False, rec=True)]
        self.assertEqual(signal.diff_table(rows)["easy"], _cell())

    def test_의미_없는_줄은_어느_칸에도_안_든다(self):
        rows = [_row("t01", gate=None, hyp=False, rec=False), _hit("t01", "right")]
        table = signal.diff_table(rows)
        self.assertTrue(all(table[k] == _cell() for k in table))


class diff_table_보정(unittest.TestCase):
    def test_보정으로_gate가_비어_의미_없는_줄이_되면_표에서_빠진다(self):
        rows = [_row("t01", hyp=False, rec=False), {"ref": "t01", "gate": None, "by": "finn"},
                _row("t02", hyp=False, rec=False), _hit("t02", "right")]
        self.assertEqual(signal.diff_table(rows)["easy"], _cell(right=1))

    def test_보정으로_gate가_채워지면_표에_들어온다(self):
        rows = [_row("t01", gate=None, hyp=False, rec=False),
                {"ref": "t01", "gate": "설계", "by": "finn"}, _hit("t01", "wrong")]
        self.assertEqual(signal.diff_table(rows)["easy"], _cell(wrong=1))


class diff_table_순수(unittest.TestCase):
    def test_입력_rows를_바꾸지_않고_원문_칸은_결과에_없다(self):
        rows = [_row("t01", hyp_text="SECRET-TEXT"), _hit("t01")]
        before = copy.deepcopy(rows)
        out = signal.diff_table(rows)
        self.assertEqual(rows, before)
        self.assertNotIn("SECRET-TEXT", repr(out))


if __name__ == "__main__":
    unittest.main()
