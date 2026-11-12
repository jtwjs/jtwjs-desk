"""desk/routine.py — 우편함(질문함·답함) 파싱·판정 순수 함수 (step 1). 픽스처는 지어낸 문항이다."""
import json
import unittest
from datetime import date

from desk import routine

TODAY = date(2026, 11, 12)


def q(id_, d="2026-11-12", kind="재시험", text="샘플 문항", **extra):
    return {"id": id_, "date": d, "kind": kind, "text": text, **extra}


def a(id_, status="answered", value="샘플 답", **extra):
    row = {"id": id_, "status": status, "at": "2026-11-12T21:00:00", **extra}
    if status == "answered":
        row["value"] = value
    return row


def jl(*rows):
    return "\n".join(r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)
                     for r in rows)


class TestParseQuestions(unittest.TestCase):
    def test_빈_텍스트면_빈_결과와_0이다(self):
        self.assertEqual(routine.parse_questions(""), ({}, 0))

    def test_빈_줄은_깨진_줄이_아니라_무시한다(self):
        text = "\n" + jl(q("a")) + "\n\n   \n" + jl(q("b")) + "\n"
        got, broken = routine.parse_questions(text)
        self.assertEqual(sorted(got), ["a", "b"])
        self.assertEqual(broken, 0)

    def test_같은_id가_여러_줄이면_마지막_줄이_이긴다(self):
        got, broken = routine.parse_questions(jl(q("a", text="옛"), q("a", text="새")))
        self.assertEqual(got["a"]["text"], "새")
        self.assertEqual(broken, 0)

    def test_JSON이_아닌_줄과_객체가_아닌_줄은_깨진_줄로_센다(self):
        got, broken = routine.parse_questions(jl(q("a"), "{깨짐", "[1, 2]", '"문자열"'))
        self.assertEqual(list(got), ["a"])
        self.assertEqual(broken, 3)

    def test_필수_필드가_없거나_형식이_틀리면_깨진_줄이다(self):
        rows = [
            {"date": "2026-11-12", "kind": "복습", "text": "x"},
            {"id": "a", "kind": "복습", "text": "x"},
            {"id": "a", "date": "2026-11-12", "text": "x"},
            {"id": "a", "date": "2026-11-12", "kind": "복습"},
            q("", ),
            q("a", d="2026/11/12"),
            q("a", d="2026-13-40"),
            q("a", kind=""),
            q("a", text=""),
            q("a", text=5),
        ]
        got, broken = routine.parse_questions(jl(*rows))
        self.assertEqual(got, {})
        self.assertEqual(broken, len(rows))

    def test_options_형식이_틀리면_깨진_줄이다(self):
        rows = [
            q("a", options=[]),
            q("b", options="가나"),
            q("c", options=[{"key": "k"}]),
            q("d", options=[{"key": "", "label": "L"}]),
            q("e", options=["x"]),
        ]
        got, broken = routine.parse_questions(jl(*rows))
        self.assertEqual(got, {})
        self.assertEqual(broken, 5)

    def test_올바른_options는_그대로_보존한다(self):
        opts = [{"key": "k1", "label": "하나"}, {"key": "k2", "label": "둘"}]
        got, _ = routine.parse_questions(jl(q("a", options=opts)))
        self.assertEqual(got["a"]["options"], opts)

    def test_깨진_줄이_같은_id의_앞_줄을_지우지_않는다(self):
        got, broken = routine.parse_questions(
            jl(q("a", text="멀쩡"), {"id": "a", "date": "나쁨", "kind": "복습", "text": "x"}))
        self.assertEqual(got["a"]["text"], "멀쩡")
        self.assertEqual(broken, 1)


class TestParseAnswers(unittest.TestCase):
    def test_빈_텍스트면_빈_결과와_0이다(self):
        self.assertEqual(routine.parse_answers(""), ({}, 0))

    def test_같은_id가_여러_줄이면_마지막_줄이_이긴다(self):
        got, broken = routine.parse_answers(jl(a("a", value="옛"), a("a", value="새")))
        self.assertEqual(got["a"]["value"], "새")
        self.assertEqual(broken, 0)

    def test_건너뜀_줄은_value_없이도_정상이다(self):
        got, broken = routine.parse_answers(jl(a("a", status="skipped")))
        self.assertEqual(got["a"]["status"], "skipped")
        self.assertEqual(broken, 0)

    def test_깨진_답_줄은_건너뛰고_개수만_센다(self):
        rows = [
            a("ok"),
            "{깨짐",
            "[1]",
            {"status": "answered", "value": "x", "at": "t"},
            {"id": "b", "status": "done", "value": "x", "at": "t"},
            {"id": "c", "status": "answered", "value": "", "at": "t"},
            {"id": "d", "status": "answered", "at": "t"},
        ]
        got, broken = routine.parse_answers(jl(*rows))
        self.assertEqual(list(got), ["ok"])
        self.assertEqual(broken, 6)

    def test_빈_줄은_무시한다(self):
        got, broken = routine.parse_answers("\n\n" + jl(a("a")) + "\n  \n")
        self.assertEqual(list(got), ["a"])
        self.assertEqual(broken, 0)

    def test_깨진_줄이_앞의_답을_지우지_않는다(self):
        got, broken = routine.parse_answers(
            jl(a("a", value="멀쩡"), {"id": "a", "status": "answered", "value": "", "at": "t"}))
        self.assertEqual(got["a"]["value"], "멀쩡")
        self.assertEqual(broken, 1)


