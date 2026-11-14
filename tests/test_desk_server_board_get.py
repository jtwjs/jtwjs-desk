"""GET /board · GET /board/card (step 4) — 읽기 전용 칸반 엔드포인트.

엣지 5축: 빈 값(설정 없음 · 레포 0개 · 빈 q) · 비정상 입력(잘못된 날짜 · 모르는 레포 · 경로 탈출) ·
실패 경로(설정 없음 · phases 없음 · 없는 카드) · 상태 전이(보관 후 archived=1) · 동시성(해당 없음: 읽기 전용).
🔴 픽스처는 임시 폴더 안의 지어낸 레포 · 카드 · example.com 링크다.
"""
import json
import sys
import time
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_desk_server_review import _ReviewCase
from desk import board

DAY = 86400


def _snapshot(root: Path) -> dict:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


class _BoardCase(_ReviewCase):
    def setUp(self):
        super().setUp()
        self.now = time.time()
        self.repo = "fake-repo"
        self.board_root = self.home_dir / "board"
        self._write_cfg([self.repo_root])
        (self.repo_root / "phases" / "kan-task").mkdir(parents=True)
        (self.repo_root / "phases" / "kan-task" / "index.json").write_text(json.dumps({
            "summary": "샘플 phase 요약",
            "steps": [
                {"step": 1, "name": "첫 step", "status": "completed", "summary": "첫 요약"},
                {"step": 2, "name": "둘째 step", "status": "pending"},
            ]}), encoding="utf-8")

    def _seed(self):
        """예정 1(요청됨) · 진행 1(task 연결) · 완료 1."""
        b = board
        planned = b.add_card(self.repo, "예정 카드 Alpha", "메모 하나", self.now - 5 * DAY)
        b.request_start(self.repo, planned["id"], self.now - 3 * DAY)
        doing = b.add_card(self.repo, "진행 카드 Beta", "", self.now - 9 * DAY)
        b.request_start(self.repo, doing["id"], self.now - 4 * DAY)
        b.move_card(self.repo, doing["id"], "doing", self.now - 4 * DAY)
        b.set_task(self.repo, doing["id"], "kan-task")
        b.add_ref(self.repo, doing["id"], "참고 문서", "https://example.com/doc")
        done = b.add_card(self.repo, "완료 카드 Gamma", "", self.now - 12 * DAY)
        b.move_card(self.repo, done["id"], "doing", self.now - 10 * DAY)
        b.move_card(self.repo, done["id"], "done", self.now - 1 * DAY)
        return planned, doing, done

    def _titles(self, body, col):
        return [c["title"] for c in body["columns"][col]["cards"]]


