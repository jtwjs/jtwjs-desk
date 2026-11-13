"""desk/signal.py 순수 함수 테스트. 픽스처는 전부 지어낸 원장이다.

엣지 5축: 빈 값(빈 원장) · 비정상 입력(깨진 줄) · 실패 경로(해당 없음: 순수 함수)
 · 상태 전이(연속·재요구) · 동시성(해당 없음: 순수 함수)
"""
import json
import unittest

from desk import signal


def row(ts="t0", repo="repo-a", task="task-1", gate=None, area="FE", hyp=False,
        rec=False, acc=False, why=False, rebut=False, skip=False, **extra):
    r = {"ts": ts, "repo": repo, "task": task, "gate": gate, "area": area,
         "hyp": hyp, "rec": rec, "acc": acc, "why": why, "rebut": rebut, "skip": skip}
    r.update(extra)
    return r


def hit(ref, value, by="model"):
    return {"ref": ref, "hit": value, "by": by}


def jsonl(*rows):
    return "\n".join(r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)
                     for r in rows) + "\n"


def compute(*rows, broken=None, threshold=None):
    return signal.compute_signal(list(rows), broken or [], threshold)


def accept(ts, **kw):
    """게이트가 있고 추천을 받아 이유 없이 수락한 줄."""
    return row(ts=ts, gate="design", rec=True, acc=True, why=False, **kw)


class 원장을_읽을_때(unittest.TestCase):
    def test_정상_줄은_순서대로_파싱된다(self):
        rows, broken = signal.parse_ledger(jsonl(row(ts="a"), row(ts="b")))
        self.assertEqual([r["ts"] for r in rows], ["a", "b"])
        self.assertEqual(broken, [])

    def test_빈_텍스트는_빈_결과다(self):
        self.assertEqual(signal.parse_ledger(""), ([], []))

    def test_빈_줄은_무시한다(self):
        rows, broken = signal.parse_ledger("\n" + jsonl(row(ts="a")) + "\n\n")
        self.assertEqual(len(rows), 1)
        self.assertEqual(broken, [])

    def test_깨진_줄은_줄번호와_이유를_남기고_건너뛴다(self):
        text = jsonl(row(ts="a"), "{깨진", row(ts="b"), "[1, 2]")
        rows, broken = signal.parse_ledger(text)
        self.assertEqual([r["ts"] for r in rows], ["a", "b"])
        self.assertEqual(broken, [{"line": 2, "reason": "JSON 아님"},
                                  {"line": 4, "reason": "객체 아님"}])

    def test_수정_후보_키는_만들지_않는다(self):
        _, broken = signal.parse_ledger("{깨진\n")
        self.assertNotIn("fix", broken[0])


