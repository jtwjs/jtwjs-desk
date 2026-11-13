"""보정 줄 {ref, gate, by} 반영 (step 6). 🔴 픽스처는 지어낸 값(repo-a · task-1 · t01)뿐이다.

엣지 5축: 빈 값(보정만 있는 원장) · 비정상 입력(없는 ref) · 상태 전이(같은 ref 두 번) ·
실패 경로(해당 없음) · 동시성(해당 없음 — 순수 함수).
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from desk import signal
from page import server


def _row(ts, **over):
    base = {"ts": ts, "repo": "repo-a", "task": "task-1", "gate": "설계", "area": "BE",
            "hyp": False, "rec": True, "acc": True, "why": False, "rebut": False, "skip": False}
    base.update(over)
    return base


def _fix(ref, gate):
    return {"ref": ref, "gate": gate, "by": "finn"}


def _compute(rows, threshold=None):
    return signal.compute_signal(rows, [], threshold)


class 보정_줄_반영(unittest.TestCase):
    def test_null에서_설계로_보정되면_이유_없이_수락_분모에_들어온다(self):
        base = [_row("t01"), _row("t02", gate=None)]
        before = _compute(base)
        after = _compute(base + [_fix("t02", "설계")])
        self.assertEqual(before["acc_no_reason"], {"n": 1, "m": 1, "pct": 100})
        self.assertEqual(after["acc_no_reason"], {"n": 2, "m": 2, "pct": 100})
        self.assertEqual(after["meaningful"], 2)
        self.assertEqual(after["areas"]["BE"]["count"], 2)

    def test_설계에서_null로_보정되면_분모와_의미_있는_줄에서_빠진다(self):
        rows = [_row("t01"), _row("t02", rec=False, acc=False), _row("t03", acc=False)]
        result = _compute(rows + [_fix("t02", None)])
        self.assertEqual(result["meaningful"], 2)
        self.assertEqual(result["areas"]["BE"]["count"], 2)
        self.assertEqual(result["acc_no_reason"], {"n": 1, "m": 2, "pct": 50})

    def test_null_보정은_연속에서도_빠진다(self):
        rows = [_row("t01"), _row("t02"), _row("t03")]
        self.assertEqual(_compute(rows, 2)["streak"], 3)
        fixed = _compute(rows + [_fix("t02", None)], 2)
        self.assertEqual(fixed["streak"], 2)

    def test_같은_ref_보정_두_줄은_마지막이_유효하다(self):
        rows = [_row("t01", gate=None)]
        a = _compute(rows + [_fix("t01", "설계"), _fix("t01", None)])
        b = _compute(rows + [_fix("t01", None), _fix("t01", "설계")])
        self.assertEqual(a["acc_no_reason"]["m"], 0)
        self.assertEqual(b["acc_no_reason"]["m"], 1)

    def test_보정_줄은_맡김_줄_수에_들지_않는다(self):
        rows = [_row("t01", task=None, skip=True)]
        plain = _compute(rows)
        fixed = _compute(rows + [_fix("t01", "설계")])
        for key in ("meaningful", "no_ident", "skipped", "empty"):
            self.assertEqual(fixed[key], plain[key], key)
        self.assertEqual(fixed["no_ident"], 1)
        self.assertEqual(fixed["skipped"], 1)

    def test_보정만_있는_원장은_비어_있다(self):
        result = _compute([_fix("t01", "설계"), _fix("t02", None)])
        self.assertTrue(result["empty"])
        self.assertEqual(result["meaningful"], 0)
        self.assertEqual(result["no_ident"], 0)

    def test_없는_ref의_보정은_무시된다(self):
        rows = [_row("t01"), _row("t02", gate=None)]
        self.assertEqual(_compute(rows + [_fix("t99", "설계"), _fix("t99", None)]), _compute(rows))

    def test_적중_줄과_보정_줄이_섞여도_영역별_적중이_그대로다(self):
        rows = [_row("t01", hyp=True), _row("t02", area="FE", hyp=True)]
        hits = [{"ref": "t01", "hit": "right", "by": "model"},
                {"ref": "t02", "hit": "wrong", "by": "finn"}]
        plain = _compute(rows + hits)
        mixed = _compute(rows + [_fix("t01", "설계")] + hits + [_fix("t02", "설계")])
        self.assertEqual(mixed["areas"], plain["areas"])
        self.assertEqual(mixed["areas"]["BE"]["right"], 1)
        self.assertEqual(mixed["areas"]["FE"]["wrong"], 1)

    def test_hit이_유효하면_gate가_있어도_적중_줄이다(self):
        rows = [_row("t01", gate=None, hyp=True)]
        hit = {"ref": "t01", "hit": "partial", "by": "model", "gate": "설계"}
        result = _compute(rows + [hit])
        self.assertEqual(result["areas"]["BE"]["partial"], 1)
        self.assertEqual(result["meaningful"], 1)

    def test_보정이_없는_원장은_이전과_같은_dict다(self):
        rows = [_row("t01", hyp=True), _row("t02", gate=None, acc=False)]
        result = _compute(rows)
        self.assertEqual(set(result), {"areas", "unknown_area", "hyp_first", "acc_no_reason",
                                       "streak", "reasked", "skipped", "no_ident", "broken",
                                       "meaningful", "empty"})
        self.assertEqual(result, _compute(list(rows)))
        self.assertEqual(result["meaningful"], 2)
        self.assertEqual(result["acc_no_reason"], {"n": 1, "m": 1, "pct": 100})

    def test_gate_키가_없는_ref_줄은_보정이_아니다(self):
        rows = [_row("t01")]
        self.assertEqual(_compute(rows + [{"ref": "t01", "by": "finn"}]), _compute(rows))


class 서버_경로(unittest.TestCase):
    def test_보정_줄이_든_원장_파일에서_유효_gate_기준_값이_나온다(self):
        rows = [_row("t01", gate=None, area="BE"), _row("t02", gate=None, area="FE", rec=False, acc=False),
                _fix("t01", "설계"), {"ref": "t02", "hit": "right", "by": "model"}]
        rows[0]["hyp_text"] = "SECRET-TEXT"
        rows[1]["why_text"] = "SECRET-TEXT"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.jsonl"
            path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                            encoding="utf-8")
            body = server.build_hypothesis_signal({"hypothesis_ledger": str(path)})
        self.assertIsNone(body["missing"])
        self.assertEqual(body["meaningful"], 1)
        self.assertEqual(body["acc_no_reason"], {"n": 1, "m": 1, "pct": 100})
        self.assertEqual(body["areas"]["BE"]["count"], 1)
        self.assertEqual(body["areas"]["FE"]["count"], 0)
        self.assertEqual(body["no_ident"], 0)
        self.assertNotIn("SECRET-TEXT", json.dumps(body, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
