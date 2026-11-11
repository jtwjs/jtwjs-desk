"""GET /competency/proactive · POST /share/shared (step 7).

엣지 5축: 빈 값(설정 없음 · 패턴 비어 있음) · 비정상 입력(토큰 · 이름 형식 · `..` 패턴) ·
실패 경로(criteria 못 읽음 · 타임스탬프 없음) · 상태 전이(마킹 전 → 후) · 동시성(해당 없음).
🔴 픽스처는 임시 폴더 안의 지어낸 문서 · 레포다.
"""
import json
import os
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import test_desk_server as base


def _index(steps, docs=None):
    d = {"project": "fake", "steps": steps}
    if docs:
        d["docs"] = docs
    return json.dumps(d)


class _ProactiveCase(base._ServerTestCase):
    def setUp(self):
        super().setUp()
        tmp = Path(self._tmp.name)
        self.tmp = tmp
        self.repo_root = tmp / "fake-repo"
        self.repo_root.mkdir()
        self.cfg_path = tmp / "config.json"
        env = patch.dict(os.environ, {
            "DESK_CONFIG": str(self.cfg_path),
            "DESK_CONDUCTOR": str(tmp / "no-conductor.json"),
        })
        env.start()
        self.addCleanup(env.stop)

    def _write_cfg(self, **extra):
        data = {"repos": [str(self.repo_root)], **extra}
        self.cfg_path.write_text(json.dumps(data), encoding="utf-8")

    def _phase(self, task, steps, docs=None):
        d = self.repo_root / "phases" / task
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.json").write_text(_index(steps, docs), encoding="utf-8")

    def _share(self, id_, text="- 샘플 불렛", repo="fake-repo"):
        d = self.home_dir / "share" / repo
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{id_}.md").write_text(text, encoding="utf-8")


class 통합_criteria(_ProactiveCase):
    def test_설정이_없으면_source_none과_설정_없음이다(self):
        status, body = self._get("/competency/proactive")
        self.assertEqual(status, 200)
        self.assertEqual(body["config"]["source"], "none")
        self.assertEqual(body["criteria"], {"text": None, "note": "설정 없음"})

    def test_criteria_file이_있으면_텍스트_그대로다(self):
        f = self.tmp / "criteria.md"
        f.write_text("# 지어낸 기준\n\n- 하나\n- 둘\n", encoding="utf-8")
        self._write_cfg(criteria_file=str(f))
        _, body = self._get("/competency/proactive")
        self.assertEqual(body["criteria"], {"text": "# 지어낸 기준\n\n- 하나\n- 둘\n"})

    def test_criteria_file이_키가_없으면_설정_없음이다(self):
        self._write_cfg()
        _, body = self._get("/competency/proactive")
        self.assertEqual(body["criteria"], {"text": None, "note": "설정 없음"})

    def test_criteria_file을_못_읽으면_읽을_수_없음이다(self):
        self._write_cfg(criteria_file=str(self.tmp / "ghost.md"))
        status, body = self._get("/competency/proactive")
        self.assertEqual(status, 200)
        self.assertEqual(body["criteria"], {"text": None, "note": "읽을 수 없음"})

    def test_Host가_다르면_403이다(self):
        status, _ = self._get_raw_host("/competency/proactive", "evil.example:80")
        self.assertEqual(status, 403)


class 통합_speed(_ProactiveCase):
    def test_고정_문구와_링크만_있다(self):
        self._write_cfg()
        _, body = self._get("/competency/proactive")
        self.assertEqual(body["speed"]["metric2"], "측정 안 함")
        self.assertEqual(body["speed"]["workflow_link"], "workflow")
        self.assertEqual(body["speed"]["durations"], [])
        self.assertEqual(body["speed"]["no_data"], 0)

    def test_가장_이른_시작부터_가장_늦은_완료까지_분이다(self):
        self._phase("task-a", [
            {"step": 1, "started_at": "2026-11-11T10:00:00+0900",
             "completed_at": "2026-11-11T10:20:00+0900"},
            {"step": 2, "started_at": "2026-11-11T10:25:00+0900",
             "completed_at": "2026-11-11T11:00:00+0900"},
        ])
        self._write_cfg()
        _, body = self._get("/competency/proactive")
        self.assertEqual(body["speed"]["durations"],
                         [{"repo": "fake-repo", "task": "task-a", "minutes": 60}])
        self.assertEqual(body["speed"]["no_data"], 0)

    def test_타임스탬프가_없거나_깨진_phase는_no_data로_센다(self):
        self._phase("no-ts", [{"step": 1, "status": "pending"}])
        self._phase("broken-ts", [{"step": 1, "started_at": "어제",
                                   "completed_at": "오늘"}])
        self._phase("half-ts", [{"step": 1, "started_at": "2026-11-11T10:00:00+0900"}])
        self._phase("ok", [{"step": 1, "started_at": "2026-11-11T10:00:00+0900",
                            "completed_at": "2026-11-11T10:05:00+0900"}])
        self._write_cfg()
        status, body = self._get("/competency/proactive")
        self.assertEqual(status, 200)
        self.assertEqual([d["task"] for d in body["speed"]["durations"]], ["ok"])
        self.assertEqual(body["speed"]["no_data"], 3)