class 영역_건수와_적중을_셀_때(unittest.TestCase):
    def test_영역별_입력_건수와_적중_세_값을_센다(self):
        rows = [
            row(ts="1", area="FE", hyp=True), row(ts="2", area="FE", hyp=True),
            row(ts="3", area="FE", hyp=True), row(ts="4", area="BE", hyp=True),
            row(ts="5", area="infra", gate="x"), row(ts="6", area="domain", rec=True),
            hit("1", "right"), hit("2", "partial"), hit("4", "wrong"),
        ]
        a = compute(*rows)["areas"]
        self.assertEqual(set(a), {"FE", "BE", "infra", "domain"})
        self.assertEqual((a["FE"]["count"], a["FE"]["right"], a["FE"]["partial"],
                          a["FE"]["wrong"], a["FE"]["pending"]), (3, 1, 1, 0, 1))
        self.assertEqual((a["BE"]["count"], a["BE"]["wrong"], a["BE"]["pending"]), (1, 1, 0))
        self.assertEqual((a["infra"]["count"], a["infra"]["pending"]), (1, 0))
        self.assertEqual(a["domain"]["count"], 1)

    def test_같은_ref가_여러_줄이면_마지막_줄만_센다(self):
        rows = [row(ts="1", hyp=True), hit("1", "wrong"), hit("1", "right")]
        fe = compute(*rows)["areas"]["FE"]
        self.assertEqual((fe["right"], fe["wrong"], fe["partial"], fe["pending"]), (1, 0, 0, 0))

    def test_없는_ref는_건너뛰고_세지_않는다(self):
        rows = [row(ts="1", hyp=True), hit("zzz", "right")]
        fe = compute(*rows)["areas"]["FE"]
        self.assertEqual((fe["right"], fe["pending"]), (0, 1))

    def test_적중_줄은_입력_건수와_의미_있는_줄에_들지_않는다(self):
        r = compute(row(ts="1", hyp=True), hit("1", "right"))
        self.assertEqual(r["meaningful"], 1)
        self.assertEqual(r["areas"]["FE"]["count"], 1)

    def test_unknown이거나_빈_영역은_unknown_area로_센다(self):
        r = compute(row(ts="1", area="unknown", hyp=True), row(ts="2", area=None, hyp=True),
                    row(ts="3", area="FE", hyp=True), row(ts="4", area="unknown"))
        self.assertEqual(r["unknown_area"], 2)
        self.assertEqual(r["meaningful"], 3)

    def test_영역별_이유_없이_수락은_영역_안에서_센다(self):
        r = compute(accept("1", area="FE"), row(ts="2", area="FE", gate="d", rec=True, acc=True, why=True),
                    accept("3", area="BE"))
        self.assertEqual(r["areas"]["FE"]["acc_no_reason"], {"n": 1, "m": 2, "pct": 50})
        self.assertEqual(r["areas"]["BE"]["acc_no_reason"], {"n": 1, "m": 1, "pct": 100})
        self.assertEqual(r["areas"]["infra"]["acc_no_reason"], {"n": 0, "m": 0, "pct": None})


class 가설_먼저를_셀_때(unittest.TestCase):
    def _ten(self):
        return ([row(ts=f"h{i}", hyp=True) for i in range(3)]
                + [row(ts=f"o{i}", gate="design") for i in range(7)])

    def test_의미_있는_줄_10줄_중_가설_3줄이면_30퍼센트다(self):
        self.assertEqual(compute(*self._ten())["hyp_first"], {"n": 3, "m": 10, "pct": 30})

    def test_세_칸이_빈_줄을_섞어도_값이_같다(self):
        empties = [row(ts=f"e{i}", area=None) for i in range(5)]
        r = compute(*(self._ten() + empties))
        self.assertEqual(r["hyp_first"], {"n": 3, "m": 10, "pct": 30})
        self.assertEqual(r["meaningful"], 10)

    def test_게이트만_채운_건너뜀_줄은_분모에_든다(self):
        r = compute(row(ts="1", hyp=True), row(ts="2", gate="design", skip=True))
        self.assertEqual(r["hyp_first"], {"n": 1, "m": 2, "pct": 50})

    def test_의미_있는_줄이_0이면_pct는_null이다(self):
        r = compute(row(ts="1", area=None))
        self.assertEqual(r["hyp_first"], {"n": 0, "m": 0, "pct": None})
        self.assertIsNone(compute()["hyp_first"]["pct"])


class 이유_없이_수락을_셀_때(unittest.TestCase):
    def test_4줄_중_1줄이면_25퍼센트다(self):
        rows = [accept("1"),
                row(ts="2", gate="d", rec=True, acc=True, why=True),
                row(ts="3", gate="d", rec=True, acc=False),
                row(ts="4", gate="d", rec=True, acc=False, why=True)]
        self.assertEqual(compute(*rows)["acc_no_reason"], {"n": 1, "m": 4, "pct": 25})

    def test_gate가_null인_줄을_섞어도_값이_같다(self):
        rows = [accept("1"), row(ts="2", gate="d", rec=True, acc=False),
                row(ts="3", gate="d", rec=True, acc=False), row(ts="4", gate="d", rec=True, why=True)]
        base = compute(*rows)["acc_no_reason"]
        mixed = compute(*(rows + [row(ts="5", gate=None, rec=True, acc=True),
                                  row(ts="6", gate=None, rec=True, acc=True, why=True)]))
        self.assertEqual(mixed["acc_no_reason"], base)
        self.assertEqual(base, {"n": 1, "m": 4, "pct": 25})

    def test_분모가_0이면_null이다(self):
        r = compute(row(ts="1", gate=None, rec=True, acc=True))
        self.assertEqual(r["acc_no_reason"], {"n": 0, "m": 0, "pct": None})


