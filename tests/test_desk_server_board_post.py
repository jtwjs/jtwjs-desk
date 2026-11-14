"""POST /board/* (step 5) — 카드 추가 · 삭제 · 보관 · 시작 · 취소 · 링크 엔드포인트.

엣지 5축: 빈 값(빈 제목 · 빈 링크 이름) · 비정상 입력(깨진 본문 · 경로 탈출 · javascript: URL · 길이 초과) ·
실패 경로(404 · 409) · 상태 전이(add → start → cancel · archive ↔ revive) ·
동시성(요청 파일이 이미 있을 때 두 번째 start 거절).
🔴 픽스처는 임시 폴더 안의 지어낸 레포 · 카드 · example.com 링크다.
"""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_desk_server_review import _ReviewCase
from desk import board


def _snapshot(root: Path) -> dict:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


class _PostCase(_ReviewCase):
    def setUp(self):
        super().setUp()
        self.repo = "fake-repo"
        self.board_root = self.home_dir / "board"
        self._write_cfg([self.repo_root])

    def _p(self, path, payload, headers=None):
        return self._post(path, payload, headers if headers is not None else self._pick_headers())

    def _add(self, title="카드 하나", note="", **extra):
        status, body = self._p("/board/add", {"repo": self.repo, "title": title, "note": note, **extra})
        self.assertEqual(status, 200, body)
        return body["id"]

    def _files(self):
        return _snapshot(self.board_root) if self.board_root.exists() else {}

    def _card(self, card_id):
        _, body = self._get(f"/board/card?repo={self.repo}&id={card_id}")
        return body

    def _find(self, body, col, card_id):
        return next((c for c in body["columns"][col]["cards"] if c["id"] == card_id), None)

    def _to_doing(self, card_id):
        board.request_start(self.repo, card_id, 1000.0)
        board.move_card(self.repo, card_id, "doing", 2000.0)


class 토큰_가드(_PostCase):
    def test_토큰이_없으면_엔드포인트마다_403이고_파일은_그대로다(self):
        cid = self._add("가드 카드")
        before = self._files()
        calls = {
            "/board/add": {"repo": self.repo, "title": "새 카드"},
            "/board/delete": {"repo": self.repo, "id": cid},
            "/board/archive": {"repo": self.repo, "id": cid},
            "/board/revive": {"repo": self.repo, "id": cid},
            "/board/start": {"repo": self.repo, "id": cid},
            "/board/cancel": {"repo": self.repo, "id": cid},
            "/board/ref/add": {"repo": self.repo, "id": cid, "name": "n", "url": "https://example.com"},
            "/board/ref/update": {"repo": self.repo, "id": cid, "ref_id": "r0000", "name": "n",
                                  "url": "https://example.com"},
            "/board/ref/delete": {"repo": self.repo, "id": cid, "ref_id": "r0000"},
        }
        for path, payload in calls.items():
            status, _ = self._p(path, payload, {"Content-Type": "application/json"})
            self.assertEqual(status, 403, path)
        self.assertEqual(self._files(), before)

    def test_Origin이_다르면_403이다(self):
        status, _ = self._p("/board/add", {"repo": self.repo, "title": "x"},
                            self._pick_headers(Origin="http://evil.example"))
        self.assertEqual(status, 403)
        self.assertEqual(self._files(), {})