class 통합_GET_board(_BoardCase):
    def test_카드_3장이_열별로_오고_화면이_읽는_필드가_값과_함께_있다(self):
        planned, doing, done = self._seed()
        status, body = self._get("/board")
        self.assertEqual(status, 200)
        self.assertEqual(self._titles(body, "planned"), ["예정 카드 Alpha"])
        self.assertEqual(self._titles(body, "doing"), ["진행 카드 Beta"])
        self.assertEqual(self._titles(body, "done"), ["완료 카드 Gamma"])
        p = body["columns"]["planned"]["cards"][0]
        self.assertEqual(p["badge"], "requested")
        d = body["columns"]["doing"]["cards"][0]
        self.assertEqual(d["elapsed_days"], 4)
        self.assertEqual(d["progress"], {"done": 1, "total": 2})
        self.assertIs(d["pr_waiting"], False)
        self.assertEqual(d["repo"], self.repo)
        self.assertEqual(body["columns"]["doing"]["count"], 1)
        self.assertEqual(body["columns"]["doing"]["total"], 1)
        self.assertEqual(body["broken"], 0)
        self.assertIs(body["archived"], False)

    def test_응답에_config와_레포_이름_목록이_있다(self):
        self._seed()
        _, body = self._get("/board")
        self.assertEqual(body["repos"], [self.repo])
        self.assertEqual(body["config"]["source"], "config")

    def test_q는_제목만_거르고_메모에만_있는_글자는_안_걸린다(self):
        self._seed()
        _, hit = self._get("/board?q=" + quote("ALPHA"))
        self.assertEqual(self._titles(hit, "planned"), ["예정 카드 Alpha"])
        self.assertEqual(self._titles(hit, "doing"), [])
        self.assertEqual(hit["columns"]["doing"]["total"], 1)
        _, memo = self._get("/board?q=" + quote("메모 하나"))
        self.assertEqual(self._titles(memo, "planned"), [])
        _, blank = self._get("/board?q=" + quote("   "))
        self.assertEqual(self._titles(blank, "planned"), ["예정 카드 Alpha"])

    def test_repo_필터는_그_레포만_낸다(self):
        self._seed()
        _, body = self._get(f"/board?repo={self.repo}")
        self.assertEqual(body["columns"]["planned"]["count"], 1)

    def test_기간_필터는_열별_기준일로_걸러내고_전체_건수는_그대로다(self):
        self._seed()
        import datetime
        # 진행 카드 doing_at = 4일 전, 예정 created_at = 5일 전, 완료 done_at = 1일 전
        frm = (datetime.date.today() - datetime.timedelta(days=2)).isoformat()
        _, body = self._get(f"/board?from={frm}")
        self.assertEqual(self._titles(body, "planned"), [])
        self.assertEqual(self._titles(body, "doing"), [])
        self.assertEqual(self._titles(body, "done"), ["완료 카드 Gamma"])
        self.assertEqual(body["columns"]["planned"]["total"], 1)

    def test_sort_파라미터가_열별_정렬을_바꾼다(self):
        board.add_card(self.repo, "오래된 것", "", self.now - 8 * DAY)
        board.add_card(self.repo, "새 것", "", self.now - 1 * DAY)
        _, default = self._get("/board")
        self.assertEqual(self._titles(default, "planned"), ["오래된 것", "새 것"])
        _, newest = self._get("/board?sort_planned=new")
        self.assertEqual(self._titles(newest, "planned"), ["새 것", "오래된 것"])

    def test_보관한_카드는_기본에서_빠지고_archived_1에서만_나온다(self):
        planned, doing, _ = self._seed()
        board.archive_card(self.repo, doing["id"], self.now)
        _, normal = self._get("/board")
        self.assertEqual(self._titles(normal, "doing"), [])
        _, arch = self._get("/board?archived=1")
        self.assertEqual(self._titles(arch, "doing"), ["진행 카드 Beta"])
        self.assertIs(arch["archived"], True)

    def test_잘못된_쿼리_4종은_400이고_예외_메시지에_경로가_없다(self):
        self._seed()
        for qs in ("repo=nope-repo", "from=2026-13-40", "from=2026-11-10&to=2026-11-01",
                   "sort_doing=sideways"):
            with self.subTest(qs=qs):
                status, body = self._get("/board?" + qs)
                self.assertEqual(status, 400)
                self.assertIn("error", body)
                self.assertNotIn(self._tmp.name, json.dumps(body, ensure_ascii=False))

    def test_깨진_카드_파일은_그_카드만_빠지고_broken에_센다(self):
        self._seed()
        d = self.board_root / self.repo
        (d / "9999999999-abcd.json").write_text("{깨짐", encoding="utf-8")
        status, body = self._get("/board")
        self.assertEqual(status, 200)
        self.assertEqual(body["broken"], 1)
        self.assertEqual(self._titles(body, "planned"), ["예정 카드 Alpha"])

    def test_phases_폴더가_없는_레포도_200이고_진행도만_비어_있다(self):
        import shutil
        self._seed()
        shutil.rmtree(self.repo_root / "phases")
        status, body = self._get("/board")
        self.assertEqual(status, 200)
        d = body["columns"]["doing"]["cards"][0]
        self.assertNotEqual(d["progress"], {"done": 1, "total": 2})

    def test_GET은_board_폴더를_바꾸지_않는다(self):
        self._seed()
        before = _snapshot(self.board_root)
        self._get("/board")
        self._get("/board?archived=1&q=a")
        self.assertEqual(_snapshot(self.board_root), before)

    def test_응답에_가짜_경로_문자열이_없다(self):
        self._seed()
        self.assertTrue(self._get("/board")[0] == 200)
        raw = json.dumps(self._get("/board")[1], ensure_ascii=False)
        self.assertNotIn(self._tmp.name, raw)

    def test_설정이_없으면_columns가_비어_있고_200이다(self):
        self.cfg_path.unlink()
        status, body = self._get("/board")
        self.assertEqual(status, 200)
        self.assertEqual(body["config"]["source"], "none")
        for col in ("planned", "doing", "done"):
            self.assertEqual(body["columns"][col]["cards"], [])
        self.assertEqual(body["repos"], [])

    def test_레포가_0개여도_200이다(self):
        self._write_cfg([])
        status, body = self._get("/board")
        self.assertEqual(status, 200)
        self.assertEqual(body["repos"], [])
        self.assertEqual(body["columns"]["planned"]["cards"], [])

    def test_이름이_거절되는_레포가_있어도_200이고_다른_레포는_정상이다(self):
        planned, _, _ = self._seed()
        weird = Path(self._tmp.name) / "my..repo"
        weird.mkdir()
        self._write_cfg([weird, self.repo_root])
        status, body = self._get("/board")
        self.assertEqual(status, 200)
        self.assertEqual(body["broken"], 1)
        self.assertIn("예정 카드 Alpha", self._titles(body, "planned"))
        self.assertEqual(len(body["columns"]["doing"]["cards"]), 1)

    def test_nav_counts_키_집합은_그대로다(self):
        _, counts = self._get("/nav-counts")
        self.assertEqual(set(counts), {"judge", "review", "routine", "trends", "errors"})

    def test_Host가_다르면_403이다(self):
        status, _ = self._get_raw_host("/board", "evil.example:1")
        self.assertEqual(status, 403)


