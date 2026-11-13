"""GET /hypothesis-signal?repo= (step 8).

엣지 5축: 빈 값(repo 빈 문자열) · 비정상 입력(모르는 레포 이름) · 실패 경로(missing 응답에는 repos 없음) ·
상태 전이(해당 없음 — 매 요청 새로 읽음) · 동시성(해당 없음 — 읽기 전용, 바이트 동일).
🔴 픽스처는 임시 폴더 안의 지어낸 값(repo-a · repo-b · task-1)뿐이다.
"""
import hashlib
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
            "hyp": True, "rec": True, "acc": True, "why": False, "rebut": False, "skip": False,
            "hyp_text": "SECRET-TEXT"}
    base.update(over)
    return base


ROWS = [
    _row("t1"),
    _row("t2", repo="repo-b", area="FE", task="task-2", acc=True, why=False),
    {"ref": "t1", "hit": "right", "by": "model"},
    _row("t3", hyp=False, skip=True),
    _row("t4", repo="repo-b", area="infra", task="task-2", why=True),
]


def _expected(repo):
    rows, broken = signal.parse_ledger(_lines(ROWS))
    return signal.compute_signal(signal.filter_rows(rows, repo), broken, 2)


def _strip(body):
    return {k: v for k, v in body.items() if k not in ("missing", "repos")}


class _RepoCase(_ReviewCase):
    def setUp(self):
        super().setUp()
        self.ledger = Path(self._tmp.name) / "ledger.jsonl"
        self.ledger.write_text(_lines(ROWS), encoding="utf-8")
        self.cfg = {"hypothesis_ledger": str(self.ledger), "hypothesis_streak_threshold": 2}

    def _write_cfg(self, **over):
        cfg = dict(self.cfg)
        cfg.update(over)
        self.cfg_path.write_text(json.dumps({k: v for k, v in cfg.items() if v is not None}),
                                 encoding="utf-8")


class 서버_build_hypothesis_signal_repo(_RepoCase):
    def test_repo가_없으면_전체_값에_repos_목록이_붙는다(self):
        body = server.build_hypothesis_signal(self.cfg)
        self.assertEqual(_strip(body), _expected(None))
        self.assertEqual(body["repos"], ["repo-a", "repo-b"])
        self.assertIsNone(body["missing"])

    def test_repo_a면_a_줄만으로_센_값이고_repos는_전체다(self):
        body = server.build_hypothesis_signal(self.cfg, "repo-a")
        self.assertEqual(_strip(body), _expected("repo-a"))
        self.assertNotEqual(_strip(body), _expected(None))
        self.assertEqual(body["repos"], ["repo-a", "repo-b"])

    def test_모르는_레포_이름은_전체와_같다(self):
        body = server.build_hypothesis_signal(self.cfg, "no-such-repo")
        self.assertEqual(_strip(body), _expected(None))
        self.assertEqual(body["repos"], ["repo-a", "repo-b"])

    def test_원장_파일은_바이트까지_안_바뀐다(self):
        before = hashlib.sha256(self.ledger.read_bytes()).hexdigest()
        server.build_hypothesis_signal(self.cfg, "repo-a")
        self.assertEqual(hashlib.sha256(self.ledger.read_bytes()).hexdigest(), before)

    def test_missing_응답에는_repos가_없다(self):
        self.assertNotIn("repos", server.build_hypothesis_signal({}, "repo-a"))
        self.assertNotIn("repos", server.build_hypothesis_signal(
            {"hypothesis_ledger": str(self.ledger.parent / "none.jsonl")}, "repo-a"))

    def test_응답에_원문이_없다(self):
        body = server.build_hypothesis_signal(self.cfg, "repo-a")
        self.assertNotIn("SECRET-TEXT", json.dumps(body, ensure_ascii=False))


class 통합_GET_hypothesis_signal_repo(_RepoCase):
    def test_쿼리_repo_a가_200이고_build와_같은_본문이다(self):
        self._write_cfg()
        status, body = self._get("/hypothesis-signal?repo=" + quote("repo-a"))
        self.assertEqual(status, 200)
        self.assertEqual(body, server.build_hypothesis_signal(self.cfg, "repo-a"))
        self.assertNotIn("SECRET-TEXT", json.dumps(body, ensure_ascii=False))

    def test_쿼리가_없거나_빈_문자열이면_전체다(self):
        self._write_cfg()
        _, none_body = self._get("/hypothesis-signal")
        _, empty_body = self._get("/hypothesis-signal?repo=")
        self.assertEqual(none_body, empty_body)
        self.assertEqual(_strip(none_body), _expected(None))

    def test_쿼리가_있어도_missing은_repos없이_200이다(self):
        self._write_cfg(hypothesis_ledger=None)
        status, body = self._get("/hypothesis-signal?repo=repo-a")
        self.assertEqual(status, 200)
        self.assertEqual(body, {"missing": "설정 없음"})
