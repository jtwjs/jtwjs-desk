"""GET /routine · POST /routine/answer · POST /routine/rollover (step 5).

엣지 5축: 빈 값(설정 없음 · 문항 0건) · 비정상 입력(토큰 · Origin · 깨진 JSON · choice 밖 값 · 없는 id) ·
실패 경로(질문함 파일 없음 · 깨진 줄) · 상태 전이(unanswered → answered, unanswered → skipped,
답한 문항은 건너뜀 안 됨) · 동시성(rollover와 answer를 스레드로 동시에 호출).
🔴 픽스처는 임시 폴더 안의 지어낸 문항이다.
"""
import json
import sys
import threading
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_desk_server_review import _ReviewCase
from desk import routine
from page import server

TODAY = date(2026, 3, 10)
YESTERDAY = "2026-03-09"


def _q(id_, d, kind="재시험", **extra):
    return {"id": id_, "date": d, "kind": kind, "text": f"샘플 문항 {id_}", **extra}


class 통합_routine(_ReviewCase):
    def setUp(self):
        super().setUp()
        p = patch.object(server, "_today", return_value=TODAY)
        p.start()
        self.addCleanup(p.stop)
        self.qpath = Path(self._tmp.name) / "mail" / "q.jsonl"
        self.apath = Path(self._tmp.name) / "mail" / "a.jsonl"
        self.qpath.parent.mkdir()

    def _cfg(self):
        self.cfg_path.write_text(json.dumps({
            "routine_questions": str(self.qpath),
            "routine_answers": str(self.apath)}), encoding="utf-8")

    def _write_q(self, rows, raw=""):
        self.qpath.write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows) + raw,
            encoding="utf-8")

    def _answer(self, payload, headers=None):
        return self._post("/routine/answer", payload,
                          headers if headers is not None else self._pick_headers())

    def _rollover(self, headers=None):
        return self._post("/routine/rollover", {},
                          headers if headers is not None else self._pick_headers())

    def _answers(self):
        return routine.parse_answers(self.apath.read_text(encoding="utf-8"))[0]


class 설정이_없을_때(통합_routine):
    def test_GET은_설정_없음_이유_행을_준다(self):
        status, body = self._get("/routine")
        self.assertEqual(status, 200)
        self.assertEqual(body["groups"], [])
        self.assertEqual(body["past"], [])
        self.assertEqual(body["broken"], 0)
        self.assertEqual(body["date"], "2026-03-10")
        self.assertEqual(body["missing"], [{"what": "질문함", "reason": "설정 없음"}])
        self.assertIn("source", body["config"])

    def test_rollover는_200_skipped_0이다(self):
        self.assertEqual(self._rollover(), (200, {"ok": True, "skipped": 0}))

    def test_answer는_400_routine_not_configured다(self):
        status, body = self._answer({"id": "a", "value": "x"})
        self.assertEqual((status, body), (400, {"error": "routine not configured"}))


class 질문함_파일이_없을_때(통합_routine):
    def test_GET은_파일_없음_이유_행을_준다(self):
        self._cfg()
        status, body = self._get("/routine")
        self.assertEqual(status, 200)
        self.assertEqual(body["missing"], [{"what": "질문함", "reason": "파일 없음"}])
        self.assertEqual(body["groups"], [])


class 질문함이_있을_때(통합_routine):
    def setUp(self):
        super().setUp()
        self._write_q([
            _q("t1", "2026-03-10", "재시험"),
            _q("t2", "2026-03-10", "복습"),
            _q("t3", "2026-03-10", "설명"),
            _q("t4", "2026-03-10", "새종류"),
            _q("t5", "2026-03-10", "결정", options=[{"key": "a", "label": "가"}, {"key": "b", "label": "나"}]),
            _q("p1", YESTERDAY),
            _q("p2", YESTERDAY),
            _q("f1", "2026-03-11"),
        ], raw="깨진 줄\n")
        self._cfg()

    def test_GET은_오늘을_종류별로_묶고_input_options_state를_준다(self):
        status, body = self._get("/routine")
        self.assertEqual(status, 200)
        self.assertEqual(body["missing"], [])
        self.assertEqual([g["kind"] for g in body["groups"]], ["재시험", "복습", "설명", "새종류", "결정"])
        items = {i["id"]: i for g in body["groups"] for i in g["items"]}
        self.assertEqual(items["t1"]["input"], "line")
        self.assertEqual(items["t2"]["input"], "choice")
        self.assertEqual(items["t2"]["options"], routine.REVIEW_DEFAULT_OPTIONS)
        self.assertEqual(items["t3"]["input"], "long")
        self.assertEqual(items["t4"]["input"], "line")
        self.assertEqual(items["t5"]["input"], "choice")
        self.assertEqual(items["t1"]["state"], "unanswered")
        for key in ("id", "date", "kind", "text", "input", "options", "state", "value", "note"):
            self.assertIn(key, items["t1"])

    def test_GET은_지난_미답_문항을_past에_주고_미래는_안_준다(self):
        _, body = self._get("/routine")
        self.assertEqual({i["id"] for i in body["past"]}, {"p1", "p2"})
        everything = {i["id"] for g in body["groups"] for i in g["items"]} | {i["id"] for i in body["past"]}
        self.assertNotIn("f1", everything)

    def test_GET은_깨진_줄_수를_준다(self):
        _, body = self._get("/routine")
        self.assertEqual(body["broken"], 1)

    def test_GET을_여러_번_불러도_답함_파일은_안_바뀐다(self):
        self.assertEqual(self._answer({"id": "t1", "value": "내 답"})[0], 200)
        before = self.apath.read_bytes()
        for _ in range(3):
            self._get("/routine")
        self.assertEqual(self.apath.read_bytes(), before)

    def test_GET은_Host가_다르면_403이다(self):
        self.assertEqual(self._get_raw_host("/routine", "evil.example:80")[0], 403)

    def test_질문함이_빈_파일이면_문항_0건이고_이유_행이_없다(self):
        self.qpath.write_text("", encoding="utf-8")
        _, body = self._get("/routine")
        self.assertEqual((body["groups"], body["past"], body["missing"]), ([], [], []))