class 통합_GET_board_card(_BoardCase):
    def test_링크와_step_summary를_준다(self):
        _, doing, _ = self._seed()
        status, body = self._get(f"/board/card?repo={self.repo}&id={doing['id']}")
        self.assertEqual(status, 200)
        self.assertEqual(body["title"], "진행 카드 Beta")
        self.assertEqual(body["refs"][0]["name"], "참고 문서")
        self.assertEqual(body["refs"][0]["url"], "https://example.com/doc")
        self.assertEqual(body["steps"][0]["summary"], "첫 요약")
        self.assertEqual(body["steps"][0]["status"], "completed")
        self.assertEqual(body["phase_summary"], "샘플 phase 요약")
        self.assertNotIn(self._tmp.name, json.dumps(body, ensure_ascii=False))

    def test_task가_없는_카드는_step이_비어_있다(self):
        planned, _, _ = self._seed()
        status, body = self._get(f"/board/card?repo={self.repo}&id={planned['id']}")
        self.assertEqual(status, 200)
        self.assertEqual(body["steps"], [])
        self.assertEqual(body["note"], "메모 하나")

    def test_없는_카드는_404다(self):
        self._seed()
        status, body = self._get(f"/board/card?repo={self.repo}&id=1-abcd")
        self.assertEqual(status, 404)
        self.assertIn("error", body)

    def test_알려진_레포여도_없는_레포_이름은_404다(self):
        self._seed()
        status, _ = self._get("/board/card?repo=nope-repo&id=1-abcd")
        self.assertEqual(status, 404)

    def test_경로_탈출과_잘못된_id는_400이다(self):
        self._seed()
        for qs in ("repo=..&id=1-abcd", "repo=" + quote("../x") + "&id=1-abcd",
                   f"repo={self.repo}&id=" + quote("../../etc/passwd"),
                   f"repo={self.repo}&id=bad", f"repo={self.repo}", "id=1-abcd"):
            with self.subTest(qs=qs):
                status, body = self._get("/board/card?" + qs)
                self.assertEqual(status, 400)
                self.assertIn("error", body)

    def test_phases가_없어도_200이다(self):
        import shutil
        _, doing, _ = self._seed()
        shutil.rmtree(self.repo_root / "phases")
        status, body = self._get(f"/board/card?repo={self.repo}&id={doing['id']}")
        self.assertEqual(status, 200)
        self.assertEqual(body["steps"], [])

    def test_설정이_없으면_카드를_못_찾아_404다(self):
        self.cfg_path.unlink()
        status, _ = self._get(f"/board/card?repo={self.repo}&id=1-abcd")
        self.assertEqual(status, 404)

    def test_GET은_board_폴더를_바꾸지_않는다(self):
        _, doing, _ = self._seed()
        before = _snapshot(self.board_root)
        self._get(f"/board/card?repo={self.repo}&id={doing['id']}")
        self.assertEqual(_snapshot(self.board_root), before)


