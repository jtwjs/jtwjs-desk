"""GET /hypothesis-signal 응답의 diff 키 (step 11). 🔴 픽스처는 임시 폴더 안의 지어낸 값뿐이다.

엣지 5축: 빈 값(빈 원장) · 비정상 입력(해당 없음) · 실패 경로(missing 응답에는 diff 없음) ·
상태 전이(해당 없음 — 매 요청 새로 읽음) · 동시성(해당 없음 — 읽기 전용).
"""
import json
import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_desk_server_review import _ReviewCase
from desk import signal
from page import server


def _lines(rows):
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)


def _row(ts, **over):
    base = {"ts": ts, "repo": "repo-a", "task": "task-1", "gate": "API 계약", "area": "BE",
            "diff": "hard", "hyp": True, "rec": True, "acc": True, "why": False, "rebut": False,
            "skip": False, "hyp_text": "SECRET-TEXT"}
    base.update(over)
    return base


ROWS = [
    _row("t1"),
    _row("t2", repo="repo-b", diff="easy", task="task-2"),
    {"ref": "t1", "hit": "right", "by": "model"},
    _row("t3", diff="mid"),
    _row("t4", repo="repo-b", diff=None, task="task-2"),
]


def _table(repo=None):
    rows, _ = signal.parse_ledger(_lines(ROWS))
    return signal.diff_table(signal.filter_rows(rows, repo))


class _DiffCase(_ReviewCase):
    def setUp(self):
        super().setUp()
        self.ledger = Path(self._tmp.name) / "ledger.jsonl"
        self.ledger.write_text(_lines(ROWS), encoding="utf-8")
        self.cfg = {"hypothesis_ledger": str(self.ledger), "hypothesis_streak_threshold": 2}

    def _write_cfg(self, **over):
        cfg = {**self.cfg, **over}
        self.cfg_path.write_text(json.dumps({k: v for k, v in cfg.items() if v is not None}),
                                 encoding="utf-8")


class 서버_build_hypothesis_signal_diff(_DiffCase):
    def test_응답에_diff가_있고_diff_table과_같다(self):
        body = server.build_hypothesis_signal(self.cfg)
        self.assertEqual(body["diff"], _table(None))
        self.assertEqual(body["diff"]["hard"]["right"], 1)

    def test_repo_a면_a_줄만_센다(self):
        body = server.build_hypothesis_signal(self.cfg, "repo-a")
        self.assertEqual(body["diff"], _table("repo-a"))
        self.assertEqual(body["diff"]["easy"], {"right": 0, "partial": 0, "wrong": 0, "pending": 0})
        self.assertEqual(body["diff"]["none"]["pending"], 0)
        self.assertNotEqual(body["diff"], _table(None))

    def test_응답에_원문이_없다(self):
        body = server.build_hypothesis_signal(self.cfg, "repo-a")
        self.assertNotIn("SECRET-TEXT", json.dumps(body, ensure_ascii=False))

    def test_missing_응답에는_diff가_없다(self):
        self.assertNotIn("diff", server.build_hypothesis_signal({}))
        self.assertNotIn("diff", server.build_hypothesis_signal(
            {"hypothesis_ledger": str(self.ledger.parent / "none.jsonl")}))

    def test_빈_원장은_네_키_모두_0이다(self):
        self.ledger.write_text("", encoding="utf-8")
        body = server.build_hypothesis_signal(self.cfg)
        self.assertEqual(set(body["diff"]), {"easy", "mid", "hard", "none"})
        for cell in body["diff"].values():
            self.assertEqual(cell, {"right": 0, "partial": 0, "wrong": 0, "pending": 0})


class 통합_GET_hypothesis_signal_diff(_DiffCase):
    def test_쿼리_repo_a가_200이고_diff가_build와_같다(self):
        self._write_cfg()
        status, body = self._get("/hypothesis-signal?repo=" + quote("repo-a"))
        self.assertEqual(status, 200)
        self.assertEqual(body["diff"], _table("repo-a"))
        self.assertNotIn("SECRET-TEXT", json.dumps(body, ensure_ascii=False))

    def test_원장_없음_응답에는_diff_키가_없다(self):
        self._write_cfg(hypothesis_ledger=None)
        status, body = self._get("/hypothesis-signal")
        self.assertEqual(status, 200)
        self.assertNotIn("diff", body)
