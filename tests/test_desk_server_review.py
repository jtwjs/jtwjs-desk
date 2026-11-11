"""page/server.py 공통 부품 · GET /review · POST /review/done (step 5).

엣지 5축: 빈 값(설정 없음 · 레포 폴더 없음) · 비정상 입력(토큰 · Origin · 키 형식 · 허용 밖 경로) ·
실패 경로(파일 없음 · 깨진 JSON) · 상태 전이(마킹 전 → 후) · 동시성(해당 없음 — 마킹은 키별 파일).
🔴 픽스처는 임시 폴더 안의 지어낸 레포 · 카드다.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import test_desk_server as base
from desk import ledger
from page import server

INBOX = """# 학습 수신함 (지어낸 픽스처)

## 2026-01-02 · 샘플 개념 A
- 종류: 기술 · 출처: AI 설명
- 이 레포 어디: `src/sample/app.tsx`
- 요지: 샘플 요지
- 상태: 모름
- vault:

## 2026-01-03 · 샘플 개념 B
- 종류: 도메인 · 출처: 내가 물음
- 이 레포 어디: `docs/sample.md`
- 요지: 이미 반영
- 상태: 설명 들음
- vault: 1_MyBrain/sample/b.md

## 2026-01-04 · 샘플 직무 C
- 종류: 직무 · 출처: 내가 물음
- 이 레포 어디: `docs/x.md`
- 요지: 직무는 안 보인다
- 상태: 모름
- vault:
"""


class 순수_함수_읽기_허용_목록(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "fake-repo"
        (self.root / "_learn").mkdir(parents=True)
        (self.root / "_learn" / "inbox.md").write_text("내용", encoding="utf-8")

    def test_허용된_상대경로는_내용을_돌려준다(self):
        self.assertEqual(server.read_ledger(self.root, "_learn/inbox.md"), "내용")

    def test_허용된_파일이_없으면_None이다(self):
        self.assertIsNone(server.read_ledger(self.root, ".claude/observations.md"))

    def test_허용_밖_경로는_ValueError다(self):
        for rel in ("secrets.md", "../outside.md", "/etc/passwd", "_learn/../x.md"):
            with self.subTest(rel=rel):
                with self.assertRaises(ValueError):
                    server.read_ledger(self.root, rel)

    def test_ALLOWED_REL은_이_step의_둘을_담는다(self):
        self.assertIn(".claude/observations.md", server.ALLOWED_REL)
        self.assertIn("_learn/inbox.md", server.ALLOWED_REL)


class 순수_함수_phase_목록(unittest.TestCase):
    def test_index_json만_읽고_깨진_JSON은_건너뛴다(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / "phases" / "good").mkdir(parents=True)
            (root / "phases" / "bad").mkdir(parents=True)
            (root / "phases" / "good" / "index.json").write_text('{"a": 1}', encoding="utf-8")
            (root / "phases" / "bad" / "index.json").write_text("{깨짐", encoding="utf-8")
            (root / "phases" / "good" / "step1.md").write_text("x", encoding="utf-8")
            self.assertEqual(server.list_phase_indexes(root), [("good", {"a": 1})])

    def test_phases_폴더가_없으면_빈_목록이다(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(server.list_phase_indexes(Path(t)), [])


class 순수_함수_vault_friction(unittest.TestCase):
    def test_vault가_None이면_None이다(self):
        self.assertIsNone(server.read_vault_friction(None))

    def test_고정_경로_한_파일만_읽는다(self):
        with tempfile.TemporaryDirectory() as t:
            vault = Path(t)
            f = vault / "1_MyBrain" / "brain" / "friction"
            f.mkdir(parents=True)
            (f / "index.md").write_text("표", encoding="utf-8")
            (vault / "raw").mkdir()
            (vault / "raw" / "x.md").write_text("원문", encoding="utf-8")
            self.assertEqual(server.read_vault_friction(vault), "표")

    def test_파일이_없으면_None이다(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertIsNone(server.read_vault_friction(Path(t)))


class 순수_함수_config_block_missing_row(unittest.TestCase):
    def test_config_block은_세_키를_낸다(self):
        cfg = {"source": "config", "repos": [Path("/x/known")], "error": None}
        with patch.object(server, "list_sessions", return_value=[{"repo": "known"}, {"repo": "stray"}]):
            block = server.config_block(cfg)
        self.assertEqual(block, {"source": "config", "unregistered": ["stray"], "error": None})

    def test_missing_row_모양(self):
        self.assertEqual(
            server.missing_row("r", "inbox", "파일 없음"),
            {"repo": "r", "what": "inbox", "missing": "파일 없음"},
        )


class _ReviewCase(base._ServerTestCase):
    def setUp(self):
        super().setUp()
        tmp = Path(self._tmp.name)
        self.repo_root = tmp / "fake-repo"
        (self.repo_root / "_learn").mkdir(parents=True)
        (self.repo_root / "_learn" / "inbox.md").write_text(INBOX, encoding="utf-8")
        (self.repo_root / "phases" / "task-x").mkdir(parents=True)
        (self.repo_root / "phases" / "task-x" / "index.json").write_text(
            json.dumps({"reflect": {"understanding_check": "skipped"}}), encoding="utf-8")
        (self.repo_root / "phases" / "task-y").mkdir(parents=True)
        (self.repo_root / "phases" / "task-y" / "index.json").write_text(
            json.dumps({"reflect": {"understanding_check": "done"}}), encoding="utf-8")
        self.cfg_path = tmp / "config.json"
        env = patch.dict(os.environ, {
            "DESK_CONFIG": str(self.cfg_path),
            "DESK_CONDUCTOR": str(tmp / "no-conductor.json"),
        })
        env.start()
        self.addCleanup(env.stop)

    def _write_cfg(self, repos):
        self.cfg_path.write_text(json.dumps({"repos": [str(r) for r in repos]}), encoding="utf-8")


class 통합_GET_review(_ReviewCase):
    def test_설정이_없으면_source_none과_빈_items다(self):
        status, body = self._get("/review")
        self.assertEqual(status, 200)
        self.assertEqual(body["config"]["source"], "none")
        self.assertEqual(body["items"], [])

    def test_건너뛴_phase와_vault_빈_카드가_보이고_직무와_반영_카드는_안_보인다(self):
        self._write_cfg([self.repo_root])
        status, body = self._get("/review")
        self.assertEqual(status, 200)
        keys = {(i["kind"], i["title"]) for i in body["items"]}
        self.assertEqual(keys, {("phase", "task-x"), ("card", "샘플 개념 A")})
        phase = next(i for i in body["items"] if i["kind"] == "phase")
        self.assertEqual(phase["repo"], "fake-repo")
        self.assertEqual(phase["key"], ledger.phase_key("task-x"))
        card = next(i for i in body["items"] if i["kind"] == "card")
        self.assertEqual(card["key"], ledger.card_key("샘플 개념 A"))
        self.assertEqual(card["card_kind"], "기술")
        self.assertEqual(card["status"], "모름")

    def test_레포_폴더가_없으면_missing에_경로_없음이다(self):
        self._write_cfg([self.repo_root.parent / "ghost-repo"])
        status, body = self._get("/review")
        self.assertEqual(status, 200)
        self.assertEqual(body["items"], [])
        self.assertTrue(any(m["repo"] == "ghost-repo" and m["missing"] == "경로 없음"
                            for m in body["missing"]))

    def test_inbox가_없는_레포는_파일_없음_행이_나온다(self):
        bare = self.repo_root.parent / "bare-repo"
        bare.mkdir()
        self._write_cfg([bare])
        _, body = self._get("/review")
        self.assertTrue(any(m["repo"] == "bare-repo" and m["missing"] == "파일 없음"
                            for m in body["missing"]))

    def test_Host가_다르면_403이다(self):
        status, _ = self._get_raw_host("/review", "evil.example:80")
        self.assertEqual(status, 403)

    def test_CORS_헤더를_내지_않는다(self):
        import urllib.request
        resp = urllib.request.urlopen(self._url("/review"), timeout=1)
        self.assertIsNone(resp.headers.get("Access-Control-Allow-Origin"))


class 통합_POST_review_done(_ReviewCase):
    def _done(self, payload, headers=None):
        return self._post("/review/done", payload,
                          headers if headers is not None else self._pick_headers())

    def test_마킹_뒤_review에서_사라지고_파일에는_at만_있다(self):
        self._write_cfg([self.repo_root])
        key = ledger.phase_key("task-x")
        status, body = self._done({"repo": "fake-repo", "key": key})
        self.assertEqual((status, body), (200, {"ok": True}))
        mark = self.home_dir / "review" / "fake-repo" / f"{key}.done.json"
        data = json.loads(mark.read_text(encoding="utf-8"))
        self.assertEqual(list(data), ["at"])
        self.assertIsInstance(data["at"], str)
        _, review = self._get("/review")
        self.assertNotIn(key, [i["key"] for i in review["items"]])
        self.assertEqual(len(review["items"]), 1)

    def test_두_번_눌러도_200이다(self):
        key = ledger.card_key("샘플 개념 A")
        self.assertEqual(self._done({"repo": "r", "key": key})[0], 200)
        self.assertEqual(self._done({"repo": "r", "key": key})[0], 200)

    def test_토큰이_없으면_403이다(self):
        h = self._pick_headers()
        del h["X-Desk-Token"]
        self.assertEqual(self._done({"repo": "r", "key": "phase-a"}, h)[0], 403)

    def test_Origin이_다르면_403이다(self):
        h = self._pick_headers(Origin="http://evil.example")
        self.assertEqual(self._done({"repo": "r", "key": "phase-a"}, h)[0], 403)

    def test_키_형식이_틀리면_400이다(self):
        for key in ("../escape", "plain", "phase-a/b", "card-"):
            with self.subTest(key=key):
                self.assertEqual(self._done({"repo": "r", "key": key})[0], 400)

    def test_repo_형식이_틀리면_400이다(self):
        for repo in ("../x", "a/b", ""):
            with self.subTest(repo=repo):
                self.assertEqual(self._done({"repo": repo, "key": "phase-a"})[0], 400)
        self.assertFalse((self.home_dir / "review").exists())


if __name__ == "__main__":
    unittest.main()
