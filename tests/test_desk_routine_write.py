"""desk/routine.py — 답함 쓰기 껍질(save_answer · rollover · append_answer) (step 3). 픽스처는 지어낸 문항이다."""
import json
import tempfile
import threading
import unittest
from datetime import date, datetime
from pathlib import Path

from desk import routine

TODAY = date(2026, 11, 12)
NOW = datetime(2026, 11, 12, 21, 0, 0)


def q(id_, d="2026-11-12", kind="재시험", text="샘플 문항 A", **extra):
    return {"id": id_, "date": d, "kind": kind, "text": text, **extra}


def write_lines(path: Path, *rows):
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                    encoding="utf-8")


def read_rows(path: Path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.qp = self.dir / "questions.jsonl"
        self.ap = self.dir / "answers.jsonl"


class TestReadTextOrNone(Base):
    def test_파일이_없으면_None이다(self):
        self.assertIsNone(routine.read_text_or_none(self.dir / "없음.jsonl"))

    def test_None_경로면_None이다(self):
        self.assertIsNone(routine.read_text_or_none(None))

    def test_디렉터리처럼_못_읽는_경로도_예외_없이_None이다(self):
        self.assertIsNone(routine.read_text_or_none(self.dir))

    def test_빈_파일은_빈_문자열이다(self):
        self.ap.write_text("", encoding="utf-8")
        self.assertEqual(routine.read_text_or_none(self.ap), "")

    def test_있는_파일은_내용을_돌려준다(self):
        self.ap.write_text("가나다\n", encoding="utf-8")
        self.assertEqual(routine.read_text_or_none(self.ap), "가나다\n")


class TestAppendAnswer(Base):
    def test_한_줄을_한글_그대로_덧붙인다(self):
        routine.append_answer(self.ap, {"id": "a", "value": "한글"})
        self.assertEqual(self.ap.read_text(encoding="utf-8"), '{"id": "a", "value": "한글"}\n')

    def test_디렉터리가_없으면_만든다(self):
        path = self.dir / "새폴더" / "하위" / "answers.jsonl"
        routine.append_answer(path, {"id": "a"})
        self.assertEqual(read_rows(path), [{"id": "a"}])

    def test_파일_끝에_개행이_없으면_개행부터_쓴다(self):
        self.ap.write_text('{"id": "x", "status": "skipped", "at": "t"}', encoding="utf-8")
        routine.append_answer(self.ap, {"id": "b"})
        lines = self.ap.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[1]), {"id": "b"})

    def test_빈_파일에는_앞_개행_없이_쓴다(self):
        self.ap.write_text("", encoding="utf-8")
        routine.append_answer(self.ap, {"id": "a"})
        self.assertEqual(self.ap.read_text(encoding="utf-8"), '{"id": "a"}\n')


