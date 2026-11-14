"""desk/board.py 파일 읽기·쓰기 테스트 (step 2). 임시 DESK_HOME · 지어낸 레포 · example.com 링크.

엣지 5축: 빈 값(카드 0장 · 링크 0개) · 비정상 입력(깨진 JSON · 경로 탈출) ·
실패 경로(없는 카드 · 409 계열) · 상태 전이(열 이동 · 보관 · 요청 · 취소) ·
동시성(요청 · 링크를 카드와 별도 파일로 나눈 것을 단언)
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from desk import board, paths

REPO = "sample-repo"
OTHER = "other-repo"
NOW = 1_800_000_000.0


class _Case(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        patcher = patch.dict(os.environ, {"DESK_HOME": self._tmp.name})
        patcher.start()
        self.addCleanup(patcher.stop)

    def files(self, repo=REPO):
        d = paths.board_dir(repo)
        return sorted(p.name for p in d.iterdir()) if d.exists() else []

    def card_path(self, cid, repo=REPO):
        return paths.board_dir(repo) / f"{cid}.json"

    def raw(self, cid, repo=REPO):
        return json.loads(self.card_path(cid, repo).read_text(encoding="utf-8"))

    def make_doing(self, title="진행 작업", repo=REPO):
        card = board.add_card(repo, title, "", NOW)
        board.move_card(repo, card["id"], "doing", NOW + 10)
        return card["id"]


class 경로와_id(_Case):
    def test_board_dir은_홈_아래_board_레포다(self):
        self.assertEqual(paths.board_dir(REPO), Path(self._tmp.name) / "board" / REPO)

    def test_id는_정수초_하이픈_16진4자리다(self):
        cid = board.new_card_id(NOW)
        self.assertRegex(cid, r"^1800000000-[0-9a-f]{4}$")

    def test_id는_시각순으로_정렬된다(self):
        self.assertLess(board.new_card_id(NOW), board.new_card_id(NOW + 5))


class 카드를_추가할_때(_Case):
    def test_카드_파일이_생기고_열은_예정이다(self):
        card = board.add_card(REPO, "  샘플 작업  ", "메모", NOW)
        data = self.raw(card["id"])
        self.assertEqual(data["title"], "샘플 작업")
        self.assertEqual(data["note"], "메모")
        self.assertEqual(data["column"], "planned")
        self.assertEqual(data["created_at"], NOW)
        for key in ("task", "doing_at", "pr_at", "done_at", "archived_at"):
            self.assertIsNone(data[key])
        self.assertEqual(self.files(), [f"{card['id']}.json"])

    def test_빈_제목은_거절하고_파일이_없다(self):
        with self.assertRaises(ValueError):
            board.add_card(REPO, "   ", "", NOW)
        self.assertEqual(self.files(), [])

    def test_같은_레포_같은_예정_제목은_DuplicateTitle이고_파일이_안_는다(self):
        board.add_card(REPO, "중복 제목", "", NOW)
        with self.assertRaises(board.DuplicateTitle):
            board.add_card(REPO, "  중복 제목 ", "", NOW + 1)
        self.assertEqual(len(self.files()), 1)

    def test_다른_레포의_같은_제목은_통과한다(self):
        board.add_card(REPO, "같은 제목", "", NOW)
        board.add_card(OTHER, "같은 제목", "", NOW + 1)
        self.assertEqual(len(self.files(OTHER)), 1)

    def test_진행_카드와_같은_제목은_통과한다(self):
        self.make_doing("같은 제목")
        board.add_card(REPO, "같은 제목", "", NOW + 20)
        self.assertEqual(len(board.list_cards(REPO)[0]), 2)

    def test_완료_카드와_같은_제목은_통과한다(self):
        cid = self.make_doing("같은 제목")
        board.move_card(REPO, cid, "done", NOW + 20)
        board.add_card(REPO, "같은 제목", "", NOW + 30)

    def test_보관한_진행_카드와_같은_제목은_통과한다(self):
        cid = self.make_doing("같은 제목")
        board.archive_card(REPO, cid, NOW + 20)
        board.add_card(REPO, "같은 제목", "", NOW + 30)

    def test_링크가_같이_오면_링크_파일도_쓴다(self):
        card = board.add_card(REPO, "링크 카드", "", NOW,
                              links=[("문서", "https://example.com/a")])
        self.assertEqual(self.files(), [f"{card['id']}.json", f"{card['id']}.refs.json"])
        refs = json.loads((paths.board_dir(REPO) / f"{card['id']}.refs.json")
                          .read_text(encoding="utf-8"))["refs"]
        self.assertEqual([(r["name"], r["url"]) for r in refs],
                         [("문서", "https://example.com/a")])
        self.assertTrue(refs[0]["id"])

    def test_링크가_없으면_링크_파일을_안_만든다(self):
        card = board.add_card(REPO, "링크 없음", "", NOW)
        self.assertEqual(self.files(), [f"{card['id']}.json"])

    def test_링크_하나가_틀리면_카드_파일도_없다(self):
        with self.assertRaises(ValueError):
            board.add_card(REPO, "깨질 카드", "", NOW, links=[
                ("좋은", "https://example.com/a"),
                ("나쁜", "javascript:alert(1)"),
            ])
        self.assertEqual(self.files(), [])

    def test_링크_6개면_거절하고_파일이_없다(self):
        links = [(f"n{i}", f"https://example.com/{i}") for i in range(6)]
        with self.assertRaises(ValueError):
            board.add_card(REPO, "많은 링크", "", NOW, links=links)
        self.assertEqual(self.files(), [])

    def test_링크_5개는_통과한다(self):
        links = [(f"n{i}", f"https://example.com/{i}") for i in range(5)]
        card = board.add_card(REPO, "다섯 링크", "", NOW, links=links)
        self.assertEqual(len(board.read_refs(REPO, card["id"])[0]), 5)

    def test_검증_실패는_중복_검사보다_먼저라_예외가_ValueError다(self):
        board.add_card(REPO, "중복", "", NOW)
        with self.assertRaises(ValueError) as cm:
            board.add_card(REPO, "중복", "", NOW + 1, links=[("x", "ftp://example.com")])
        self.assertNotIsInstance(cm.exception, board.DuplicateTitle)

    def test_경로_탈출_레포는_거절한다(self):
        for bad in ("", "..", "a/b", "../x", "a\\b"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                board.add_card(bad, "제목", "", NOW)
        self.assertFalse((Path(self._tmp.name) / "board").exists())


class 카드를_읽을_때(_Case):
    def test_카드가_0장이면_빈_목록과_0이다(self):
        self.assertEqual(board.list_cards(REPO), ([], 0))

    def test_목록_항목에_id와_요청_시각이_붙는다(self):
        card = board.add_card(REPO, "읽기", "", NOW)
        board.request_start(REPO, card["id"], NOW + 5)
        cards, broken = board.list_cards(REPO)
        self.assertEqual(broken, 0)
        self.assertEqual(cards[0]["id"], card["id"])
        self.assertEqual(cards[0]["requested_at"], NOW + 5)

    def test_요청이_없으면_requested_at은_None이다(self):
        board.add_card(REPO, "읽기", "", NOW)
        self.assertIsNone(board.list_cards(REPO)[0][0]["requested_at"])

    def test_깨진_카드_파일은_건너뛰고_센다(self):
        good = board.add_card(REPO, "멀쩡", "", NOW)
        d = paths.board_dir(REPO)
        (d / "1800000001-aaaa.json").write_text("{깨짐", encoding="utf-8")
        (d / "1800000002-bbbb.json").write_text(json.dumps({"note": "제목 없음"}), encoding="utf-8")
        cards, broken = board.list_cards(REPO)
        self.assertEqual([c["id"] for c in cards], [good["id"]])
        self.assertEqual(broken, 2)

    def test_깨진_요청_파일은_요청_없음으로_보고_카드는_산다(self):
        card = board.add_card(REPO, "요청 깨짐", "", NOW)
        (paths.board_dir(REPO) / f"{card['id']}.request.json").write_text("{깨짐", encoding="utf-8")
        cards, broken = board.list_cards(REPO)
        self.assertEqual(len(cards), 1)
        self.assertEqual(broken, 0)
        self.assertIsNone(cards[0]["requested_at"])
        self.assertTrue(cards[0]["request_broken"])

    def test_깨진_링크_파일은_빈_목록이고_표시된다(self):
        card = board.add_card(REPO, "링크 깨짐", "", NOW)
        (paths.board_dir(REPO) / f"{card['id']}.refs.json").write_text("{깨짐", encoding="utf-8")
        self.assertEqual(board.read_refs(REPO, card["id"]), ([], True))
        cards, broken = board.list_cards(REPO)
        self.assertEqual(len(cards), 1)
        self.assertEqual(broken, 0)
        self.assertTrue(cards[0]["refs_broken"])

    def test_링크_파일이_없으면_빈_목록이고_깨진_게_아니다(self):
        card = board.add_card(REPO, "링크 없음", "", NOW)
        self.assertEqual(board.read_refs(REPO, card["id"]), ([], False))

    def test_없는_카드는_NotFound다(self):
        with self.assertRaises(board.NotFound):
            board.read_card(REPO, "1800000000-abcd")

    def test_레포_폴더가_없어도_목록은_비어_있다(self):
        self.assertEqual(board.list_cards("never-made"), ([], 0))

    def test_점으로_시작하는_임시_파일과_보조_파일은_카드로_세지_않는다(self):
        card = board.add_card(REPO, "하나", "", NOW)
        board.request_start(REPO, card["id"], NOW)
        board.add_ref(REPO, card["id"], "문서", "https://example.com/x")
        (paths.board_dir(REPO) / ".1800000000-aaaa.json.x.tmp").write_text("x", encoding="utf-8")
        cards, broken = board.list_cards(REPO)
        self.assertEqual((len(cards), broken), (1, 0))


class 경로_탈출_id(_Case):
    def test_id_형식이_아니면_모든_함수가_거절한다(self):
        card = board.add_card(REPO, "대상", "", NOW)
        bad_ids = ("../x", "1800000000-ABCD", "1800000000-abc", "abc", "", "1800000000-abcd/..",
                   "1800000000-abcd.request")
        calls = [
            lambda i: board.read_card(REPO, i),
            lambda i: board.delete_card(REPO, i),
            lambda i: board.archive_card(REPO, i, NOW),
            lambda i: board.revive_card(REPO, i),
            lambda i: board.request_start(REPO, i, NOW),
            lambda i: board.cancel_request(REPO, i),
            lambda i: board.add_ref(REPO, i, "n", "https://example.com"),
            lambda i: board.update_ref(REPO, i, "r1", "n", "https://example.com"),
            lambda i: board.delete_ref(REPO, i, "r1"),
            lambda i: board.move_card(REPO, i, "doing", NOW),
            lambda i: board.mark_pr(REPO, i, NOW),
            lambda i: board.set_task(REPO, i, "t"),
            lambda i: board.read_refs(REPO, i),
        ]
        for bad in bad_ids:
            for call in calls:
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    call(bad)
        self.assertEqual(self.raw(card["id"])["column"], "planned")

    def test_레포_이름이_탈출_문자면_읽기도_거절한다(self):
        for bad in ("", "..", "a/b"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                board.list_cards(bad)
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                board.read_card(bad, "1800000000-abcd")


class 카드를_삭제할_때(_Case):
    def test_예정_카드는_카드_요청_링크_파일이_함께_사라진다(self):
        card = board.add_card(REPO, "삭제", "", NOW, links=[("문서", "https://example.com/a")])
        board.request_start(REPO, card["id"], NOW + 1)
        self.assertEqual(len(self.files()), 3)
        board.delete_card(REPO, card["id"])
        self.assertEqual(self.files(), [])

    def test_진행_카드_삭제는_WrongColumn이고_파일은_그대로다(self):
        cid = self.make_doing()
        before = self.card_path(cid).read_bytes()
        with self.assertRaises(board.WrongColumn):
            board.delete_card(REPO, cid)
        self.assertEqual(self.card_path(cid).read_bytes(), before)

    def test_PR_대기_표시_카드_삭제도_거절한다(self):
        cid = self.make_doing()
        board.mark_pr(REPO, cid, NOW + 20)
        with self.assertRaises(board.WrongColumn):
            board.delete_card(REPO, cid)
        self.assertTrue(self.card_path(cid).exists())

    def test_완료_카드_삭제도_거절한다(self):
        cid = self.make_doing()
        board.move_card(REPO, cid, "done", NOW + 20)
        with self.assertRaises(board.WrongColumn):
            board.delete_card(REPO, cid)

    def test_없는_카드_삭제는_NotFound다(self):
        with self.assertRaises(board.NotFound):
            board.delete_card(REPO, "1800000000-abcd")

    def test_보조_파일이_없는_카드도_삭제된다(self):
        card = board.add_card(REPO, "단순", "", NOW)
        board.delete_card(REPO, card["id"])
        self.assertEqual(self.files(), [])


class 보관과_되살리기(_Case):
    def test_진행_카드를_보관하면_보관_시각이_적힌다(self):
        cid = self.make_doing()
        board.archive_card(REPO, cid, NOW + 99)
        data = self.raw(cid)
        self.assertEqual(data["archived_at"], NOW + 99)
        self.assertEqual(data["column"], "doing")

    def test_PR_대기_카드와_완료_카드도_보관된다(self):
        a = self.make_doing("a")
        board.mark_pr(REPO, a, NOW + 20)
        board.archive_card(REPO, a, NOW + 30)
        b = self.make_doing("b")
        board.move_card(REPO, b, "done", NOW + 20)
        board.archive_card(REPO, b, NOW + 30)
        self.assertEqual(self.raw(a)["archived_at"], NOW + 30)
        self.assertEqual(self.raw(b)["archived_at"], NOW + 30)

    def test_예정_카드_보관은_WrongColumn이다(self):
        card = board.add_card(REPO, "예정", "", NOW)
        with self.assertRaises(board.WrongColumn):
            board.archive_card(REPO, card["id"], NOW)
        self.assertIsNone(self.raw(card["id"])["archived_at"])

    def test_되살리면_보관_시각이_지워지고_열은_그대로다(self):
        cid = self.make_doing()
        board.archive_card(REPO, cid, NOW + 30)
        board.revive_card(REPO, cid)
        data = self.raw(cid)
        self.assertIsNone(data["archived_at"])
        self.assertEqual(data["column"], "doing")

    def test_없는_카드_보관_되살리기는_NotFound다(self):
        with self.assertRaises(board.NotFound):
            board.archive_card(REPO, "1800000000-abcd", NOW)
        with self.assertRaises(board.NotFound):
            board.revive_card(REPO, "1800000000-abcd")


class 시작_요청(_Case):
    def test_요청_파일이_정확히_하나_생기고_카드_파일은_안_바뀐다(self):
        card = board.add_card(REPO, "시작", "", NOW)
        before = self.card_path(card["id"]).read_bytes()
        board.request_start(REPO, card["id"], NOW + 7)
        reqs = [f for f in self.files() if f.endswith(".request.json")]
        self.assertEqual(reqs, [f"{card['id']}.request.json"])
        data = json.loads((paths.board_dir(REPO) / reqs[0]).read_text(encoding="utf-8"))
        self.assertEqual(data, {"at": NOW + 7})
        self.assertEqual(self.card_path(card["id"]).read_bytes(), before)

    def test_두_번째_요청은_AlreadyRequested고_요청_파일은_하나다(self):
        card = board.add_card(REPO, "시작", "", NOW)
        board.request_start(REPO, card["id"], NOW + 7)
        with self.assertRaises(board.AlreadyRequested):
            board.request_start(REPO, card["id"], NOW + 8)
        reqs = [f for f in self.files() if f.endswith(".request.json")]
        self.assertEqual(len(reqs), 1)
        self.assertEqual(board.list_cards(REPO)[0][0]["requested_at"], NOW + 7)

    def test_예정이_아닌_카드는_WrongColumn이고_요청_파일이_없다(self):
        cid = self.make_doing()
        with self.assertRaises(board.WrongColumn):
            board.request_start(REPO, cid, NOW + 30)
        self.assertEqual([f for f in self.files() if f.endswith(".request.json")], [])

    def test_없는_카드는_NotFound다(self):
        with self.assertRaises(board.NotFound):
            board.request_start(REPO, "1800000000-abcd", NOW)


class 요청을_취소할_때(_Case):
    def test_요청_파일만_지우고_카드_파일은_그대로다(self):
        card = board.add_card(REPO, "취소", "", NOW)
        board.request_start(REPO, card["id"], NOW + 1)
        before = self.card_path(card["id"]).read_bytes()
        board.cancel_request(REPO, card["id"])
        self.assertEqual(self.files(), [f"{card['id']}.json"])
        self.assertEqual(self.card_path(card["id"]).read_bytes(), before)

    def test_취소_뒤_다시_시작하면_새_파일을_쓴다(self):
        card = board.add_card(REPO, "재시작", "", NOW)
        board.request_start(REPO, card["id"], NOW + 1)
        board.cancel_request(REPO, card["id"])
        board.request_start(REPO, card["id"], NOW + 9)
        self.assertEqual(board.list_cards(REPO)[0][0]["requested_at"], NOW + 9)

    def test_요청이_없으면_NoRequest다(self):
        card = board.add_card(REPO, "요청 없음", "", NOW)
        with self.assertRaises(board.NoRequest):
            board.cancel_request(REPO, card["id"])

    def test_예정을_떠난_카드는_WrongColumn이고_요청_파일은_그대로다(self):
        card = board.add_card(REPO, "떠남", "", NOW)
        board.request_start(REPO, card["id"], NOW + 1)
        board.move_card(REPO, card["id"], "doing", NOW + 2)
        with self.assertRaises(board.WrongColumn):
            board.cancel_request(REPO, card["id"])
        self.assertIn(f"{card['id']}.request.json", self.files())

    def test_없는_카드는_NotFound다(self):
        with self.assertRaises(board.NotFound):
            board.cancel_request(REPO, "1800000000-abcd")


class 링크를_고칠_때(_Case):
    def setUp(self):
        super().setUp()
        self.cid = board.add_card(REPO, "링크 대상", "", NOW)["id"]

    def names(self):
        return [r["name"] for r in board.read_refs(REPO, self.cid)[0]]

    def test_추가하면_id가_붙은_링크를_돌려준다(self):
        ref = board.add_ref(REPO, self.cid, " 문서 ", "https://example.com/a")
        self.assertEqual(ref["name"], "문서")
        self.assertEqual(ref["url"], "https://example.com/a")
        self.assertTrue(ref["id"])
        self.assertEqual(board.read_refs(REPO, self.cid)[0], [ref])

    def test_링크_id는_서로_다르다(self):
        a = board.add_ref(REPO, self.cid, "a", "https://example.com/a")
        b = board.add_ref(REPO, self.cid, "b", "https://example.com/b")
        self.assertNotEqual(a["id"], b["id"])

    def test_5개까지_되고_6번째는_TooManyLinks다(self):
        for i in range(5):
            board.add_ref(REPO, self.cid, f"n{i}", f"https://example.com/{i}")
        with self.assertRaises(board.TooManyLinks):
            board.add_ref(REPO, self.cid, "n5", "https://example.com/5")
        self.assertEqual(len(self.names()), 5)

    def test_틀린_이름_URL은_ValueError고_파일이_안_바뀐다(self):
        board.add_ref(REPO, self.cid, "ok", "https://example.com/ok")
        path = paths.board_dir(REPO) / f"{self.cid}.refs.json"
        before = path.read_bytes()
        bad = [("", "https://example.com"), ("x" * 41, "https://example.com"),
               ("n", "javascript:alert(1)"), ("n", "/Users/me/vault/x.md"),
               ("n", "file:///etc/passwd"), ("n", "https://example.com/" + "a" * 2000)]
        for name, url in bad:
            with self.subTest(name=name[:5], url=url[:20]), self.assertRaises(ValueError):
                board.add_ref(REPO, self.cid, name, url)
        self.assertEqual(path.read_bytes(), before)

    def test_수정은_이름과_URL을_바꾸고_개수는_그대로다(self):
        a = board.add_ref(REPO, self.cid, "a", "https://example.com/a")
        board.add_ref(REPO, self.cid, "b", "https://example.com/b")
        board.update_ref(REPO, self.cid, a["id"], "새 이름", "https://example.com/new")
        refs = board.read_refs(REPO, self.cid)[0]
        self.assertEqual(len(refs), 2)
        self.assertEqual((refs[0]["id"], refs[0]["name"], refs[0]["url"]),
                         (a["id"], "새 이름", "https://example.com/new"))
        self.assertEqual(refs[1]["name"], "b")

    def test_수정도_검증한다(self):
        a = board.add_ref(REPO, self.cid, "a", "https://example.com/a")
        with self.assertRaises(ValueError):
            board.update_ref(REPO, self.cid, a["id"], "a", "javascript:x")
        self.assertEqual(board.read_refs(REPO, self.cid)[0][0]["url"], "https://example.com/a")

    def test_삭제는_그_링크만_지운다(self):
        a = board.add_ref(REPO, self.cid, "a", "https://example.com/a")
        board.add_ref(REPO, self.cid, "b", "https://example.com/b")
        board.delete_ref(REPO, self.cid, a["id"])
        self.assertEqual(self.names(), ["b"])

    def test_없는_링크의_수정_삭제는_NotFound다(self):
        board.add_ref(REPO, self.cid, "a", "https://example.com/a")
        with self.assertRaises(board.NotFound):
            board.update_ref(REPO, self.cid, "nope", "a", "https://example.com/a")
        with self.assertRaises(board.NotFound):
            board.delete_ref(REPO, self.cid, "nope")

    def test_없는_카드의_링크_작업은_NotFound다(self):
        ghost = "1800000000-abcd"
        with self.assertRaises(board.NotFound):
            board.add_ref(REPO, ghost, "a", "https://example.com/a")
        with self.assertRaises(board.NotFound):
            board.update_ref(REPO, ghost, "r", "a", "https://example.com/a")
        with self.assertRaises(board.NotFound):
            board.delete_ref(REPO, ghost, "r")

    def test_보관과_완료_카드도_링크를_고칠_수_있다(self):
        cid = self.make_doing("보관될 것")
        board.archive_card(REPO, cid, NOW + 30)
        ref = board.add_ref(REPO, cid, "a", "https://example.com/a")
        board.update_ref(REPO, cid, ref["id"], "b", "https://example.com/b")
        board.delete_ref(REPO, cid, ref["id"])
        self.assertEqual(board.read_refs(REPO, cid)[0], [])

    def test_링크를_고쳐도_카드_파일은_안_바뀐다(self):
        before = self.card_path(self.cid).read_bytes()
        ref = board.add_ref(REPO, self.cid, "a", "https://example.com/a")
        board.update_ref(REPO, self.cid, ref["id"], "b", "https://example.com/b")
        board.delete_ref(REPO, self.cid, ref["id"])
        self.assertEqual(self.card_path(self.cid).read_bytes(), before)

    def test_깨진_링크_파일에_추가_수정_삭제하면_RefsBroken이고_파일이_안_바뀐다(self):
        path = paths.board_dir(REPO) / f"{self.cid}.refs.json"
        path.write_text("{깨짐", encoding="utf-8")
        before = path.read_bytes()
        with self.assertRaises(board.RefsBroken):
            board.add_ref(REPO, self.cid, "a", "https://example.com/a")
        with self.assertRaises(board.RefsBroken):
            board.update_ref(REPO, self.cid, "r0000", "a", "https://example.com/a")
        with self.assertRaises(board.RefsBroken):
            board.delete_ref(REPO, self.cid, "r0000")
        self.assertEqual(path.read_bytes(), before)

    def test_링크_파일이_없으면_깨진_게_아니라서_새로_만든다(self):
        self.assertFalse((paths.board_dir(REPO) / f"{self.cid}.refs.json").exists())
        board.add_ref(REPO, self.cid, "a", "https://example.com/a")
        self.assertEqual(self.names(), ["a"])


class 열을_옮길_때(_Case):
    def test_예정에서_진행_완료로만_가고_날짜가_적힌다(self):
        card = board.add_card(REPO, "이동", "", NOW)
        cid = card["id"]
        board.move_card(REPO, cid, "doing", NOW + 10)
        data = self.raw(cid)
        self.assertEqual((data["column"], data["doing_at"], data["done_at"]), ("doing", NOW + 10, None))
        board.move_card(REPO, cid, "done", NOW + 20)
        data = self.raw(cid)
        self.assertEqual((data["column"], data["doing_at"], data["done_at"]),
                         ("done", NOW + 10, NOW + 20))
        self.assertEqual(data["created_at"], NOW)

    def test_거꾸로_건너뛰기_제자리는_ValueError고_파일이_그대로다(self):
        card = board.add_card(REPO, "이동", "", NOW)
        cid = card["id"]
        before = self.card_path(cid).read_bytes()
        for new in ("done", "planned"):
            with self.subTest(new=new), self.assertRaises(ValueError):
                board.move_card(REPO, cid, new, NOW + 1)
        self.assertEqual(self.card_path(cid).read_bytes(), before)
        board.move_card(REPO, cid, "doing", NOW + 2)
        before = self.card_path(cid).read_bytes()
        for new in ("planned", "doing"):
            with self.subTest(new=new), self.assertRaises(ValueError):
                board.move_card(REPO, cid, new, NOW + 3)
        self.assertEqual(self.card_path(cid).read_bytes(), before)

    def test_모르는_열_이름은_ValueError다(self):
        card = board.add_card(REPO, "이동", "", NOW)
        with self.assertRaises(ValueError):
            board.move_card(REPO, card["id"], "archive", NOW)

    def test_이동해도_요청_파일은_지우지_않는다(self):
        card = board.add_card(REPO, "이동", "", NOW)
        board.request_start(REPO, card["id"], NOW + 1)
        board.move_card(REPO, card["id"], "doing", NOW + 2)
        self.assertIn(f"{card['id']}.request.json", self.files())

    def test_없는_카드_이동은_NotFound다(self):
        with self.assertRaises(board.NotFound):
            board.move_card(REPO, "1800000000-abcd", "doing", NOW)


class PR_대기_표시(_Case):
    def test_진행_카드에_pr_at을_적는다(self):
        cid = self.make_doing()
        board.mark_pr(REPO, cid, NOW + 50)
        data = self.raw(cid)
        self.assertEqual((data["pr_at"], data["column"]), (NOW + 50, "doing"))

    def test_두_번째는_ValueError고_시각이_안_바뀐다(self):
        cid = self.make_doing()
        board.mark_pr(REPO, cid, NOW + 50)
        with self.assertRaises(ValueError):
            board.mark_pr(REPO, cid, NOW + 60)
        self.assertEqual(self.raw(cid)["pr_at"], NOW + 50)

    def test_진행이_아닌_카드는_ValueError다(self):
        card = board.add_card(REPO, "예정", "", NOW)
        with self.assertRaises(ValueError):
            board.mark_pr(REPO, card["id"], NOW)
        self.assertIsNone(self.raw(card["id"])["pr_at"])
        cid = self.make_doing("완료될 것")
        board.move_card(REPO, cid, "done", NOW + 20)
        with self.assertRaises(ValueError):
            board.mark_pr(REPO, cid, NOW + 30)

    def test_완료로_옮겨도_pr_at은_이력으로_남는다(self):
        cid = self.make_doing()
        board.mark_pr(REPO, cid, NOW + 50)
        board.move_card(REPO, cid, "done", NOW + 60)
        data = self.raw(cid)
        self.assertEqual((data["column"], data["pr_at"]), ("done", NOW + 50))

    def test_없는_카드는_NotFound다(self):
        with self.assertRaises(board.NotFound):
            board.mark_pr(REPO, "1800000000-abcd", NOW)


class task_기록(_Case):
    def test_phases가_없는_이름도_저장된다(self):
        cid = self.make_doing()
        board.set_task(REPO, cid, "no-such-phase")
        self.assertEqual(self.raw(cid)["task"], "no-such-phase")

    def test_예정_카드에도_저장된다(self):
        card = board.add_card(REPO, "예정", "", NOW)
        board.set_task(REPO, card["id"], "early")
        self.assertEqual(self.raw(card["id"])["task"], "early")

    def test_경로_탈출_이름은_거절한다(self):
        cid = self.make_doing()
        for bad in ("", "  ", "..", "a/b", "../x", "a\\b", None, 5):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                board.set_task(REPO, cid, bad)
        self.assertIsNone(self.raw(cid)["task"])

    def test_다른_필드는_그대로다(self):
        cid = self.make_doing()
        before = self.raw(cid)
        board.set_task(REPO, cid, "t")
        after = self.raw(cid)
        before["task"] = "t"
        self.assertEqual(after, before)

    def test_없는_카드는_NotFound다(self):
        with self.assertRaises(board.NotFound):
            board.set_task(REPO, "1800000000-abcd", "t")


class 쓰기_방식(_Case):
    def test_모든_쓰기는_write_json_atomic을_거친다(self):
        real = board.write_json_atomic
        with patch.object(board, "write_json_atomic", side_effect=real) as spy:
            card = board.add_card(REPO, "원자", "", NOW, links=[("a", "https://example.com/a")])
            board.request_start(REPO, card["id"], NOW)
            board.add_ref(REPO, card["id"], "b", "https://example.com/b")
            board.move_card(REPO, card["id"], "doing", NOW + 1)
            board.mark_pr(REPO, card["id"], NOW + 2)
            board.set_task(REPO, card["id"], "t")
            board.archive_card(REPO, card["id"], NOW + 3)
            board.revive_card(REPO, card["id"])
        self.assertGreaterEqual(spy.call_count, 8)

    def test_쓰기_뒤_임시_파일이_남지_않는다(self):
        card = board.add_card(REPO, "깨끗", "", NOW)
        board.request_start(REPO, card["id"], NOW)
        board.move_card(REPO, card["id"], "doing", NOW + 1)
        self.assertEqual([f for f in self.files() if f.endswith(".tmp")], [])

    def test_서버와_desk_py가_고치는_파일이_서로_다르다(self):
        card = board.add_card(REPO, "분리", "", NOW)
        cid = card["id"]
        base = paths.board_dir(REPO)
        board.request_start(REPO, cid, NOW)
        self.assertTrue((base / f"{cid}.request.json").exists())
        board.add_ref(REPO, cid, "a", "https://example.com/a")
        self.assertTrue((base / f"{cid}.refs.json").exists())
        data = self.raw(cid)
        self.assertNotIn("requested_at", data)
        self.assertNotIn("refs", data)

    def test_board_모듈은_서브프로세스와_HTTP를_쓰지_않는다(self):
        src = Path(board.__file__).read_text(encoding="utf-8")
        for banned in ("subprocess", "urllib", "http.client", "socket", "os.system", "requests"):
            self.assertNotIn(banned, src)
        self.assertNotIn("write_text", src)


if __name__ == "__main__":
    unittest.main()