class TestInputShape(unittest.TestCase):
    OPTS = [{"key": "k1", "label": "하나"}]

    def test_options가_있으면_choice이고_그_options를_쓴다(self):
        item = q("a", kind="재시험", options=self.OPTS)
        self.assertEqual(routine.input_shape(item), "choice")
        self.assertEqual(routine.effective_options(item), self.OPTS)

    def test_복습은_choice이고_기본_선택지를_채운다(self):
        item = q("a", kind="복습")
        self.assertEqual(routine.input_shape(item), "choice")
        self.assertEqual(routine.effective_options(item), routine.REVIEW_DEFAULT_OPTIONS)
        self.assertEqual([o["key"] for o in routine.REVIEW_DEFAULT_OPTIONS],
                         ["known", "unsure"])

    def test_복습에_options가_오면_그것이_이긴다(self):
        item = q("a", kind="복습", options=self.OPTS)
        self.assertEqual(routine.input_shape(item), "choice")
        self.assertEqual(routine.effective_options(item), self.OPTS)

    def test_설명은_long이고_선택지가_없다(self):
        item = q("a", kind="설명")
        self.assertEqual(routine.input_shape(item), "long")
        self.assertIsNone(routine.effective_options(item))

    def test_재시험은_line이다(self):
        item = q("a", kind="재시험")
        self.assertEqual(routine.input_shape(item), "line")
        self.assertIsNone(routine.effective_options(item))

    def test_모르는_종류도_에러가_아니라_line이다(self):
        item = q("a", kind="새종류")
        self.assertEqual(routine.input_shape(item), "line")
        self.assertIsNone(routine.effective_options(item))


class TestQuestionState(unittest.TestCase):
    def test_답_줄이_없으면_unanswered다(self):
        self.assertEqual(routine.question_state(q("a"), {}), "unanswered")

    def test_답이_늘면_상태가_바뀐다(self):
        item = q("a")
        self.assertEqual(routine.question_state(item, {}), "unanswered")
        skipped, _ = routine.parse_answers(jl(a("a", status="skipped")))
        self.assertEqual(routine.question_state(item, skipped), "skipped")
        later, _ = routine.parse_answers(jl(a("a", status="skipped"), a("a")))
        self.assertEqual(routine.question_state(item, later), "answered")


class TestValidateAnswer(unittest.TestCase):
    def test_없는_문항이면_id를_돌려준다(self):
        self.assertEqual(routine.validate_answer(None, {"id": "x", "status": "answered",
                                                        "value": "v"}), ["id"])

    def test_정상_답은_빈_목록이다(self):
        self.assertEqual(routine.validate_answer(
            q("a"), {"id": "a", "status": "answered", "value": "답"}), [])

    def test_빈_value는_value를_돌려준다(self):
        for v in ("", "   ", None, 3):
            self.assertEqual(routine.validate_answer(
                q("a"), {"id": "a", "status": "answered", "value": v}), ["value"])

    def test_상한_초과는_value를_돌려준다(self):
        over = "가" * (routine.ANSWER_MAX_CHARS + 1)
        self.assertEqual(routine.validate_answer(
            q("a"), {"id": "a", "status": "answered", "value": over}), ["value"])
        edge = "가" * routine.ANSWER_MAX_CHARS
        self.assertEqual(routine.validate_answer(
            q("a"), {"id": "a", "status": "answered", "value": edge}), [])

    def test_note가_문자열이_아니거나_상한을_넘으면_note를_돌려준다(self):
        base = {"id": "a", "status": "answered", "value": "v"}
        self.assertEqual(routine.validate_answer(q("a"), {**base, "note": 5}), ["note"])
        self.assertEqual(routine.validate_answer(
            q("a"), {**base, "note": "가" * (routine.ANSWER_MAX_CHARS + 1)}), ["note"])
        self.assertEqual(routine.validate_answer(q("a"), {**base, "note": "이유"}), [])

    def test_choice_밖_value는_value를_돌려준다(self):
        item = q("a", options=[{"key": "k1", "label": "하나"}])
        self.assertEqual(routine.validate_answer(
            item, {"id": "a", "status": "answered", "value": "zz"}), ["value"])
        self.assertEqual(routine.validate_answer(
            item, {"id": "a", "status": "answered", "value": "k1"}), [])

    def test_복습은_기본_선택지_key만_받는다(self):
        item = q("a", kind="복습")
        self.assertEqual(routine.validate_answer(
            item, {"id": "a", "status": "answered", "value": "known"}), [])
        self.assertEqual(routine.validate_answer(
            item, {"id": "a", "status": "answered", "value": "맞음"}), ["value"])

    def test_body가_dict가_아니어도_예외를_던지지_않는다(self):
        self.assertEqual(routine.validate_answer(q("a"), "문자열"), ["value"])
        self.assertEqual(routine.validate_answer(None, None), ["id"])