class 연속을_셀_때(unittest.TestCase):
    def test_같은_작업에서_이유_없이_수락_3번이면_3이다(self):
        self.assertEqual(compute(accept("1"), accept("2"), accept("3"))["streak"], 3)

    def test_이유를_쓴_줄은_연속을_0으로_만든다(self):
        r = compute(accept("1"), accept("2"), row(ts="3", gate="d", why=True))
        self.assertEqual(r["streak"], 0)

    def test_작업이_바뀌면_0부터_다시_센다(self):
        r = compute(accept("1"), accept("2"), accept("3", task="task-2"))
        self.assertEqual(r["streak"], 1)

    def test_레포가_다르면_같은_task_이름도_다른_작업이다(self):
        r = compute(accept("1"), accept("2", repo="repo-b"))
        self.assertEqual(r["streak"], 1)

    def test_식별이_빈_줄은_세지도_끊지도_않는다(self):
        r = compute(accept("1"), accept("2"), row(ts="3", task=None, gate="d", rec=True, acc=True),
                    accept("4"))
        self.assertEqual(r["streak"], 3)
        self.assertEqual(r["no_ident"], 1)

    def test_task가_빈_문자열이어도_식별_없음이다(self):
        r = compute(accept("1"), row(ts="2", task="", gate="d", why=True), accept("3"))
        self.assertEqual((r["streak"], r["no_ident"]), (2, 1))

    def test_적중_줄은_식별_없는_줄로_세지_않는다(self):
        r = compute(accept("1"), hit("1", "right"))
        self.assertEqual(r["no_ident"], 0)


class 건너뜀을_셀_때(unittest.TestCase):
    def test_건너뜀_예_줄_수와_같다(self):
        r = compute(row(ts="1", gate="d", skip=True), row(ts="2", gate="d", skip=True),
                    row(ts="3", gate="d"), row(ts="4", task=None, gate="d", skip=True))
        self.assertEqual(r["skipped"], 3)


class 재요구_상태를_셀_때(unittest.TestCase):
    def test_기준_2에서_이유_없이_수락_2번이면_켜진다(self):
        self.assertTrue(compute(accept("1"), accept("2"), threshold=2)["reasked"])
        self.assertFalse(compute(accept("1"), threshold=2)["reasked"])

    def test_기준이_None이면_항상_꺼져_있다(self):
        self.assertFalse(compute(accept("1"), accept("2"), accept("3"), threshold=None)["reasked"])

    def test_이유만_쓴_줄이_와도_켜진_채_유지되고_연속만_0이다(self):
        r = compute(accept("1"), accept("2"), row(ts="3", gate="d", why=True), threshold=2)
        self.assertTrue(r["reasked"])
        self.assertEqual(r["streak"], 0)

    def test_가설_줄과_반박_줄이_순서_무관으로_나오면_둘째_줄에서_꺼진다(self):
        on = [accept("1"), accept("2")]
        hyp_only = compute(*on, row(ts="3", hyp=True), threshold=2)
        self.assertTrue(hyp_only["reasked"])
        self.assertFalse(compute(*on, row(ts="3", hyp=True), row(ts="4", rebut=True),
                                 threshold=2)["reasked"])
        self.assertFalse(compute(*on, row(ts="3", rebut=True), row(ts="4", hyp=True),
                                 threshold=2)["reasked"])

    def test_한_줄에_가설과_반박이_같이_있어도_꺼진다(self):
        r = compute(accept("1"), accept("2"), row(ts="3", hyp=True, rebut=True), threshold=2)
        self.assertFalse(r["reasked"])

    def test_켜진_뒤_작업이_바뀌면_모은_것을_버린다(self):
        r = compute(accept("1"), accept("2"), row(ts="3", hyp=True),
                    row(ts="4", task="task-2", rebut=True), threshold=2)
        self.assertTrue(r["reasked"])

    def test_식별_없는_줄은_모으기에_넣지도_끊지도_않는다(self):
        r = compute(accept("1"), accept("2"), row(ts="3", hyp=True),
                    row(ts="4", task=None, rebut=True), threshold=2)
        self.assertTrue(r["reasked"])
        r2 = compute(accept("1"), accept("2"), row(ts="3", hyp=True),
                     row(ts="4", task=None, rebut=True), row(ts="5", rebut=True), threshold=2)
        self.assertFalse(r2["reasked"])

    def test_켜지기_전의_가설_줄은_모으지_않는다(self):
        r = compute(row(ts="0", hyp=True), accept("1"), accept("2"), row(ts="3", rebut=True),
                    threshold=2)
        self.assertTrue(r["reasked"])


