"""GET /nav-counts 의 routine 항목 — 오늘 미답 수 + 항목별 격리(errors 객체, 오류 없으면 빈 객체).

엣지 5축: 빈 값(설정 없음 · 질문함 없음 → 0) · 비정상 입력(깨진 질문함 줄) ·
실패 경로(항목 하나가 예외 → 그 항목만 None + errors) · 상태 전이(답하면 줄어듦) ·
동시성(해당 없음 — 읽기 전용).
🔴 픽스처는 임시 폴더 안의 지어낸 문항이다.
"""
import json
import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_desk_server_review import _ReviewCase
from page import server

TODAY = date(2026, 3, 10)


def _q(id_, d, kind="재시험"):
    return {"id": id_, "date": d, "kind": kind, "text": f"샘플 문항 {id_}"}


class 통합_nav_counts_routine(_ReviewCase):
    def setUp(self):
        super().setUp()
        p = patch.object(server, "_today", return_value=TODAY)
        p.start()
        self.addCleanup(p.stop)
        self.qpath = Path(self._tmp.name) / "mail" / "q.jsonl"
        self.apath = Path(self._tmp.name) / "mail" / "a.jsonl"
        self.qpath.parent.mkdir()

    def _cfg(self, **extra):
        self.cfg_path.write_text(json.dumps({
            "routine_questions": str(self.qpath),
            "routine_answers": str(self.apath), **extra}), encoding="utf-8")

    def _write_q(self, rows, raw=""):
        self.qpath.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows) + raw,
                              encoding="utf-8")

    def test_설정이_없으면_routine은_0이고_errors는_빈_객체다(self):
        _, body = self._get("/nav-counts")
        self.assertEqual(body["routine"], 0)
        self.assertEqual(body["errors"], {})

    def test_질문함_파일이_없으면_0이다(self):
        self._cfg()
        _, body = self._get("/nav-counts")
        self.assertEqual(body["routine"], 0)
        self.assertEqual(body["errors"], {})

    def test_오늘_미답만_센다_건너뜀_답함_지난_미래는_뺀다(self):
        self._write_q([_q("a", "2026-03-10"), _q("b", "2026-03-10"), _q("c", "2026-03-10"),
                       _q("d", "2026-03-09"), _q("e", "2026-03-11")])
        self.apath.write_text(
            json.dumps({"id": "b", "status": "skipped", "at": "t"}) + "\n"
            + json.dumps({"id": "c", "status": "answered", "value": "x", "at": "t"}) + "\n",
            encoding="utf-8")
        self._cfg()
        _, body = self._get("/nav-counts")
        self.assertEqual(body["routine"], 1)

    def test_답하면_줄어든다(self):
        self._write_q([_q("a", "2026-03-10"), _q("b", "2026-03-10")])
        self._cfg()
        _, before = self._get("/nav-counts")
        self.apath.write_text(
            json.dumps({"id": "a", "status": "answered", "value": "x", "at": "t"}) + "\n",
            encoding="utf-8")
        _, after = self._get("/nav-counts")
        self.assertEqual((before["routine"], after["routine"]), (2, 1))

    def test_깨진_줄이_섞여도_나머지는_세고_다른_배지는_그대로다(self):
        self._write_q([_q("a", "2026-03-10")], raw="{깨짐\n")
        self._cfg()
        status, body = self._get("/nav-counts")
        self.assertEqual(status, 200)
        self.assertEqual((body["judge"], body["review"], body["routine"]), (0, 0, 1))

    def test_routine이_예외를_내면_routine만_None이고_이유는_예외_이름뿐이다(self):
        self._write_q([_q("a", "2026-03-10")])
        self._cfg()
        self._write_ask("repo-a", "ask-1")
        with patch("desk.routine.unanswered_today_count", side_effect=ValueError("/비밀/경로")):
            status, body = self._get("/nav-counts")
        self.assertEqual(status, 200)
        self.assertEqual(body["judge"], 1)
        self.assertIsNone(body["routine"])
        self.assertEqual(body["errors"], {"routine": "ValueError"})

    def test_judge를_읽다_예외가_나도_review와_routine은_나온다(self):
        self._write_q([_q("a", "2026-03-10")])
        self._cfg(repos=[str(self.repo_root)])
        with patch.object(server, "list_judgments", side_effect=OSError("x")):
            status, body = self._get("/nav-counts")
        self.assertEqual(status, 200)
        self.assertIsNone(body["judge"])
        self.assertEqual(body["errors"], {"judge": "OSError"})
        self.assertGreater(body["review"], 0)
        self.assertEqual(body["routine"], 1)