class 통합_GET_board_card_요청_시각(_BoardCase):
    """step 11 — 상세 응답이 목록(GET /board)과 같은 requested_at · elapsed_days를 준다."""

    def _list_card(self, card_id):
        _, body = self._get("/board")
        for col in body["columns"].values():
            for c in col["cards"]:
                if c["id"] == card_id:
                    return c
        self.fail("목록에 카드 없음")

    def _detail(self, card_id):
        status, body = self._get(f"/board/card?repo={self.repo}&id={card_id}")
        self.assertEqual(status, 200)
        return body

    def test_요청_파일이_있는_예정_카드는_requested_at이_요청_시각이고_elapsed_days는_null이다(self):
        planned, _, _ = self._seed()
        d = self._detail(planned["id"])
        self.assertAlmostEqual(d["requested_at"], self.now - 3 * DAY, places=3)
        self.assertIsNone(d["elapsed_days"])
        self.assertEqual(d["requested_at"], self._list_card(planned["id"])["requested_at"])
        self.assertIsNone(self._list_card(planned["id"])["elapsed_days"])

    def test_진행_카드의_elapsed_days는_목록과_같은_숫자다(self):
        _, doing, _ = self._seed()
        d = self._detail(doing["id"])
        self.assertEqual(d["elapsed_days"], 4)
        self.assertEqual(d["elapsed_days"], self._list_card(doing["id"])["elapsed_days"])
        self.assertEqual(d["requested_at"], self._list_card(doing["id"])["requested_at"])

    def test_요청_파일이_없는_카드는_requested_at이_null이다(self):
        card = board.add_card(self.repo, "요청 없는 카드", "", self.now - DAY)
        d = self._detail(card["id"])
        self.assertIsNone(d["requested_at"])
        self.assertIsNone(d["elapsed_days"])

    def test_완료_카드는_elapsed_days가_null이다(self):
        _, _, done = self._seed()
        self.assertIsNone(self._detail(done["id"])["elapsed_days"])

    def test_요청_파일이_깨진_카드는_목록과_같은_결과다(self):
        planned, doing, _ = self._seed()
        for card in (planned, doing):
            (self.board_root / self.repo / f"{card['id']}.request.json").write_text(
                "{깨짐", encoding="utf-8")
            d = self._detail(card["id"])
            lst = self._list_card(card["id"])
            self.assertIsNone(d["requested_at"])
            self.assertEqual(d["requested_at"], lst["requested_at"])
            self.assertEqual(d["elapsed_days"], lst["elapsed_days"])

    def test_예정에서_진행으로_옮긴_뒤_값이_목록과_같다(self):
        planned, _, _ = self._seed()
        self.assertIsNone(self._detail(planned["id"])["elapsed_days"])
        board.move_card(self.repo, planned["id"], "doing", self.now - 3 * DAY)
        d = self._detail(planned["id"])
        self.assertEqual(d["elapsed_days"], 3)
        self.assertEqual(d["elapsed_days"], self._list_card(planned["id"])["elapsed_days"])

    def test_없는_카드는_그대로_404다(self):
        self._seed()
        status, _ = self._get(f"/board/card?repo={self.repo}&id=1-abcd")
        self.assertEqual(status, 404)

    def test_읽기만_하고_요청_파일을_바꾸지_않으며_경로가_안_실린다(self):
        planned, doing, _ = self._seed()
        before = _snapshot(self.board_root)
        for card in (planned, doing):
            body = self._detail(card["id"])
            self.assertNotIn(self._tmp.name, json.dumps(body, ensure_ascii=False))
        self.assertEqual(_snapshot(self.board_root), before)

    def test_응답_키_집합은_늘지_않는다(self):
        planned, _, _ = self._seed()
        self.assertEqual(set(self._detail(planned["id"])), {
            "id", "title", "note", "column", "task", "created_at", "requested_at", "doing_at",
            "pr_at", "done_at", "archived_at", "elapsed_days", "refs", "steps", "phase_summary"})