class 통합_impact(_ProactiveCase):
    def test_PRD가_있는_phase에만_링크가_붙는다(self):
        (self.repo_root / "docs" / "feat-a").mkdir(parents=True)
        (self.repo_root / "docs" / "feat-a" / "PRD.md").write_text("# PRD", encoding="utf-8")
        (self.repo_root / "docs" / "feat-b").mkdir(parents=True)
        self._phase("task-a", [], docs="docs/feat-a")
        self._phase("task-b", [], docs="docs/feat-b")
        self._phase("task-c", [])
        self._write_cfg()
        _, body = self._get("/competency/proactive")
        self.assertEqual(body["impact"]["prds"],
                         [{"repo": "fake-repo", "task": "task-a", "prd": "docs/feat-a/PRD.md"}])

    def test_evidence_globs가_비면_경로_미설정이다(self):
        self._write_cfg()
        _, body = self._get("/competency/proactive")
        self.assertEqual(body["impact"]["evidence"], {"note": "경로 미설정"})
        self.assertEqual(body["impact"]["ignored"], 0)

    def test_패턴에_걸린_파일이_최신순_상위_5개다(self):
        ev = self.repo_root / "evidence"
        ev.mkdir()
        now = time.time()
        for i in range(7):
            f = ev / f"e{i}.md"
            f.write_text("내용 비공개", encoding="utf-8")
            os.utime(f, (now - 1000 + i * 10, now - 1000 + i * 10))
        self._write_cfg(evidence_globs=["evidence/*.md"])
        _, body = self._get("/competency/proactive")
        rows = body["impact"]["evidence"]
        self.assertEqual([r["path"] for r in rows],
                         [f"evidence/e{i}.md" for i in (6, 5, 4, 3, 2)])
        self.assertEqual(set(rows[0]), {"repo", "path", "mtime"})
        self.assertEqual(rows[0]["repo"], "fake-repo")
        self.assertNotIn("내용 비공개", json.dumps(body, ensure_ascii=False))

    def test_점점_패턴과_절대경로_패턴은_무시하고_개수를_낸다(self):
        outside = self.tmp / "outside.md"
        outside.write_text("밖", encoding="utf-8")
        (self.repo_root / "in.md").write_text("안", encoding="utf-8")
        self._write_cfg(evidence_globs=["../outside.md", str(outside), "*.md"])
        status, body = self._get("/competency/proactive")
        self.assertEqual(status, 200)
        self.assertEqual(body["impact"]["ignored"], 2)
        self.assertIsNone(body["config"]["error"])
        paths_ = [r["path"] for r in body["impact"]["evidence"]]
        self.assertEqual(paths_, ["in.md"])


class 통합_transparency(_ProactiveCase):
    def test_미반영_공유_파일만_id와_텍스트로_보인다(self):
        self._write_cfg()
        self._share("t1", "- 첫째")
        self._share("t2", "- 둘째")
        (self.home_dir / "share" / "fake-repo" / "t2.shared.json").write_text(
            json.dumps({"at": "2026-11-11T10:00:00"}), encoding="utf-8")
        self._share("other", "- 설정에 없는 레포", repo="stray-repo")
        _, body = self._get("/competency/proactive")
        self.assertEqual(body["transparency"],
                         [{"repo": "fake-repo", "id": "t1", "text": "- 첫째"}])

    def test_공유_폴더가_없으면_빈_목록이다(self):
        self._write_cfg()
        _, body = self._get("/competency/proactive")
        self.assertEqual(body["transparency"], [])

    def test_레포_폴더가_없으면_missing에_경로_없음이다(self):
        self.cfg_path.write_text(json.dumps({"repos": [str(self.tmp / "ghost-repo")]}),
                                 encoding="utf-8")
        _, body = self._get("/competency/proactive")
        self.assertTrue(any(m["repo"] == "ghost-repo" and m["missing"] == "경로 없음"
                            for m in body["missing"]))


class 통합_POST_share_shared(_ProactiveCase):
    def _mark(self, payload, headers=None):
        return self._post("/share/shared", payload,
                          headers if headers is not None else self._pick_headers())

    def test_마킹_뒤_사라지고_md는_그대로이며_파일에는_at만_있다(self):
        self._write_cfg()
        self._share("t1", "- 첫째")
        status, body = self._mark({"repo": "fake-repo", "id": "t1"})
        self.assertEqual((status, body), (200, {"ok": True}))
        d = self.home_dir / "share" / "fake-repo"
        data = json.loads((d / "t1.shared.json").read_text(encoding="utf-8"))
        self.assertEqual(list(data), ["at"])
        self.assertIsInstance(data["at"], str)
        self.assertEqual((d / "t1.md").read_text(encoding="utf-8"), "- 첫째")
        _, after = self._get("/competency/proactive")
        self.assertEqual(after["transparency"], [])

    def test_두_번_눌러도_200이다(self):
        self.assertEqual(self._mark({"repo": "r", "id": "x"})[0], 200)
        self.assertEqual(self._mark({"repo": "r", "id": "x"})[0], 200)

    def test_토큰이_없으면_403이고_아무것도_안_쓴다(self):
        h = self._pick_headers()
        del h["X-Desk-Token"]
        self.assertEqual(self._mark({"repo": "r", "id": "x"}, h)[0], 403)
        self.assertFalse((self.home_dir / "share").exists())

    def test_Origin이_다르면_403이다(self):
        h = self._pick_headers(Origin="http://evil.example")
        self.assertEqual(self._mark({"repo": "r", "id": "x"}, h)[0], 403)

    def test_이름_형식이_틀리면_400이고_아무것도_안_쓴다(self):
        for payload in ({"repo": "../x", "id": "a"}, {"repo": "r", "id": "../a"},
                        {"repo": "a/b", "id": "a"}, {"repo": "r", "id": ""},
                        {"repo": "r", "id": "a/b"}, {"repo": "r"}):
            with self.subTest(payload=payload):
                self.assertEqual(self._mark(payload)[0], 400)
        self.assertFalse((self.home_dir / "share").exists())


if __name__ == "__main__":
    unittest.main()
