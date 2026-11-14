"""desk/board.py 응답 조립(build_view · build_card_detail) 단위 테스트 — 순수 함수, 파일 없음.

픽스처는 지어낸 레포·카드·example.com 링크다.
"""
import unittest
from datetime import date, datetime

from desk import board

TODAY = date(2026, 11, 14)


def ts(y, m, d, h=12):
    return datetime(y, m, d, h).timestamp()


def card(cid, title, column="planned", **kw):
    base = {"id": cid, "title": title, "note": "", "column": column, "task": None,
            "created_at": ts(2026, 11, 1), "doing_at": None, "pr_at": None, "done_at": None,
            "archived_at": None, "requested_at": None, "request_broken": False,
            "refs_broken": False}
    base.update(kw)
    return base


def view(cards_by_repo, phases_by_repo=None, query=None):
    return board.build_view(cards_by_repo, phases_by_repo or {}, TODAY, ts(2026, 11, 14),
                            query or {})


def titles(v, col):
    return [c["title"] for c in v["columns"][col]["cards"]]


def phase(*statuses, summaries=None):
    return {"steps": [{"step": i + 1, "name": f"s{i + 1}", "status": s,
                       "summary": (summaries or {}).get(i)} for i, s in enumerate(statuses)]}


class TestBuildView(unittest.TestCase):
    def test_열_3개로_묶는다(self):
        v = view({"alpha": ([card("1-aaaa", "a"), card("2-aaaa", "b", "doing", doing_at=ts(2026, 11, 2)),
                             card("3-aaaa", "c", "done", done_at=ts(2026, 11, 3))], 0)})
        self.assertEqual(set(v["columns"]), {"planned", "doing", "done"})
        self.assertEqual(titles(v, "planned"), ["a"])
        self.assertEqual(titles(v, "doing"), ["b"])
        self.assertEqual(titles(v, "done"), ["c"])

    def test_카드_0장이면_열이_비어_있다(self):
        v = view({"alpha": ([], 0)})
        for col in board.COLUMNS:
            self.assertEqual(v["columns"][col], {"cards": [], "count": 0, "total": 0})
        self.assertEqual(v["broken"], 0)
        self.assertFalse(v["archived"])

    def test_보관_카드는_기본에서_빠지고_archived에서만_나온다(self):
        cards = [card("1-aaaa", "보통"), card("2-aaaa", "보관", "doing", doing_at=ts(2026, 11, 2),
                                             archived_at=ts(2026, 11, 5))]
        v = view({"alpha": (cards, 0)})
        self.assertEqual(titles(v, "planned"), ["보통"])
        self.assertEqual(titles(v, "doing"), [])
        self.assertEqual(v["columns"]["doing"]["total"], 0)
        va = view({"alpha": (cards, 0)}, query={"archived": "1"})
        self.assertEqual(titles(va, "planned"), [])
        self.assertEqual(titles(va, "doing"), ["보관"])
        self.assertTrue(va["archived"])

    def test_보관_후_되살리면_목록이_바뀐다(self):
        c = card("1-aaaa", "x", "done", done_at=ts(2026, 11, 2), archived_at=ts(2026, 11, 3))
        self.assertEqual(titles(view({"alpha": ([c], 0)}), "done"), [])
        c2 = {**c, "archived_at": None}
        self.assertEqual(titles(view({"alpha": ([c2], 0)}), "done"), ["x"])

    def test_repo_필터(self):
        v = view({"alpha": ([card("1-aaaa", "a1")], 0), "beta": ([card("2-aaaa", "b1")], 0)},
                 query={"repo": "beta"})
        self.assertEqual(titles(v, "planned"), ["b1"])
        self.assertEqual(v["columns"]["planned"]["count"], 1)
        self.assertEqual(v["columns"]["planned"]["total"], 2)
        self.assertEqual(v["columns"]["planned"]["cards"][0]["repo"], "beta")

    def test_모르는_repo는_BadQuery다(self):
        with self.assertRaises(board.BadQuery):
            view({"alpha": ([], 0)}, query={"repo": "nope"})

    def test_잘못된_날짜는_BadQuery다(self):
        for q in ({"from": "2026-13-01"}, {"to": "11/14"}, {"from": "abc"}):
            with self.assertRaises(board.BadQuery, msg=str(q)):
                view({"alpha": ([], 0)}, query=q)

    def test_from이_to보다_크면_BadQuery다(self):
        with self.assertRaises(board.BadQuery):
            view({"alpha": ([], 0)}, query={"from": "2026-11-10", "to": "2026-11-09"})

    def test_모르는_sort는_BadQuery다(self):
        for key in ("sort_planned", "sort_doing", "sort_done"):
            with self.assertRaises(board.BadQuery, msg=key):
                view({"alpha": ([], 0)}, query={key: "sideways"})

    def test_기간은_열별_기준일로_건다_경계_포함(self):
        cards = [
            card("1-aaaa", "p-in", created_at=ts(2026, 11, 10)),
            card("2-aaaa", "p-out", created_at=ts(2026, 11, 9, 23)),
            card("3-aaaa", "d", "doing", created_at=ts(2026, 10, 1), doing_at=ts(2026, 11, 12)),
            card("4-aaaa", "n", "done", created_at=ts(2026, 10, 1), doing_at=ts(2026, 10, 2),
                 done_at=ts(2026, 11, 14, 23)),
        ]
        v = view({"alpha": (cards, 0)}, query={"from": "2026-11-10", "to": "2026-11-14"})
        self.assertEqual(titles(v, "planned"), ["p-in"])
        self.assertEqual(titles(v, "doing"), ["d"])
        self.assertEqual(titles(v, "done"), ["n"])

    def test_예정_만든_날과_진행_시작일이_갈리면_열별로_다르게_걸린다(self):
        c_plan = card("1-aaaa", "plan", created_at=ts(2026, 11, 1))
        c_doing = card("2-aaaa", "doing", "doing", created_at=ts(2026, 11, 1),
                       doing_at=ts(2026, 11, 12))
        v = view({"alpha": ([c_plan, c_doing], 0)}, query={"from": "2026-11-10"})
        self.assertEqual(titles(v, "planned"), [])
        self.assertEqual(titles(v, "doing"), ["doing"])

    def test_한쪽만_줘도_된다(self):
        cards = [card("1-aaaa", "old", created_at=ts(2026, 11, 1)),
                 card("2-aaaa", "new", created_at=ts(2026, 11, 12))]
        self.assertEqual(titles(view({"alpha": (cards, 0)}, query={"from": "2026-11-05"}),
                                "planned"), ["new"])
        self.assertEqual(titles(view({"alpha": (cards, 0)}, query={"to": "2026-11-05"}),
                                "planned"), ["old"])

    def test_q는_제목에만_걸리고_대소문자를_무시한다(self):
        cards = [card("1-aaaa", "Fix Login Bug", note="상세"), card("2-aaaa", "다른 일", note="login 언급")]
        v = view({"alpha": (cards, 0)}, query={"q": "LOGIN"})
        self.assertEqual(titles(v, "planned"), ["Fix Login Bug"])

    def test_공백뿐인_q는_필터_없음이다(self):
        cards = [card("1-aaaa", "a"), card("2-aaaa", "b")]
        self.assertEqual(len(view({"alpha": (cards, 0)}, query={"q": "   "})["columns"]["planned"]["cards"]), 2)
        self.assertEqual(len(view({"alpha": (cards, 0)}, query={"q": ""})["columns"]["planned"]["cards"]), 2)

    def test_q와_repo와_기간은_AND다(self):
        a = [card("1-aaaa", "배포 점검", created_at=ts(2026, 11, 10)),
             card("2-aaaa", "배포 정리", created_at=ts(2026, 11, 1)),
             card("3-aaaa", "문서", created_at=ts(2026, 11, 10))]
        b = [card("4-aaaa", "배포 점검", created_at=ts(2026, 11, 10))]
        v = view({"alpha": (a, 0), "beta": (b, 0)},
                 query={"q": "배포", "repo": "alpha", "from": "2026-11-05"})
        self.assertEqual(titles(v, "planned"), ["배포 점검"])
        self.assertEqual(v["columns"]["planned"]["count"], 1)
        self.assertEqual(v["columns"]["planned"]["total"], 4)

    def test_count와_total은_필터가_뺄_때_다르다(self):
        cards = [card("1-aaaa", "a"), card("2-aaaa", "b"), card("3-aaaa", "c")]
        v = view({"alpha": (cards, 0)}, query={"q": "a"})
        self.assertEqual(v["columns"]["planned"]["count"], 1)
        self.assertEqual(v["columns"]["planned"]["total"], 3)
        self.assertEqual(v["columns"]["doing"]["count"], 0)
        self.assertEqual(v["columns"]["doing"]["total"], 0)

    def test_total은_보관_기준이_같다(self):
        cards = [card("1-aaaa", "a"), card("2-aaaa", "b", "doing", doing_at=ts(2026, 11, 2),
                                          archived_at=ts(2026, 11, 3))]
        self.assertEqual(view({"alpha": (cards, 0)})["columns"]["doing"]["total"], 0)
        self.assertEqual(view({"alpha": (cards, 0)}, query={"archived": "1"})["columns"]["doing"]["total"], 1)
        self.assertEqual(view({"alpha": (cards, 0)}, query={"archived": "1"})["columns"]["planned"]["total"], 0)

    def test_카드_목록은_자르지_않는다(self):
        cards = [card(f"{i}-aaaa", f"t{i}", created_at=ts(2026, 11, 1) + i) for i in range(1, 8)]
        v = view({"alpha": (cards, 0)})
        self.assertEqual(len(v["columns"]["planned"]["cards"]), 7)
        self.assertEqual(v["columns"]["planned"]["count"], 7)
        self.assertEqual(v["columns"]["planned"]["total"], 7)

    def test_기본_정렬은_예정_진행_오래된순_완료_최신순이다(self):
        planned = [card("1-aaaa", "p2", created_at=ts(2026, 11, 5)),
                   card("2-aaaa", "p1", created_at=ts(2026, 11, 2))]
        doing = [card("3-aaaa", "d2", "doing", doing_at=ts(2026, 11, 6)),
                 card("4-aaaa", "d1", "doing", doing_at=ts(2026, 11, 3))]
        done = [card("5-aaaa", "n1", "done", done_at=ts(2026, 11, 3)),
                card("6-aaaa", "n2", "done", done_at=ts(2026, 11, 7))]
        v = view({"alpha": (planned + doing + done, 0)})
        self.assertEqual(titles(v, "planned"), ["p1", "p2"])
        self.assertEqual(titles(v, "doing"), ["d1", "d2"])
        self.assertEqual(titles(v, "done"), ["n2", "n1"])

    def test_sort로_뒤집는다(self):
        planned = [card("1-aaaa", "p2", created_at=ts(2026, 11, 5)),
                   card("2-aaaa", "p1", created_at=ts(2026, 11, 2))]
        doing = [card("3-aaaa", "d2", "doing", doing_at=ts(2026, 11, 6)),
                 card("4-aaaa", "d1", "doing", doing_at=ts(2026, 11, 3))]
        done = [card("5-aaaa", "n1", "done", done_at=ts(2026, 11, 3)),
                card("6-aaaa", "n2", "done", done_at=ts(2026, 11, 7))]
        v = view({"alpha": (planned + doing + done, 0)},
                 query={"sort_planned": "new", "sort_doing": "new", "sort_done": "old"})
        self.assertEqual(titles(v, "planned"), ["p2", "p1"])
        self.assertEqual(titles(v, "doing"), ["d2", "d1"])
        self.assertEqual(titles(v, "done"), ["n1", "n2"])

    def test_한_열만_sort를_줘도_나머지는_기본이다(self):
        planned = [card("1-aaaa", "p2", created_at=ts(2026, 11, 5)),
                   card("2-aaaa", "p1", created_at=ts(2026, 11, 2))]
        done = [card("5-aaaa", "n1", "done", done_at=ts(2026, 11, 3)),
                card("6-aaaa", "n2", "done", done_at=ts(2026, 11, 7))]
        v = view({"alpha": (planned + done, 0)}, query={"sort_planned": "new"})
        self.assertEqual(titles(v, "planned"), ["p2", "p1"])
        self.assertEqual(titles(v, "done"), ["n2", "n1"])

    def test_PR_대기_카드는_어느_정렬에서도_진행_맨_위다(self):
        doing = [card("1-aaaa", "early", "doing", doing_at=ts(2026, 11, 1)),
                 card("2-aaaa", "pr", "doing", doing_at=ts(2026, 11, 5), pr_at=ts(2026, 11, 8)),
                 card("3-aaaa", "late", "doing", doing_at=ts(2026, 11, 9))]
        for sort, expect in (("old", ["pr", "early", "late"]), ("new", ["pr", "late", "early"])):
            v = view({"alpha": (doing, 0)}, query={"sort_doing": sort})
            self.assertEqual(titles(v, "doing"), expect, sort)
            self.assertTrue(v["columns"]["doing"]["cards"][0]["pr_waiting"])

    def test_요청_배지는_예정_카드에만_붙는다(self):
        cards = [card("1-aaaa", "req", requested_at=ts(2026, 11, 13)),
                 card("2-aaaa", "no"),
                 card("3-aaaa", "moved", "doing", doing_at=ts(2026, 11, 14), requested_at=ts(2026, 11, 13))]
        v = view({"alpha": (cards, 0)})
        by = {c["title"]: c for col in board.COLUMNS for c in v["columns"][col]["cards"]}
        self.assertEqual(by["req"]["badge"], "requested")
        self.assertIsNone(by["no"]["badge"])
        self.assertIsNone(by["moved"]["badge"])

    def test_경과_일수는_진행_카드만이고_PR_대기면_pr_at부터다(self):
        cards = [card("1-aaaa", "d", "doing", doing_at=ts(2026, 11, 10), requested_at=ts(2026, 11, 9)),
                 card("2-aaaa", "p", "doing", doing_at=ts(2026, 11, 10), requested_at=ts(2026, 11, 9),
                      pr_at=ts(2026, 11, 12)),
                 card("3-aaaa", "plan", requested_at=ts(2026, 11, 9)),
                 card("4-aaaa", "done", "done", done_at=ts(2026, 11, 10), requested_at=ts(2026, 11, 9))]
        v = view({"alpha": (cards, 0)})
        by = {c["title"]: c for col in board.COLUMNS for c in v["columns"][col]["cards"]}
        self.assertEqual(by["d"]["elapsed_days"], 5)
        self.assertEqual(by["p"]["elapsed_days"], 2)
        self.assertIsNone(by["plan"]["elapsed_days"])
        self.assertIsNone(by["done"]["elapsed_days"])

    def test_진행도와_후보_표식과_연결_상태(self):
        cards = [
            card("1-aaaa", "done-all", "doing", doing_at=ts(2026, 11, 2), task="t-done"),
            card("2-aaaa", "half", "doing", doing_at=ts(2026, 11, 3), task="t-half"),
            card("3-aaaa", "no-task", "doing", doing_at=ts(2026, 11, 4)),
            card("4-aaaa", "missing", "doing", doing_at=ts(2026, 11, 5), task="t-gone"),
            card("5-aaaa", "marked", "doing", doing_at=ts(2026, 11, 6), task="t-done", pr_at=ts(2026, 11, 7)),
            card("6-aaaa", "fin", "done", done_at=ts(2026, 11, 6), task="t-done"),
        ]
        phases = {"alpha": {"t-done": phase("completed", "completed"),
                            "t-half": phase("completed", "pending")}}
        v = view({"alpha": (cards, 0)}, phases, query={"sort_doing": "old"})
        by = {c["title"]: c for col in board.COLUMNS for c in v["columns"][col]["cards"]}
        self.assertEqual(by["done-all"]["progress"], {"done": 2, "total": 2})
        self.assertTrue(by["done-all"]["candidate"])
        self.assertIsNone(by["done-all"]["connection"])
        self.assertEqual(by["half"]["progress"], {"done": 1, "total": 2})
        self.assertFalse(by["half"]["candidate"])
        self.assertEqual(by["no-task"]["connection"], "designing")
        self.assertIsNone(by["no-task"]["progress"])
        self.assertEqual(by["missing"]["connection"], "disconnected")
        self.assertFalse(by["marked"]["candidate"])
        self.assertTrue(by["marked"]["pr_waiting"])
        self.assertFalse(by["fin"]["candidate"])
        self.assertIsNone(by["fin"]["connection"])

    def test_phases를_못_읽어도_터지지_않고_진행도와_후보만_빈다(self):
        cards = [card("1-aaaa", "a", "doing", doing_at=ts(2026, 11, 2), task="t1"),
                 card("2-aaaa", "b", "doing", doing_at=ts(2026, 11, 2))]
        for phases in ({}, {"alpha": None}):
            v = view({"alpha": (cards, 0)}, phases)
            by = {c["title"]: c for c in v["columns"]["doing"]["cards"]}
            self.assertIsNone(by["a"]["progress"])
            self.assertFalse(by["a"]["candidate"])
            self.assertEqual(by["b"]["connection"], "designing")

    def test_카드_필드가_갖춰져_있고_refs는_없다(self):
        c = card("1-aaaa", "t", note="메모", task=None, requested_at=ts(2026, 11, 13))
        got = view({"alpha": ([c], 0)})["columns"]["planned"]["cards"][0]
        for key in ("id", "repo", "title", "note", "column", "badge", "pr_waiting", "elapsed_days",
                    "progress", "candidate", "connection", "created_at", "requested_at", "doing_at",
                    "pr_at", "done_at", "archived_at", "task", "archived"):
            self.assertIn(key, got)
        self.assertNotIn("refs", got)
        self.assertEqual(got["repo"], "alpha")
        self.assertFalse(got["archived"])

    def test_보관_카드는_archived_표시가_true다(self):
        c = card("1-aaaa", "t", "done", done_at=ts(2026, 11, 2), archived_at=ts(2026, 11, 3))
        got = view({"alpha": ([c], 0)}, query={"archived": "1"})["columns"]["done"]["cards"][0]
        self.assertTrue(got["archived"])

    def test_broken은_깨진_카드_요청_링크_수의_합이다(self):
        cards = [card("1-aaaa", "a", request_broken=True),
                 card("2-aaaa", "b", refs_broken=True),
                 card("3-aaaa", "c", request_broken=True, refs_broken=True)]
        v = view({"alpha": (cards, 2), "beta": ([], 1)})
        self.assertEqual(v["broken"], 2 + 1 + 2 + 2)

    def test_깨진_카드만_있어도_나머지는_보인다(self):
        v = view({"alpha": ([card("1-aaaa", "ok")], 1)})
        self.assertEqual(titles(v, "planned"), ["ok"])
        self.assertEqual(v["broken"], 1)