class 카드_추가(_PostCase):
    def test_정상_add_뒤_GET_board에_예정_카드로_보인다(self):
        cid = self._add("새 일감", "메모")
        _, body = self._get("/board")
        card = self._find(body, "planned", cid)
        self.assertEqual(card["title"], "새 일감")
        self.assertTrue((self.board_root / self.repo / f"{cid}.json").is_file())

    def test_빈_제목은_400이고_파일이_안_생긴다(self):
        for title in ("", "   ", None, 5):
            status, _ = self._p("/board/add", {"repo": self.repo, "title": title})
            self.assertEqual(status, 400, title)
        self.assertEqual(self._files(), {})

    def test_모르는_레포는_400이다(self):
        status, _ = self._p("/board/add", {"repo": "ghost-repo", "title": "x"})
        self.assertEqual(status, 400)
        self.assertEqual(self._files(), {})

    def test_경로_탈출_레포는_400이다(self):
        for repo in ("../evil", "a/b", "..", ""):
            status, _ = self._p("/board/add", {"repo": repo, "title": "x"})
            self.assertEqual(status, 400, repo)
        self.assertEqual(self._files(), {})

    def test_깨진_본문은_400이다(self):
        req = urllib.request.Request(self._url("/board/add"), data=b"{not json", method="POST",
                                     headers=self._pick_headers())
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=1)
        self.assertEqual(ctx.exception.code, 400)
        ctx.exception.read()

    def test_본문이_객체가_아니면_400이다(self):
        status, _ = self._p("/board/add", ["a"])
        self.assertEqual(status, 400)

    def test_같은_레포의_같은_예정_제목은_409고_파일이_안_늘고_오류에_경로가_없다(self):
        self._add("겹침")
        before = self._files()
        status, body = self._p("/board/add", {"repo": self.repo, "title": "겹침"})
        self.assertEqual((status, body), (409, {"error": "duplicate"}))
        self.assertEqual(self._files(), before)

    def test_진행_카드와_같은_제목은_통과한다(self):
        cid = self._add("재작업")
        self._to_doing(cid)
        self._add("재작업")

    def test_링크를_같이_보내면_refs_파일에_저장되고_상세에_나온다(self):
        cid = self._add("링크 카드", links=[{"name": "문서", "url": "https://example.com/a"}])
        detail = self._card(cid)
        self.assertEqual([(r["name"], r["url"]) for r in detail["refs"]],
                         [("문서", "https://example.com/a")])
        self.assertTrue((self.board_root / self.repo / f"{cid}.refs.json").is_file())

    def test_링크가_하나라도_틀리면_400이고_카드_파일도_안_생긴다(self):
        bad_sets = {
            "6개": [{"name": f"n{i}", "url": "https://example.com"} for i in range(6)],
            "javascript": [{"name": "ok", "url": "https://example.com"},
                           {"name": "x", "url": "javascript:alert(1)"}],
            "로컬 경로": [{"name": "x", "url": "/Users/someone/file.md"}],
            "이름 41자": [{"name": "가" * 41, "url": "https://example.com"}],
            "URL 2001자": [{"name": "x", "url": "https://example.com/" + "a" * 1982}],
            "빈 이름": [{"name": "", "url": "https://example.com"}],
            "모양 오류": ["https://example.com"],
            "목록 아님": "https://example.com",
        }
        self.assertEqual(len("https://example.com/" + "a" * 1982), 2002)
        for label, links in bad_sets.items():
            status, _ = self._p("/board/add", {"repo": self.repo, "title": f"t-{label}", "links": links})
            self.assertEqual(status, 400, label)
        self.assertEqual(self._files(), {})

    def test_링크_5개와_2000자_URL은_통과한다(self):
        url = "https://example.com/" + "a" * 1980
        self.assertEqual(len(url), 2000)
        links = [{"name": f"n{i}", "url": url} for i in range(5)]
        cid = self._add("경계", links=links)
        self.assertEqual(len(self._card(cid)["refs"]), 5)


class 삭제_보관(_PostCase):
    def test_예정_카드는_삭제되고_요청_링크_파일도_사라진다(self):
        cid = self._add("지울 카드", links=[{"name": "n", "url": "https://example.com"}])
        self._p("/board/start", {"repo": self.repo, "id": cid})
        status, _ = self._p("/board/delete", {"repo": self.repo, "id": cid})
        self.assertEqual(status, 200)
        self.assertEqual(self._files(), {})

    def test_진행_카드_삭제는_409고_파일은_그대로다(self):
        cid = self._add("진행중")
        self._to_doing(cid)
        before = self._files()
        status, _ = self._p("/board/delete", {"repo": self.repo, "id": cid})
        self.assertEqual(status, 409)
        self.assertEqual(self._files(), before)

    def test_없는_카드_삭제는_404다(self):
        status, _ = self._p("/board/delete", {"repo": self.repo, "id": "1-abcd"})
        self.assertEqual(status, 404)

    def test_id_형식이_틀리거나_경로_탈출이면_400이다(self):
        for cid in ("../x", "abc", "", None):
            status, _ = self._p("/board/delete", {"repo": self.repo, "id": cid})
            self.assertEqual(status, 400, cid)
        status, _ = self._p("/board/delete", {"repo": "../evil", "id": "1-abcd"})
        self.assertEqual(status, 400)

    def test_모르는_레포의_id_동작은_404다(self):
        status, _ = self._p("/board/delete", {"repo": "ghost-repo", "id": "1-abcd"})
        self.assertEqual(status, 404)

    def test_보관하면_기본_목록에서_빠지고_보관_보기에_나오고_되살리면_돌아온다(self):
        cid = self._add("보관 카드")
        self._to_doing(cid)
        status, _ = self._p("/board/archive", {"repo": self.repo, "id": cid})
        self.assertEqual(status, 200)
        _, body = self._get("/board")
        self.assertIsNone(self._find(body, "doing", cid))
        _, arch = self._get("/board?archived=1")
        self.assertIsNotNone(self._find(arch, "doing", cid))
        status, _ = self._p("/board/revive", {"repo": self.repo, "id": cid})
        self.assertEqual(status, 200)
        _, body = self._get("/board")
        self.assertIsNotNone(self._find(body, "doing", cid))

    def test_예정_카드_보관은_409다(self):
        cid = self._add("예정")
        status, _ = self._p("/board/archive", {"repo": self.repo, "id": cid})
        self.assertEqual(status, 409)

    def test_없는_카드_보관_되살리기는_404다(self):
        for path in ("/board/archive", "/board/revive"):
            status, _ = self._p(path, {"repo": self.repo, "id": "1-abcd"})
            self.assertEqual(status, 404, path)