class TestSaveAnswer(Base):
    def test_검증을_통과하면_한_줄을_덧붙이고_빈_리스트를_돌려준다(self):
        write_lines(self.qp, q("a"))
        bad = routine.save_answer(self.qp, self.ap, {"id": "a", "value": "내 답"}, NOW)
        self.assertEqual(bad, [])
        self.assertEqual(read_rows(self.ap),
                         [{"id": "a", "status": "answered", "value": "내 답",
                           "at": NOW.isoformat()}])

    def test_note가_있을_때만_줄에_들어간다(self):
        write_lines(self.qp, q("a"))
        routine.save_answer(self.qp, self.ap, {"id": "a", "value": "답", "note": "이유"}, NOW)
        self.assertEqual(read_rows(self.ap)[0]["note"], "이유")

    def test_위반이_있으면_쓰지_않고_위반_목록을_돌려준다(self):
        write_lines(self.qp, q("a"))
        write_lines(self.ap, {"id": "z", "status": "skipped", "at": "t"})
        before = self.ap.read_text(encoding="utf-8")
        bad = routine.save_answer(self.qp, self.ap, {"id": "a", "value": "  "}, NOW)
        self.assertEqual(bad, ["value"])
        self.assertEqual(self.ap.read_text(encoding="utf-8"), before)

    def test_위반이_있으면_답함_파일을_만들지_않는다(self):
        write_lines(self.qp, q("a"))
        routine.save_answer(self.qp, self.ap, {"id": "a", "value": ""}, NOW)
        self.assertFalse(self.ap.exists())

    def test_질문함에_없는_id는_위반이다(self):
        write_lines(self.qp, q("a"))
        bad = routine.save_answer(self.qp, self.ap, {"id": "없는", "value": "답"}, NOW)
        self.assertEqual(bad, ["id"])
        self.assertFalse(self.ap.exists())

    def test_질문함_파일이_없으면_id_위반이다(self):
        bad = routine.save_answer(self.qp, self.ap, {"id": "a", "value": "답"}, NOW)
        self.assertEqual(bad, ["id"])
        self.assertFalse(self.ap.exists())

    def test_body가_dict가_아니면_예외_없이_위반이다(self):
        write_lines(self.qp, q("a"))
        self.assertTrue(routine.save_answer(self.qp, self.ap, "문자열", NOW))
        self.assertTrue(routine.save_answer(self.qp, self.ap, None, NOW))
        self.assertFalse(self.ap.exists())

    def test_빈_질문함_파일이면_id_위반이다(self):
        self.qp.write_text("", encoding="utf-8")
        bad = routine.save_answer(self.qp, self.ap, {"id": "a", "value": "답"}, NOW)
        self.assertEqual(bad, ["id"])

    def test_choice_입력은_선택지_key만_받는다(self):
        write_lines(self.qp, q("a", kind="복습"))
        self.assertEqual(routine.save_answer(self.qp, self.ap, {"id": "a", "value": "몰라"}, NOW),
                         ["value"])
        self.assertEqual(routine.save_answer(self.qp, self.ap, {"id": "a", "value": "known"}, NOW),
                         [])
        self.assertEqual(read_rows(self.ap)[-1]["value"], "known")

    def test_답을_고쳐_다시_저장하면_줄이_하나_늘고_마지막_줄이_이긴다(self):
        write_lines(self.qp, q("a"))
        routine.save_answer(self.qp, self.ap, {"id": "a", "value": "옛 답"}, NOW)
        routine.save_answer(self.qp, self.ap, {"id": "a", "value": "새 답"}, NOW)
        rows = read_rows(self.ap)
        self.assertEqual(len(rows), 2)
        answers, broken = routine.parse_answers(self.ap.read_text(encoding="utf-8"))
        self.assertEqual(answers["a"]["value"], "새 답")
        self.assertEqual(broken, 0)

    def test_상태_전이_unanswered에서_skipped_뒤_답하면_answered가_이긴다(self):
        write_lines(self.qp, q("a", d="2026-11-10"))
        self.assertEqual(routine.rollover(self.qp, self.ap, TODAY, NOW), 1)
        routine.save_answer(self.qp, self.ap, {"id": "a", "value": "늦은 답"}, NOW)
        answers, _ = routine.parse_answers(self.ap.read_text(encoding="utf-8"))
        self.assertEqual(answers["a"]["status"], "answered")

    def test_질문함은_절대_바꾸지_않는다(self):
        write_lines(self.qp, q("a", d="2026-11-10"))
        before = self.qp.read_text(encoding="utf-8")
        routine.save_answer(self.qp, self.ap, {"id": "a", "value": "답"}, NOW)
        routine.rollover(self.qp, self.ap, TODAY, NOW)
        self.assertEqual(self.qp.read_text(encoding="utf-8"), before)