class 답을_저장할_때(통합_routine):
    def setUp(self):
        super().setUp()
        self._write_q([_q("t1", "2026-03-10"),
                       _q("t2", "2026-03-10", "복습")])
        self._cfg()

    def test_정상이면_200과_답함에_한_줄이_생긴다(self):
        self.assertEqual(self._answer({"id": "t1", "value": "내 답", "note": "메모"}), (200, {"ok": True}))
        lines = self.apath.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        row = json.loads(lines[0])
        self.assertEqual((row["id"], row["status"], row["value"], row["note"]),
                         ("t1", "answered", "내 답", "메모"))
        self.assertIsInstance(row["at"], str)

    def test_토큰이_없으면_403이고_안_쓴다(self):
        h = self._pick_headers()
        del h["X-Desk-Token"]
        self.assertEqual(self._answer({"id": "t1", "value": "x"}, h)[0], 403)
        self.assertFalse(self.apath.exists())

    def test_Origin이_다르면_403이다(self):
        h = self._pick_headers(Origin="http://evil.example")
        self.assertEqual(self._answer({"id": "t1", "value": "x"}, h)[0], 403)
        self.assertFalse(self.apath.exists())

    def test_깨진_JSON이면_400_bad_json이다(self):
        import urllib.error
        import urllib.request
        req = urllib.request.Request(self._url("/routine/answer"), data="{깨짐".encode("utf-8"), method="POST",
                                     headers=self._pick_headers())
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req, timeout=1)
        self.assertEqual(cm.exception.code, 400)
        self.assertEqual(json.loads(cm.exception.read().decode("utf-8")), {"error": "bad json"})

    def test_choice_밖_값이면_400_violations다(self):
        status, body = self._answer({"id": "t2", "value": "엉뚱"})
        self.assertEqual(status, 400)
        self.assertEqual(body, {"violations": ["value"]})
        self.assertFalse(self.apath.exists())

    def test_빈_값이면_400이다(self):
        status, body = self._answer({"id": "t1", "value": ""})
        self.assertEqual(status, 400)
        self.assertIn("value", body["violations"])

    def test_없는_id면_404다(self):
        self.assertEqual(self._answer({"id": "없음", "value": "x"}),
                         (404, {"error": "question not found"}))

    def test_답을_고쳐_쓰면_GET의_value가_마지막_값이다(self):
        self._answer({"id": "t1", "value": "첫 답"})
        self._answer({"id": "t1", "value": "고친 답"})
        _, body = self._get("/routine")
        item = next(i for g in body["groups"] for i in g["items"] if i["id"] == "t1")
        self.assertEqual((item["state"], item["value"]), ("answered", "고친 답"))


class 날이_바뀌어_건너뜀을_찍을_때(통합_routine):
    def setUp(self):
        super().setUp()
        self._write_q([_q("p1", YESTERDAY), _q("p2", YESTERDAY), _q("t1", "2026-03-10")])
        self._cfg()

    def test_지난_미답을_skipped로_바꾸고_두_번째는_0이다(self):
        self.assertEqual(self._rollover(), (200, {"ok": True, "skipped": 2}))
        _, body = self._get("/routine")
        self.assertEqual({(i["id"], i["state"]) for i in body["past"]},
                         {("p1", "skipped"), ("p2", "skipped")})
        self.assertEqual(self._rollover(), (200, {"ok": True, "skipped": 0}))

    def test_오늘_문항에는_건너뜀을_안_찍는다(self):
        self._rollover()
        self.assertNotIn("t1", self._answers())

    def test_답한_문항에는_건너뜀을_안_찍는다(self):
        self._answer({"id": "p1", "value": "늦게 답함"})
        self.assertEqual(self._rollover(), (200, {"ok": True, "skipped": 1}))
        self.assertEqual(self._answers()["p1"]["status"], "answered")

    def test_건너뜀_뒤에도_지난_문항에_답할_수_있다(self):
        self._rollover()
        self.assertEqual(self._answer({"id": "p1", "value": "뒤늦은 답"})[0], 200)
        self.assertEqual(self._answers()["p1"]["status"], "answered")

    def test_토큰이_없으면_403이고_안_쓴다(self):
        h = self._pick_headers()
        del h["X-Desk-Token"]
        self.assertEqual(self._rollover(h)[0], 403)
        self.assertFalse(self.apath.exists())

    def test_rollover와_answer를_동시에_불러도_답한_문항은_answered로_남는다(self):
        for n in range(8):
            qid = f"race{n}"
            with self.qpath.open("a", encoding="utf-8") as f:
                f.write(json.dumps(_q(qid, YESTERDAY), ensure_ascii=False) + "\n")
            results = {}
            start = threading.Barrier(2)

            def do_answer():
                start.wait()
                results["a"] = self._answer({"id": qid, "value": "동시 답"})

            def do_rollover():
                start.wait()
                results["r"] = self._rollover()

            ts = [threading.Thread(target=do_answer), threading.Thread(target=do_rollover)]
            for t in ts:
                t.start()
            for t in ts:
                t.join()
            self.assertEqual(results["a"][0], 200)
            self.assertEqual(results["r"][0], 200)
            self.assertEqual(self._answers()[qid]["status"], "answered", qid)
