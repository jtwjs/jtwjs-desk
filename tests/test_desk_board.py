"""desk/board.py 순수 함수 테스트. 픽스처는 전부 지어낸 카드·링크(example.com)다.

엣지 5축: 빈 값(빈 제목·빈 이름·step 0개) · 비정상 입력(문자열 아님 · 경계 40/41, 2000/2001)
 · 실패 경로(거절 예외) · 상태 전이(열 이동 표) · 동시성(해당 없음: 순수 함수)
"""
import unittest
from datetime import date, datetime

from desk import board

TODAY = date(2026, 11, 14)


def ts(y, m, d, h=12):
    return datetime(y, m, d, h).timestamp()


def doing_card(**extra):
    card = {"column": "doing", "task": "sample-task", "pr_at": None}
    card.update(extra)
    return card


class 카드_제목을_검사할_때(unittest.TestCase):
    def test_앞뒤_공백은_떼어_돌려준다(self):
        self.assertEqual(board.check_title("  샘플 작업  "), "샘플 작업")

    def test_빈_제목은_거절한다(self):
        with self.assertRaises(ValueError):
            board.check_title("")

    def test_공백뿐인_제목은_거절한다(self):
        with self.assertRaises(ValueError):
            board.check_title("   \t ")

    def test_문자열이_아니면_거절한다(self):
        for bad in (None, 123, ["a"], {"t": 1}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                board.check_title(bad)


class 링크_하나를_검사할_때(unittest.TestCase):
    def test_정상_링크는_공백을_뗀_이름과_URL을_돌려준다(self):
        self.assertEqual(board.check_link(" 참고 ", "https://example.com/a"),
                         ("참고", "https://example.com/a"))

    def test_http도_통과한다(self):
        self.assertEqual(board.check_link("a", "http://example.com")[1], "http://example.com")

    def test_이름이_빈_경우_거절한다(self):
        for name in ("", "   "):
            with self.subTest(name=name), self.assertRaises(ValueError):
                board.check_link(name, "https://example.com/a")

    def test_이름이_40자면_통과하고_41자면_거절한다(self):
        self.assertEqual(board.check_link("가" * 40, "https://example.com/a")[0], "가" * 40)
        with self.assertRaises(ValueError):
            board.check_link("가" * 41, "https://example.com/a")

    def test_URL이_2000자면_통과하고_2001자면_거절한다(self):
        base = "https://example.com/"
        ok = base + "a" * (2000 - len(base))
        self.assertEqual(len(ok), 2000)
        self.assertEqual(board.check_link("a", ok)[1], ok)
        with self.assertRaises(ValueError):
            board.check_link("a", ok + "a")

    def test_http_계열이_아닌_URL은_거절한다(self):
        for url in ("javascript:alert(1)", "file:///tmp/a.html", "/Users/example/notes.md",
                    "~/vault/a.md", "ftp://example.com/a", "example.com/a", ""):
            with self.subTest(url=url), self.assertRaises(ValueError):
                board.check_link("a", url)

    def test_문자열이_아니면_거절한다(self):
        for name, url in ((None, "https://example.com"), ("a", None), (1, 2)):
            with self.subTest(name=name, url=url), self.assertRaises(ValueError):
                board.check_link(name, url)


class 링크_목록을_검사할_때(unittest.TestCase):
    def links(self, n):
        return [(f"링크{i}", f"https://example.com/{i}") for i in range(n)]

    def test_빈_목록은_통과한다(self):
        self.assertEqual(board.check_links([]), [])

    def test_5개까지는_통과한다(self):
        self.assertEqual(len(board.check_links(self.links(5))), 5)

    def test_6개는_거절한다(self):
        with self.assertRaises(ValueError):
            board.check_links(self.links(6))

    def test_하나라도_틀리면_전체를_거절한다(self):
        mixed = self.links(2) + [("나쁨", "javascript:alert(1)")]
        with self.assertRaises(ValueError):
            board.check_links(mixed)


class 열을_옮길_때(unittest.TestCase):
    def test_순방향_두_전이만_허용한다(self):
        allowed = {("planned", "doing"), ("doing", "done")}
        for cur in board.COLUMNS + ("archived", "x"):
            for new in board.COLUMNS + ("archived", "x"):
                with self.subTest(cur=cur, new=new):
                    self.assertEqual(board.can_move(cur, new), (cur, new) in allowed)

    def test_열은_세_개다(self):
        self.assertEqual(board.COLUMNS, ("planned", "doing", "done"))


class 경과_일수를_셀_때(unittest.TestCase):
    def test_요청_3일_뒤는_3이다(self):
        self.assertEqual(board.elapsed_days(ts(2026, 11, 11), None, TODAY), 3)

    def test_PR_대기_시각이_있으면_거기서부터_센다(self):
        self.assertEqual(board.elapsed_days(ts(2026, 11, 1), ts(2026, 11, 13), TODAY), 1)

    def test_둘_다_없으면_None이다(self):
        self.assertIsNone(board.elapsed_days(None, None, TODAY))

    def test_미래_시각이면_음수_대신_0이다(self):
        self.assertEqual(board.elapsed_days(ts(2026, 11, 20), None, TODAY), 0)

    def test_같은_날이면_0이다(self):
        self.assertEqual(board.elapsed_days(ts(2026, 11, 14, 1), None, TODAY), 0)


class 후보_표식을_판정할_때(unittest.TestCase):
    def test_진행_카드에_step이_전부_completed면_True다(self):
        self.assertTrue(board.candidate_mark(doing_card(), ["completed", "completed"]))

    def test_하나라도_pending이면_False다(self):
        self.assertFalse(board.candidate_mark(doing_card(), ["completed", "pending"]))

    def test_error_blocked_가_섞여도_False다(self):
        for st in ("error", "blocked"):
            with self.subTest(st=st):
                self.assertFalse(board.candidate_mark(doing_card(), ["completed", st]))

    def test_step이_0개면_False다(self):
        self.assertFalse(board.candidate_mark(doing_card(), []))

    def test_PR_대기_표시가_있으면_False다(self):
        self.assertFalse(board.candidate_mark(doing_card(pr_at=ts(2026, 11, 13)), ["completed"]))

    def test_열이_진행이_아니면_False다(self):
        for col in ("planned", "done"):
            with self.subTest(col=col):
                self.assertFalse(board.candidate_mark(doing_card(column=col), ["completed"]))


class 연결_상태를_판정할_때(unittest.TestCase):
    def test_진행인데_task가_없으면_설계_중이다(self):
        self.assertEqual(board.connection_state(doing_card(task=None), False), "designing")

    def test_task가_있는데_phases가_없으면_연결_끊김이다(self):
        self.assertEqual(board.connection_state(doing_card(), False), "disconnected")

    def test_task가_있고_phases도_있으면_None이다(self):
        self.assertIsNone(board.connection_state(doing_card(), True))

    def test_진행이_아닌_카드는_None이다(self):
        self.assertIsNone(board.connection_state({"column": "planned", "task": None}, False))
        self.assertIsNone(board.connection_state({"column": "done", "task": "x"}, False))


class 진행도를_셀_때(unittest.TestCase):
    def test_완료_수와_전체를_센다(self):
        self.assertEqual(board.progress(["completed", "pending", "completed"]),
                         {"done": 2, "total": 3})

    def test_step이_0개면_None이다(self):
        self.assertIsNone(board.progress([]))


if __name__ == "__main__":
    unittest.main()