class TestSplitByDate(unittest.TestCase):
    def setUp(self):
        self.questions = {
            "t1": q("t1", "2026-11-12", "설명"),
            "t2": q("t2", "2026-11-12", "복습"),
            "p_skip": q("p_skip", "2026-11-10"),
            "p_none": q("p_none", "2026-11-11"),
            "p_done": q("p_done", "2026-11-09"),
            "future": q("future", "2026-11-13"),
        }
        self.answers, _ = routine.parse_answers(jl(
            a("t2", value="known", note="이유"),
            a("p_skip", status="skipped"),
            a("p_done", value="끝"),
        ))
        self.got = routine.split_by_date(self.questions, self.answers, TODAY)

    def ids(self, key):
        return [i["id"] for i in self.got[key]]

    def test_today는_오늘_문항_전부이고_답한_것도_포함한다(self):
        self.assertEqual(sorted(self.ids("today")), ["t1", "t2"])

    def test_past는_건너뜀과_답_없는_문항만_담고_답한_것은_뺀다(self):
        self.assertEqual(sorted(self.ids("past")), ["p_none", "p_skip"])

    def test_미래_날짜는_어디에도_없다(self):
        self.assertNotIn("future", self.ids("today") + self.ids("past"))

    def test_각_문항에_input_options_state_value_note가_합쳐진다(self):
        t2 = next(i for i in self.got["today"] if i["id"] == "t2")
        self.assertEqual(t2["input"], "choice")
        self.assertEqual(t2["options"], routine.REVIEW_DEFAULT_OPTIONS)
        self.assertEqual(t2["state"], "answered")
        self.assertEqual(t2["value"], "known")
        self.assertEqual(t2["note"], "이유")
        t1 = next(i for i in self.got["today"] if i["id"] == "t1")
        self.assertEqual((t1["input"], t1["options"], t1["state"]),
                         ("long", None, "unanswered"))
        self.assertEqual(t1["text"], "샘플 문항")

    def test_빈_입력이면_둘_다_빈_목록이다(self):
        self.assertEqual(routine.split_by_date({}, {}, TODAY), {"today": [], "past": []})


class TestGroupByKind(unittest.TestCase):
    def test_종류는_처음_나온_순서이고_항목_순서를_유지한다(self):
        items = [{"id": 1, "kind": "복습"}, {"id": 2, "kind": "설명"},
                 {"id": 3, "kind": "복습"}, {"id": 4, "kind": "새종류"}]
        self.assertEqual(routine.group_by_kind(items), [
            {"kind": "복습", "items": [items[0], items[2]]},
            {"kind": "설명", "items": [items[1]]},
            {"kind": "새종류", "items": [items[3]]},
        ])

    def test_빈_목록이면_빈_목록이다(self):
        self.assertEqual(routine.group_by_kind([]), [])


class TestUnansweredTodayCount(unittest.TestCase):
    def test_건너뜀과_답한_것과_지난_것과_미래는_세지_않는다(self):
        questions = {
            "u1": q("u1"), "u2": q("u2", kind="복습"),
            "sk": q("sk"), "an": q("an"),
            "old": q("old", "2026-11-10"), "fut": q("fut", "2026-11-13"),
        }
        answers, _ = routine.parse_answers(jl(a("sk", status="skipped"), a("an")))
        self.assertEqual(routine.unanswered_today_count(questions, answers, TODAY), 2)

    def test_빈_입력이면_0이다(self):
        self.assertEqual(routine.unanswered_today_count({}, {}, TODAY), 0)


if __name__ == "__main__":
    unittest.main()