class TestRollover(Base):
    def test_지난_답_없는_문항에만_건너뜀을_찍는다(self):
        write_lines(self.qp,
                    q("past", d="2026-11-10"),
                    q("today", d="2026-11-12"),
                    q("future", d="2026-11-13"),
                    q("answered", d="2026-11-09"),
                    q("skipped", d="2026-11-08"))
        write_lines(self.ap,
                    {"id": "answered", "status": "answered", "value": "v", "at": "t"},
                    {"id": "skipped", "status": "skipped", "at": "t"})
        n = routine.rollover(self.qp, self.ap, TODAY, NOW)
        self.assertEqual(n, 1)
        rows = read_rows(self.ap)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[-1], {"id": "past", "status": "skipped", "at": NOW.isoformat()})

    def test_두_번_부르면_두_번째는_0줄이고_파일이_그대로다(self):
        write_lines(self.qp, q("a", d="2026-11-10"), q("b", d="2026-11-11"))
        self.assertEqual(routine.rollover(self.qp, self.ap, TODAY, NOW), 2)
        before = self.ap.read_text(encoding="utf-8")
        self.assertEqual(routine.rollover(self.qp, self.ap, TODAY, NOW), 0)
        self.assertEqual(self.ap.read_text(encoding="utf-8"), before)

    def test_질문함이_없으면_0이고_답함을_만들지_않는다(self):
        self.assertEqual(routine.rollover(self.qp, self.ap, TODAY, NOW), 0)
        self.assertFalse(self.ap.exists())

    def test_빈_질문함이면_0이다(self):
        self.qp.write_text("", encoding="utf-8")
        self.assertEqual(routine.rollover(self.qp, self.ap, TODAY, NOW), 0)

    def test_답함_파일이_없으면_만든다(self):
        write_lines(self.qp, q("a", d="2026-11-10"))
        self.assertEqual(routine.rollover(self.qp, self.ap, TODAY, NOW), 1)
        self.assertTrue(self.ap.exists())

    def test_답함_디렉터리가_없어도_만들어_쓴다(self):
        write_lines(self.qp, q("a", d="2026-11-10"))
        path = self.dir / "없던" / "answers.jsonl"
        self.assertEqual(routine.rollover(self.qp, path, TODAY, NOW), 1)
        self.assertEqual(len(read_rows(path)), 1)

    def test_오늘과_미래만_있으면_0이다(self):
        write_lines(self.qp, q("t", d="2026-11-12"), q("f", d="2026-12-01"))
        self.assertEqual(routine.rollover(self.qp, self.ap, TODAY, NOW), 0)

    def test_깨진_질문_줄은_건너뛰고_나머지에_찍는다(self):
        self.qp.write_text("{깨짐\n" + json.dumps(q("a", d="2026-11-10"), ensure_ascii=False) + "\n",
                           encoding="utf-8")
        self.assertEqual(routine.rollover(self.qp, self.ap, TODAY, NOW), 1)

    def test_답함_끝에_개행이_없어도_줄이_붙지_않는다(self):
        write_lines(self.qp, q("a", d="2026-11-10"))
        self.ap.write_text('{"id": "x", "status": "skipped", "at": "t"}', encoding="utf-8")
        routine.rollover(self.qp, self.ap, TODAY, NOW)
        lines = self.ap.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[1])["id"], "a")

    def test_답함이_깨진_줄만_있어도_예외_없이_찍는다(self):
        write_lines(self.qp, q("a", d="2026-11-10"))
        self.ap.write_text("{깨짐\n", encoding="utf-8")
        self.assertEqual(routine.rollover(self.qp, self.ap, TODAY, NOW), 1)


class TestConcurrency(Base):
    def test_save_answer와_rollover가_동시에_돌아도_답한_문항에_건너뜀이_마지막_줄로_남지_않는다(self):
        n = 40
        ids = [f"q{i}" for i in range(n)]
        write_lines(self.qp, *[q(i, d="2026-11-10") for i in ids])
        barrier = threading.Barrier(n + 8)
        errors = []

        def answer(qid):
            try:
                barrier.wait()
                self.assertEqual(
                    routine.save_answer(self.qp, self.ap, {"id": qid, "value": "답"}, NOW), [])
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        def roll():
            try:
                barrier.wait()
                routine.rollover(self.qp, self.ap, TODAY, NOW)
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        threads = [threading.Thread(target=answer, args=(i,)) for i in ids]
        threads += [threading.Thread(target=roll) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])

        answers, broken = routine.parse_answers(self.ap.read_text(encoding="utf-8"))
        self.assertEqual(broken, 0)
        wrongly_skipped = [i for i in ids if answers[i]["status"] != "answered"]
        self.assertEqual(len(wrongly_skipped), 0)
        # 줄이 섞이거나 잘리지 않았다: 전부 한 줄씩 온전히 읽힌다
        self.assertEqual(sorted(answers), sorted(ids))


if __name__ == "__main__":
    unittest.main()
