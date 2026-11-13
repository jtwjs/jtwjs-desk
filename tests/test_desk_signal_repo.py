"""레포별 거르기 repos_of · filter_rows (step 7). 🔴 픽스처는 지어낸 값(repo-a · repo-b · task-1 · t01)뿐이다.

엣지 5축: 빈 값(repo 빈 줄) · 비정상 입력(없는 이름 · None · 문자열 아닌 repo) ·
상태 전이(적중 · 보정 줄의 ref 따라가기) · 실패 경로(해당 없음) · 동시성(해당 없음 — 순수 함수).
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from desk import signal

UNKNOWN = "(알수없음)"


def _row(ts, repo="repo-a", **over):
    base = {"ts": ts, "repo": repo, "task": "task-1", "gate": "설계", "area": "BE",
            "hyp": True, "rec": True, "acc": True, "why": False, "rebut": False, "skip": False}
    base.update(over)
    return base


def _hit(ref, hit="right"):
    return {"ref": ref, "hit": hit, "by": "model"}


def _fix(ref, gate):
    return {"ref": ref, "gate": gate, "by": "finn"}


def _mixed():
    return [
        _row("t01", "repo-a", area="FE"),
        _row("t02", "repo-b", area="BE", task="task-2"),
        _hit("t01", "partial"),
        _hit("t02", "wrong"),
        _row("t03", "repo-a", area="BE", hyp=False, skip=True),
        _row("t04", "", area="infra", task=""),
        _fix("t03", None),
        _fix("t02", "계약"),
        _hit("t04", "right"),
        _fix("t04", "삭제"),
    ]


class repos_of_목록(unittest.TestCase):
    def test_나온_순서로_중복_없이_알수없음은_맨_뒤_한_번(self):
        rows = [_row("t01", "repo-a"), _row("t02", "repo-b"), _row("t03", "repo-a"),
                _row("t04", ""), _hit("t01"), _fix("t02", None)]
        self.assertEqual(signal.repos_of(rows), ["repo-a", "repo-b", UNKNOWN])

    def test_알수없음이_먼저_나와도_목록에서는_맨_뒤(self):
        rows = [_row("t01", ""), _row("t02", "repo-a"), _row("t03", None)]
        self.assertEqual(signal.repos_of(rows), ["repo-a", UNKNOWN])

    def test_repo_키_없음_문자열_아님_공백만은_알수없음(self):
        no_key = _row("t01")
        del no_key["repo"]
        rows = [no_key, _row("t02", 7), _row("t03", "   ")]
        self.assertEqual(signal.repos_of(rows), [UNKNOWN])

    def test_적중_보정_줄은_목록에_들지_않는다(self):
        rows = [_hit("t01"), _fix("t01", "설계")]
        self.assertEqual(signal.repos_of(rows), [])

    def test_빈_원장은_빈_목록(self):
        self.assertEqual(signal.repos_of([]), [])


class filter_rows_거르기(unittest.TestCase):
    def test_a_맡김_줄과_그_ts를_ref로_가진_적중_보정_줄만_남는다(self):
        result = signal.filter_rows(_mixed(), "repo-a")
        self.assertEqual(
            [(r.get("ts"), r.get("ref")) for r in result],
            [("t01", None), (None, "t01"), ("t03", None), (None, "t03")])
        self.assertNotIn("t02", [r.get("ref") for r in result])

    def test_원래_순서를_유지한다(self):
        result = signal.filter_rows(_mixed(), "repo-b")
        self.assertEqual([(r.get("ts"), r.get("ref")) for r in result],
                         [("t02", None), (None, "t02"), (None, "t02")])

    def test_알수없음으로_거르면_repo가_빈_줄과_그_줄의_적중_보정만(self):
        result = signal.filter_rows(_mixed(), UNKNOWN)
        self.assertEqual([(r.get("ts"), r.get("ref")) for r in result],
                         [("t04", None), (None, "t04"), (None, "t04")])

    def test_None과_없는_이름은_입력과_같은_내용(self):
        rows = _mixed()
        self.assertEqual(signal.filter_rows(rows, None), rows)
        self.assertEqual(signal.filter_rows(rows, "repo-z"), rows)

    def test_입력_목록과_줄_dict를_변형하지_않는다(self):
        rows = _mixed()
        rows[0]["note"] = "SECRET-TEXT"
        snapshot = copy.deepcopy(rows)
        result = signal.filter_rows(rows, "repo-a")
        self.assertEqual(rows, snapshot)
        self.assertEqual(result[0]["note"], "SECRET-TEXT")
        self.assertEqual(set(result[0]), set(rows[0]))
        self.assertEqual(set(result[1]), set(rows[2]))

    def test_원문_칸이_없는_줄에_새로_더해지지_않는다(self):
        rows = [_row("t01", "repo-a"), _row("t02", "repo-b")]
        for r in signal.filter_rows(rows, "repo-a"):
            self.assertNotIn("SECRET-TEXT", str(r))


class 거른_목록_계산(unittest.TestCase):
    def test_거른_값은_그_레포_줄만_가진_원장의_값과_같다(self):
        only_a = [
            _row("t01", "repo-a", area="FE"),
            _hit("t01", "partial"),
            _row("t03", "repo-a", area="BE", hyp=False, skip=True),
            _fix("t03", None),
        ]
        mixed = _mixed()
        self.assertEqual(
            signal.compute_signal(signal.filter_rows(mixed, "repo-a"), [], 2),
            signal.compute_signal(only_a, [], 2))

    def test_b를_거른_값에_a_줄은_영향이_없다(self):
        only_b = [_row("t02", "repo-b", area="BE", task="task-2"),
                  _hit("t02", "wrong"), _fix("t02", "계약")]
        self.assertEqual(
            signal.compute_signal(signal.filter_rows(_mixed(), "repo-b"), [], 2),
            signal.compute_signal(only_b, [], 2))


if __name__ == "__main__":
    unittest.main()