class TestBuildCardDetail(unittest.TestCase):
    REFS = [{"id": "r1", "name": "스레드", "url": "https://example.com/t"}]

    def test_상세에_메모_날짜_refs_step_summary가_있다(self):
        c = card("1-aaaa", "t", "doing", note="메모", task="t1", doing_at=ts(2026, 11, 2),
                 requested_at=ts(2026, 11, 1))
        idx = {"summary": "전체 요약", **phase("completed", "pending", summaries={0: "첫 요약"})}
        d = board.build_card_detail(c, self.REFS, idx, TODAY)
        self.assertEqual(d["note"], "메모")
        self.assertEqual(d["refs"], [{"id": "r1", "name": "스레드", "url": "https://example.com/t"}])
        self.assertEqual(d["steps"][0], {"step": 1, "name": "s1", "status": "completed", "summary": "첫 요약"})
        self.assertEqual(d["steps"][1]["status"], "pending")
        self.assertEqual(d["phase_summary"], "전체 요약")
        for key in ("created_at", "requested_at", "doing_at", "pr_at", "done_at", "archived_at"):
            self.assertIn(key, d)
        self.assertEqual(d["elapsed_days"], 13)

    def test_task가_없으면_steps가_빈다(self):
        d = board.build_card_detail(card("1-aaaa", "t", "doing", doing_at=ts(2026, 11, 2)),
                                    [], phase("completed"), TODAY)
        self.assertEqual(d["steps"], [])
        self.assertEqual(d["refs"], [])

    def test_phases가_없으면_steps가_빈다(self):
        d = board.build_card_detail(card("1-aaaa", "t", "doing", task="t1", doing_at=ts(2026, 11, 2)),
                                    [], None, TODAY)
        self.assertEqual(d["steps"], [])
        self.assertIsNone(d["phase_summary"])


if __name__ == "__main__":
    unittest.main()
