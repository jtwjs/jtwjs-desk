"""GET /nav-counts — 메뉴 배지 건수 (판정 = pick 없는 카드, 복습 = 대기 items).

엣지 5축: 빈 값(0, 0 · 설정 없음) · 비정상 입력(Host 다름) · 실패 경로(레포 경로 없음) ·
상태 전이(pick · done 처리 전 → 후) · 동시성(해당 없음 — 읽기 전용).
🔴 픽스처는 임시 폴더 안의 지어낸 레포 · 카드다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # `unittest tests.<모듈>` 로도 형제 모듈을 찾게

from test_desk_server_review import _ReviewCase


class 통합_GET_nav_counts(_ReviewCase):
    def test_아무것도_없으면_0_0이다(self):
        status, body = self._get("/nav-counts")
        self.assertEqual(status, 200)
        self.assertEqual(body, {"judge": 0, "review": 0})

    def test_pick이_없는_카드만_judge로_센다(self):
        self._write_ask("repo-a", "ask-1")
        self._write_ask("repo-a", "ask-2")
        self._post("/pick", {"repo": "repo-a", "id": "ask-2", "choice": "a"},
                   self._pick_headers())
        status, body = self._get("/nav-counts")
        self.assertEqual(status, 200)
        self.assertEqual(body["judge"], 1)

    def test_설정이_없으면_review는_0이다(self):
        status, body = self._get("/nav-counts")
        self.assertEqual(status, 200)
        self.assertEqual(body["review"], 0)

    def test_설정이_있으면_복습_대기_수를_센다(self):
        self._write_cfg([self.repo_root])
        _, review = self._get("/review")
        status, body = self._get("/nav-counts")
        self.assertEqual(status, 200)
        self.assertGreater(len(review["items"]), 0)
        self.assertEqual(body["review"], len(review["items"]))

    def test_done_처리된_복습_항목은_뺀다(self):
        self._write_cfg([self.repo_root])
        _, before = self._get("/nav-counts")
        _, review = self._get("/review")
        item = review["items"][0]
        self._post("/review/done", {"repo": item["repo"], "key": item["key"]},
                   self._pick_headers())
        status, after = self._get("/nav-counts")
        self.assertEqual(status, 200)
        self.assertEqual(after["review"], before["review"] - 1)

    def test_Host가_다르면_403이다(self):
        status, _ = self._get_raw_host("/nav-counts", "evil.example")
        self.assertEqual(status, 403)

    def test_레포_경로가_없어도_200이다(self):
        self._write_cfg([self.repo_root.parent / "no-such-repo"])
        status, body = self._get("/nav-counts")
        self.assertEqual(status, 200)
        self.assertEqual(body["review"], 0)
