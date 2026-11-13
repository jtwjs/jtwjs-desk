"""GET /hypothesis-signal (step 3).

엣지 5축: 빈 값(맡김 줄 0건) · 비정상 입력(깨진 줄 · 읽을 수 없는 바이트) · 실패 경로(설정 없음 · 파일 없음) ·
상태 전이(해당 없음 — 매 요청 새로 읽음) · 동시성(해당 없음 — 읽기 전용, 요청 전후 바이트 동일).
🔴 픽스처는 임시 폴더 안의 지어낸 값(repo-a · task-1)뿐이다.
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_desk_server_review import _ReviewCase
from desk import signal
from page import server


def _lines(rows):
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)


def _row(ts, **over):
    base = {"ts": ts, "repo": "repo-a", "task": "task-1", "gate": "API 계약", "area": "BE",
            "hyp": True, "rec": True, "acc": True, "why": False, "rebut": False, "skip": False}
    base.update(over)
    return base


class 통합_GET_hypothesis_signal(_ReviewCase):
    def setUp(self):
        super().setUp()
        self.ledger = Path(self._tmp.name) / "ledger.jsonl"

    def _cfg(self, **over):
        cfg = {"hypothesis_ledger": str(self.ledger), "hypothesis_streak_threshold": 2}
        cfg.update(over)
        self.cfg_path.write_text(json.dumps({k: v for k, v in cfg.items() if v is not None}),
                                 encoding="utf-8")

    def test_설정이_없으면_설정_없음_이유다(self):
        self._cfg(hypothesis_ledger=None)
        status, body = self._get("/hypothesis-signal")
        self.assertEqual(status, 200)
        self.assertEqual(body, {"missing": "설정 없음"})

    def test_파일이_없으면_파일_없음_이유다(self):
        self._cfg()
        status, body = self._get("/hypothesis-signal")
        self.assertEqual(status, 200)
        self.assertEqual(body, {"missing": "파일 없음"})

    def test_경로의_폴더가_없어도_파일_없음_이유다(self):
        self._cfg(hypothesis_ledger=str(Path(self._tmp.name) / "no-dir" / "ledger.jsonl"))
        _, body = self._get("/hypothesis-signal")
        self.assertEqual(body, {"missing": "파일 없음"})

    def test_읽을_수_없는_바이트면_형식_확인_필요_이유다(self):
        self.ledger.write_bytes(b"\xff\xfe\x00\x80 not utf8")
        self._cfg()
        status, body = self._get("/hypothesis-signal")
        self.assertEqual(status, 200)
        self.assertEqual(body, {"missing": "형식 확인 필요"})

    def test_정상_원장이면_compute_signal과_같은_값에_missing_null이다(self):
        rows = [_row("t1"), _row("t2", hyp=False, acc=True, why=False),
                _row("t3", area="FE", task="task-2"), {"ref": "t1", "hit": "right", "by": "model"}]
        self.ledger.write_text(_lines(rows), encoding="utf-8")
        self._cfg()
        status, body = self._get("/hypothesis-signal")
        self.assertEqual(status, 200)
        parsed, broken = signal.parse_ledger(self.ledger.read_text(encoding="utf-8"))
        expected = signal.compute_signal(parsed, broken, 2)
        self.assertIsNone(body["missing"])
        self.assertEqual({k: v for k, v in body.items() if k not in ("missing", "repos", "diff")}, expected)

    def test_깨진_줄_1개는_broken에_줄_번호가_실린다(self):
        self.ledger.write_text(_lines([_row("t1")]) + "{not json\n" + _lines([_row("t2")]),
                               encoding="utf-8")
        self._cfg()
        _, body = self._get("/hypothesis-signal")
        self.assertIsNone(body["missing"])
        self.assertEqual([b["line"] for b in body["broken"]], [2])

    def test_맡김_줄_0건이면_missing_null이고_empty_true다(self):
        self.ledger.write_text("", encoding="utf-8")
        self._cfg()
        status, body = self._get("/hypothesis-signal")
        self.assertEqual(status, 200)
        self.assertIsNone(body["missing"])
        self.assertIs(body["empty"], True)

    def test_요청_전후로_원장_바이트가_같다(self):
        self.ledger.write_text(_lines([_row("t1"), _row("t2")]) + "{broken\n", encoding="utf-8")
        self._cfg()
        before = hashlib.sha256(self.ledger.read_bytes()).hexdigest()
        self._get("/hypothesis-signal")
        self._get("/hypothesis-signal")
        self.assertEqual(hashlib.sha256(self.ledger.read_bytes()).hexdigest(), before)
        self.assertEqual(sorted(p.name for p in self.ledger.parent.glob("ledger*")), ["ledger.jsonl"])

    def test_쓰기_메서드는_이_경로에_없다(self):
        self.assertFalse(hasattr(server._DeskRequestHandler, "do_PUT"))
        self._cfg()
        status, _ = self._post("/hypothesis-signal", {"x": 1})
        self.assertNotEqual(status, 200)

    def test_원문_칸은_응답에_실리지_않는다(self):
        self.ledger.write_text(_lines([_row("t1", hyp="SECRET-TEXT", why="SECRET-TEXT")]),
                               encoding="utf-8")
        self._cfg()
        url = self._url("/hypothesis-signal")
        import urllib.request
        raw = urllib.request.urlopen(url, timeout=1).read().decode("utf-8")
        self.assertNotIn("SECRET-TEXT", raw)

    def test_신호가_missing이어도_풀스택_카드_응답은_성공한다(self):
        self._write_cfg([self.repo_root])
        cfg = json.loads(self.cfg_path.read_text(encoding="utf-8"))
        cfg["hypothesis_ledger"] = str(self.ledger)  # 파일 없음
        self.cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
        _, sig = self._get("/hypothesis-signal")
        self.assertEqual(sig, {"missing": "파일 없음"})
        status, body = self._get("/competency/fullstack")
        self.assertEqual(status, 200)
        self.assertIn("groups", body)
        self.assertEqual(set(body["groups"]), set(server._FULLSTACK_AREAS))