class 시작_취소(_PostCase):
    def _requests(self):
        return sorted((self.board_root / self.repo).glob("*.request.json"))

    def test_start는_요청_파일_하나를_쓰고_배지가_요청됨이다(self):
        cid = self._add("시작할 카드")
        card_file = self.board_root / self.repo / f"{cid}.json"
        before = card_file.read_bytes()
        status, _ = self._p("/board/start", {"repo": self.repo, "id": cid})
        self.assertEqual(status, 200)
        self.assertEqual(len(self._requests()), 1)
        self.assertEqual(card_file.read_bytes(), before)
        _, body = self._get("/board")
        self.assertEqual(self._find(body, "planned", cid)["badge"], "requested")

    def test_두_번째_start는_409고_요청_파일은_하나다(self):
        cid = self._add("중복 시작")
        self._p("/board/start", {"repo": self.repo, "id": cid})
        status, _ = self._p("/board/start", {"repo": self.repo, "id": cid})
        self.assertEqual(status, 409)
        self.assertEqual(len(self._requests()), 1)

    def test_진행_카드_start는_409다(self):
        cid = self._add("이미 진행")
        self._to_doing(cid)
        status, _ = self._p("/board/start", {"repo": self.repo, "id": cid})
        self.assertEqual(status, 409)

    def test_없는_카드_start는_404다(self):
        status, _ = self._p("/board/start", {"repo": self.repo, "id": "1-abcd"})
        self.assertEqual(status, 404)

    def test_add_start_cancel_뒤_배지가_사라지고_다시_start할_수_있다(self):
        cid = self._add("취소 카드")
        self._p("/board/start", {"repo": self.repo, "id": cid})
        status, _ = self._p("/board/cancel", {"repo": self.repo, "id": cid})
        self.assertEqual(status, 200)
        self.assertEqual(self._requests(), [])
        _, body = self._get("/board")
        self.assertIsNone(self._find(body, "planned", cid)["badge"])
        status, _ = self._p("/board/start", {"repo": self.repo, "id": cid})
        self.assertEqual(status, 200)

    def test_요청이_없으면_cancel은_409다(self):
        cid = self._add("요청 없음")
        status, _ = self._p("/board/cancel", {"repo": self.repo, "id": cid})
        self.assertEqual(status, 409)

    def test_예정을_떠난_카드_cancel은_409고_요청_파일은_그대로다(self):
        cid = self._add("떠난 카드")
        self._to_doing(cid)
        before = self._files()
        status, _ = self._p("/board/cancel", {"repo": self.repo, "id": cid})
        self.assertEqual(status, 409)
        self.assertEqual(self._files(), before)

    def test_없는_카드_cancel은_404다(self):
        status, _ = self._p("/board/cancel", {"repo": self.repo, "id": "1-abcd"})
        self.assertEqual(status, 404)