class 식별_없는_줄이_끼었을_때(unittest.TestCase):
    def test_a_수락_a_수락_빈_줄_a_수락은_연속_3이다(self):
        r = compute(accept("1", task="a"), accept("2", task="a"),
                    row(ts="3", task=None, gate="d", rec=True, acc=True),
                    accept("4", task="a"))
        self.assertEqual(r["streak"], 3)
        self.assertEqual(r["no_ident"], 1)


class 깨진_줄과_빈_원장일_때(unittest.TestCase):
    def test_깨진_줄은_그대로_응답에_싣고_나머지로_계산한다(self):
        rows, broken = signal.parse_ledger(jsonl(row(ts="1", hyp=True), "{깨짐"))
        r = signal.compute_signal(rows, broken)
        self.assertEqual(r["broken"], [{"line": 2, "reason": "JSON 아님"}])
        self.assertEqual(r["hyp_first"]["n"], 1)

    def test_맡김_줄이_0건이면_empty_true다(self):
        r = compute()
        self.assertTrue(r["empty"])
        self.assertEqual((r["meaningful"], r["streak"], r["skipped"], r["no_ident"]), (0, 0, 0, 0))
        self.assertFalse(compute(row(ts="1"))["empty"])

    def test_적중_줄만_있으면_맡김_줄이_0건이다(self):
        self.assertTrue(compute(hit("1", "right"))["empty"])

    def test_누락_키는_빈_값으로_읽는다(self):
        r = compute({"ts": "1", "gate": "d"})
        self.assertEqual(r["meaningful"], 1)
        self.assertEqual(r["unknown_area"], 1)

    def test_계약_키_이름이_정본과_같다(self):
        self.assertEqual(set(compute()), {"areas", "unknown_area", "hyp_first", "acc_no_reason",
                                          "streak", "reasked", "skipped", "no_ident", "broken",
                                          "meaningful", "empty"})
        self.assertEqual(set(compute()["areas"]["FE"]),
                         {"count", "right", "partial", "wrong", "pending", "acc_no_reason"})


class 원문이_섞였을_때(unittest.TestCase):
    def test_원문_칸의_값은_응답에_실리지_않는다(self):
        secret = "비밀원문-XYZ"
        r = compute(row(ts="1", gate="d", hyp=True, why=True, hyp_text=secret, why_text=secret,
                        note=secret))
        self.assertNotIn(secret, json.dumps(r, ensure_ascii=False))

    def test_문자열_값을_가진_칸도_원문으로_싣지_않는다(self):
        secret = "비밀원문-XYZ"
        r = compute(row(ts="1", gate="d", hyp=secret, why=secret, rec=secret))
        self.assertNotIn(secret, json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
