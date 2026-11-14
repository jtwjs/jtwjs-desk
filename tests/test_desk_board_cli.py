"""scripts/desk.py `board` 서브커맨드 테스트 (step 6). 임시 DESK_HOME · DESK_CONFIG · 지어낸 레포.

엣지 5축: 빈 값(요청 0건) · 비정상 입력(없는 카드 · 모르는 열 · 경로 탈출 id) ·
실패 경로(거절 종료 코드 · 파일 그대로) · 상태 전이(전 방향 표) ·
동시성(서버가 쓰는 요청 · 링크 파일을 이 명령이 건드리지 않음 · 원자 쓰기)
"""
import io
import json
import os
import tempfile
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from desk import board, paths
from scripts import desk

REPO = "sample-repo"
OTHER = "other-repo"
NOW = 1_800_000_000.0


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            result = desk.main(["desk.py", *argv])
        except SystemExit as e:  # argparse 오류
            result = e.code
    return result, out.getvalue(), err.getvalue()


class _Case(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        tmp = Path(self._tmp.name)
        cfg = tmp / "config.json"
        cfg.write_text(json.dumps({"repos": [f"/work/{REPO}", f"/work/{OTHER}"]}), encoding="utf-8")
        patcher = patch.dict(os.environ, {"DESK_HOME": str(tmp / "home"), "DESK_CONFIG": str(cfg)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def card_path(self, cid, repo=REPO):
        return paths.board_dir(repo) / f"{cid}.json"

    def snapshot(self, repo=REPO):
        d = paths.board_dir(repo)
        if not d.exists():
            return {}
        return {p.name: p.read_bytes() for p in sorted(d.iterdir())}

    def raw(self, cid, repo=REPO):
        return json.loads(self.card_path(cid, repo).read_text(encoding="utf-8"))

    def planned(self, title="예정 작업", repo=REPO):
        return board.add_card(repo, title, "", NOW)["id"]

    def doing(self, title="진행 작업", repo=REPO):
        cid = self.planned(title, repo)
        board.move_card(repo, cid, "doing", NOW + 10)
        return cid

    def done(self, title="완료 작업", repo=REPO):
        cid = self.doing(title, repo)
        board.move_card(repo, cid, "done", NOW + 20)
        return cid


class board_requests(_Case):
    def test_요청_0건이면_출력_없이_종료코드_0(self):
        self.planned()
        rc, out, err = _run(["board", "requests"])
        self.assertEqual((rc, out, err), (0, "", ""))

    def test_요청_파일이_있는_예정_카드만_한_줄씩_낸다(self):
        a = self.planned("첫 작업")
        self.planned("요청 없음")
        d = self.doing("진행 중")
        board.request_start(REPO, a, NOW + 5)
        board.request_start(OTHER, self.planned("다른 레포 작업", OTHER), NOW + 6)
        rc, out, _ = _run(["board", "requests"])
        self.assertEqual(rc, 0)
        lines = out.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(any(l.startswith(f"{REPO} {a} 첫 작업 ") for l in lines))
        self.assertTrue(any(l.startswith(f"{OTHER} ") and "다른 레포 작업" in l for l in lines))
        self.assertNotIn(d, out)
        first = next(l for l in lines if l.startswith(REPO))
        self.assertEqual(float(first.rsplit(" ", 1)[1]), NOW + 5)

    def test_진행으로_옮겨진_카드는_요청_파일이_남아도_안_낸다(self):
        a = self.planned()
        board.request_start(REPO, a, NOW + 1)
        board.move_card(REPO, a, "doing", NOW + 2)
        rc, out, _ = _run(["board", "requests"])
        self.assertEqual((rc, out), (0, ""))

    def test_repo_인자는_그_레포만_낸다(self):
        a = self.planned("가", REPO)
        b = self.planned("나", OTHER)
        board.request_start(REPO, a, NOW)
        board.request_start(OTHER, b, NOW)
        rc, out, _ = _run(["board", "requests", "--repo", OTHER])
        self.assertEqual(rc, 0)
        self.assertEqual(len(out.splitlines()), 1)
        self.assertTrue(out.startswith(f"{OTHER} {b} "))

    def test_제목의_줄바꿈은_한_줄을_깨지_않는다(self):
        a = self.planned("두 줄\n제목")
        board.request_start(REPO, a, NOW)
        _, out, _ = _run(["board", "requests"])
        self.assertEqual(len(out.splitlines()), 1)

    def test_requests는_파일을_바꾸지_않는다(self):
        a = self.planned()
        board.request_start(REPO, a, NOW)
        before = self.snapshot()
        _run(["board", "requests"])
        self.assertEqual(before, self.snapshot())


class board_move(_Case):
    def test_planned에서_doing으로_옮기면_doing_at이_적힌다(self):
        a = self.planned()
        rc, _, err = _run(["board", "move", REPO, a, "doing"])
        self.assertEqual((rc, err), (0, ""))
        card = self.raw(a)
        self.assertEqual(card["column"], "doing")
        self.assertIsInstance(card["doing_at"], float)
        self.assertIsNone(card["done_at"])

    def test_doing에서_done으로_옮기면_done_at이_적힌다(self):
        a = self.doing()
        rc, _, _ = _run(["board", "move", REPO, a, "done"])
        self.assertEqual(rc, 0)
        card = self.raw(a)
        self.assertEqual(card["column"], "done")
        self.assertIsInstance(card["done_at"], float)
        self.assertEqual(card["doing_at"], NOW + 10)

    def test_전이_표_허용은_순방향_둘뿐이고_나머지는_거절하며_카드가_그대로다(self):
        makers = {"planned": self.planned, "doing": self.doing, "done": self.done}
        allowed = {("planned", "doing"), ("doing", "done")}
        for src, make in makers.items():
            for dst in ("planned", "doing", "done"):
                with self.subTest(src=src, dst=dst):
                    cid = make(f"{src}-{dst}")
                    before = self.snapshot()
                    rc, out, err = _run(["board", "move", REPO, cid, dst])
                    if (src, dst) in allowed:
                        self.assertEqual(rc, 0)
                    else:
                        self.assertNotEqual(rc, 0)
                        self.assertEqual(before, self.snapshot())
                        self.assertEqual(out, "")
                        self.assertEqual(len(err.strip().splitlines()), 1)

    def test_요청됨_배지는_진행으로_옮기면_사라진다(self):
        a = self.planned()
        board.request_start(REPO, a, NOW + 1)
        _run(["board", "move", REPO, a, "doing"])
        cards, _ = board.list_cards(REPO)
        c = next(x for x in cards if x["id"] == a)
        self.assertEqual(c["column"], "doing")

    def test_이동_뒤_읽기에_열과_날짜가_반영된다(self):
        a = self.planned()
        _run(["board", "move", REPO, a, "doing"])
        _run(["board", "move", REPO, a, "done"])
        cards, broken = board.list_cards(REPO)
        self.assertEqual(broken, 0)
        c = cards[0]
        self.assertEqual(c["column"], "done")
        self.assertIsNotNone(c["doing_at"])
        self.assertIsNotNone(c["done_at"])

    def test_모르는_열은_거절한다(self):
        a = self.planned()
        before = self.snapshot()
        rc, _, _ = _run(["board", "move", REPO, a, "archive"])
        self.assertNotEqual(rc, 0)
        self.assertEqual(before, self.snapshot())

    def test_없는_카드는_거절한다(self):
        rc, out, err = _run(["board", "move", REPO, "1800000000-abcd", "doing"])
        self.assertNotEqual(rc, 0)
        self.assertEqual(out, "")
        self.assertEqual(len(err.strip().splitlines()), 1)

    def test_경로_탈출_id와_레포는_거절하고_아무것도_쓰지_않는다(self):
        self.planned()
        before = self.snapshot()
        for repo, cid in ((REPO, "../x"), (REPO, "../../etc/passwd"), ("../evil", "1800000000-abcd"), ("a/b", "1")):
            with self.subTest(repo=repo, cid=cid):
                rc, _, err = _run(["board", "move", repo, cid, "doing"])
                self.assertNotEqual(rc, 0)
                self.assertNotIn(self._tmp.name, err)
        self.assertEqual(before, self.snapshot())
        self.assertFalse((Path(self._tmp.name) / "evil").exists())

    def test_출력에_파일_경로와_스택이_없다(self):
        a = self.done()
        _, out, err = _run(["board", "move", REPO, a, "planned"])
        self.assertNotIn(self._tmp.name, out + err)
        self.assertNotIn("Traceback", out + err)

    def test_깨진_카드_파일은_한_줄_오류로_거절한다(self):
        a = self.planned()
        self.card_path(a).write_text("{깨짐", encoding="utf-8")
        rc, _, err = _run(["board", "move", REPO, a, "doing"])
        self.assertNotEqual(rc, 0)
        self.assertNotIn("Traceback", err)
        self.assertNotIn(self._tmp.name, err)

    def test_이동이_끝난_카드_파일은_읽는_쪽이_항상_완전한_JSON을_본다(self):
        a = self.planned()
        path = self.card_path(a)
        stop = threading.Event()
        bad = []

        def reader():
            while not stop.is_set():
                try:
                    json.loads(path.read_text(encoding="utf-8"))
                except (ValueError, OSError) as e:
                    bad.append(repr(e))

        t = threading.Thread(target=reader)
        t.start()
        try:
            _run(["board", "move", REPO, a, "doing"])
            _run(["board", "move", REPO, a, "done"])
        finally:
            stop.set()
            t.join()
        self.assertEqual(bad, [])

    def test_이동은_요청_파일과_링크_파일을_건드리지_않는다(self):
        a = self.planned()
        board.request_start(REPO, a, NOW + 1)
        board.add_ref(REPO, a, "참고", "https://example.com/doc")
        req = paths.board_dir(REPO) / f"{a}.request.json"
        refs = paths.board_dir(REPO) / f"{a}.refs.json"
        before = (req.read_bytes(), refs.read_bytes())
        _run(["board", "move", REPO, a, "doing"])
        self.assertEqual(before, (req.read_bytes(), refs.read_bytes()))


class board_pr(_Case):
    def test_진행_카드에_pr_at을_적는다(self):
        a = self.doing()
        rc, _, err = _run(["board", "pr", REPO, a])
        self.assertEqual((rc, err), (0, ""))
        card = self.raw(a)
        self.assertIsInstance(card["pr_at"], float)
        self.assertEqual(card["column"], "doing")

    def test_두_번째는_거절하고_첫_시각이_그대로다(self):
        a = self.doing()
        _run(["board", "pr", REPO, a])
        before = self.snapshot()
        rc, _, err = _run(["board", "pr", REPO, a])
        self.assertNotEqual(rc, 0)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(len(err.strip().splitlines()), 1)

    def test_예정_카드와_완료_카드는_거절하고_파일이_그대로다(self):
        for make in (self.planned, self.done):
            with self.subTest(make=make.__name__):
                a = make(f"{make.__name__}-pr")
                before = self.snapshot()
                rc, _, _ = _run(["board", "pr", REPO, a])
                self.assertNotEqual(rc, 0)
                self.assertEqual(before, self.snapshot())

    def test_완료로_옮겨도_pr_at은_이력으로_남는다(self):
        a = self.doing()
        _run(["board", "pr", REPO, a])
        pr_at = self.raw(a)["pr_at"]
        _run(["board", "move", REPO, a, "done"])
        self.assertEqual(self.raw(a)["pr_at"], pr_at)

    def test_없는_카드와_경로_탈출은_거절한다(self):
        for cid in ("1800000000-abcd", "../x"):
            with self.subTest(cid=cid):
                rc, _, err = _run(["board", "pr", REPO, cid])
                self.assertNotEqual(rc, 0)
                self.assertNotIn(self._tmp.name, err)

    def test_되돌리는_서브커맨드는_없다(self):
        a = self.doing()
        rc, _, _ = _run(["board", "pr", REPO, a, "--undo"])
        self.assertNotEqual(rc, 0)


class board_link(_Case):
    def test_task를_카드에_저장한다(self):
        a = self.doing()
        rc, _, err = _run(["board", "link", REPO, a, "desk-kanban"])
        self.assertEqual((rc, err), (0, ""))
        self.assertEqual(self.raw(a)["task"], "desk-kanban")

    def test_phases가_없는_이름도_저장된다(self):
        a = self.doing()
        rc, _, _ = _run(["board", "link", REPO, a, "없는-task-이름"])
        self.assertEqual(rc, 0)
        self.assertEqual(self.raw(a)["task"], "없는-task-이름")

    def test_경로_탈출_task와_id는_거절하고_파일이_그대로다(self):
        a = self.doing()
        before = self.snapshot()
        for args in ((REPO, a, "../x"), (REPO, a, "a/b"), (REPO, a, ".."), (REPO, "../x", "ok")):
            with self.subTest(args=args):
                rc, _, _ = _run(["board", "link", *args])
                self.assertNotEqual(rc, 0)
        self.assertEqual(before, self.snapshot())

    def test_없는_카드는_거절한다(self):
        rc, _, err = _run(["board", "link", REPO, "1800000000-abcd", "t"])
        self.assertNotEqual(rc, 0)
        self.assertEqual(len(err.strip().splitlines()), 1)

    def test_링크_파일과_요청_파일은_건드리지_않는다(self):
        a = self.planned()
        board.request_start(REPO, a, NOW + 1)
        board.add_ref(REPO, a, "참고", "https://example.com/doc")
        before = {k: v for k, v in self.snapshot().items() if k != f"{a}.json"}
        _run(["board", "link", REPO, a, "t"])
        after = {k: v for k, v in self.snapshot().items() if k != f"{a}.json"}
        self.assertEqual(before, after)


class 경계(_Case):
    def test_board_서브커맨드_없이는_거절한다(self):
        rc, _, _ = _run(["board"])
        self.assertNotEqual(rc, 0)

    def test_board_코드는_서브프로세스와_HTTP를_부르지_않는다(self):
        src = (Path(__file__).resolve().parent.parent / "scripts" / "desk.py").read_text(encoding="utf-8")
        for word in ("subprocess", "os.system", "urllib", "http.client", "socket"):
            self.assertNotIn(word, src)


if __name__ == "__main__":
    unittest.main()