class 레퍼런스_링크(_PostCase):
    def _ref(self, path, cid, **kw):
        return self._p(f"/board/ref/{path}", {"repo": self.repo, "id": cid, **kw})

    def test_추가_수정_삭제_왕복이고_수정은_개수가_그대로다(self):
        cid = self._add("링크 왕복")
        status, body = self._ref("add", cid, name="첫 링크", url="https://example.com/1")
        self.assertEqual(status, 200)
        ref_id = body["id"]
        self._ref("add", cid, name="둘째", url="https://example.com/2")
        self.assertEqual(len(self._card(cid)["refs"]), 2)
        status, _ = self._ref("update", cid, ref_id=ref_id, name="바뀐 이름", url="https://example.com/x")
        self.assertEqual(status, 200)
        refs = self._card(cid)["refs"]
        self.assertEqual(len(refs), 2)
        changed = next(r for r in refs if r["id"] == ref_id)
        self.assertEqual((changed["name"], changed["url"]), ("바뀐 이름", "https://example.com/x"))
        status, _ = self._ref("delete", cid, ref_id=ref_id)
        self.assertEqual(status, 200)
        self.assertEqual([r["name"] for r in self._card(cid)["refs"]], ["둘째"])

    def test_6번째_추가는_409고_파일은_그대로다(self):
        cid = self._add("가득")
        for i in range(5):
            self.assertEqual(self._ref("add", cid, name=f"n{i}", url="https://example.com")[0], 200)
        before = self._files()
        status, _ = self._ref("add", cid, name="여섯째", url="https://example.com")
        self.assertEqual(status, 409)
        self.assertEqual(self._files(), before)

    def test_잘못된_링크는_400이고_파일은_그대로다(self):
        cid = self._add("검증")
        before = self._files()
        for name, url in (("x", "javascript:alert(1)"), ("x", "file:///etc/passwd"),
                          ("가" * 41, "https://example.com"), ("", "https://example.com"),
                          ("x", "https://example.com/" + "a" * 1990)):
            status, _ = self._ref("add", cid, name=name, url=url)
            self.assertEqual(status, 400, (name[:5], url[:20]))
        self.assertEqual(self._files(), before)

    def test_수정도_같은_검증을_한다(self):
        cid = self._add("수정 검증")
        _, body = self._ref("add", cid, name="a", url="https://example.com")
        status, _ = self._ref("update", cid, ref_id=body["id"], name="a", url="javascript:alert(1)")
        self.assertEqual(status, 400)
        self.assertEqual(self._card(cid)["refs"][0]["url"], "https://example.com")

    def test_없는_카드와_없는_링크는_404다(self):
        cid = self._add("404")
        self.assertEqual(self._ref("add", "1-abcd", name="n", url="https://example.com")[0], 404)
        self.assertEqual(self._ref("update", cid, ref_id="r0000", name="n", url="https://example.com")[0], 404)
        self.assertEqual(self._ref("delete", cid, ref_id="r0000")[0], 404)

    def test_보관_카드의_링크도_수정할_수_있다(self):
        cid = self._add("보관 링크")
        _, body = self._ref("add", cid, name="옛 이름", url="https://example.com")
        self._to_doing(cid)
        self._p("/board/archive", {"repo": self.repo, "id": cid})
        status, _ = self._ref("update", cid, ref_id=body["id"], name="새 이름", url="https://example.com/n")
        self.assertEqual(status, 200)
        self.assertEqual(self._card(cid)["refs"][0]["name"], "새 이름")

    def test_깨진_링크_파일이면_세_경로가_409고_파일은_한_바이트도_안_바뀐다(self):
        cid = self._add("깨진 링크")
        path = self.board_root / self.repo / f"{cid}.refs.json"
        path.write_text("{깨짐", encoding="utf-8")
        before = self._files()
        for sub, kw in (("add", {"name": "n", "url": "https://example.com"}),
                        ("update", {"ref_id": "r0000", "name": "n", "url": "https://example.com"}),
                        ("delete", {"ref_id": "r0000"})):
            status, body = self._ref(sub, cid, **kw)
            self.assertEqual((status, body), (409, {"error": "refs broken"}), sub)
        self.assertEqual(self._files(), before)


class 메뉴_배지_없음(_PostCase):
    def test_nav_counts_키_집합이_그대로다(self):
        self._add("배지 확인")
        status, body = self._get("/nav-counts")
        self.assertEqual(status, 200)
        self.assertEqual(set(body), {"judge", "review", "routine", "trends", "errors"})
