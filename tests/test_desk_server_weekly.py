"""GET /weekly · GET /repo-health (step 8).

엣지 5축: 빈 값(설정 없음 · 일간 JSON 0개) · 비정상 입력(깨진 JSON · 원문 키 · Host) ·
실패 경로(경로 없음 · 채점 없음 · 형식 틀림) · 상태 전이(해당 없음 — 읽기 전용) · 동시성(해당 없음).
🔴 픽스처는 임시 폴더 안의 지어낸 파일이다. 시계는 `server._today`를 바꿔 끼운다.
"""
import json
import os
import unittest
import urllib.request
from datetime import date
from pathlib import Path
from unittest.mock import patch

import test_desk_server as base
from page import server

TODAY = date(2026, 3, 10)


class _WeeklyCase(base._ServerTestCase):
    def setUp(self):
        super().setUp()
        tmp = Path(self._tmp.name)
        self.tmp = tmp
        self.daily = tmp / "daily"
        self.daily.mkdir()
        self.cfg_path = tmp / "config.json"
        env = patch.dict(os.environ, {
            "DESK_CONFIG": str(self.cfg_path),
            "DESK_CONDUCTOR": str(tmp / "no-conductor.json"),
        })
        env.start()
        self.addCleanup(env.stop)
        clock = patch.object(server, "_today", lambda: TODAY)
        clock.start()
        self.addCleanup(clock.stop)

    def _write_cfg(self, repos):
        self.cfg_path.write_text(json.dumps(
            {"repos": [str(r) for r in repos], "daily_dir": str(self.daily)}),
            encoding="utf-8")

    def _get_text(self, path):
        return urllib.request.urlopen(self._url(path), timeout=1).read().decode("utf-8")

    def _day(self, name, payload):
        text = payload if isinstance(payload, str) else json.dumps(payload)
        (self.daily / f"{name}.json").write_text(text, encoding="utf-8")


class 통합_GET_weekly(_WeeklyCase):
    def test_설정이_없으면_source_none을_알린다(self):
        status, body = self._get("/weekly")
        self.assertEqual(status, 200)
        self.assertEqual(body["config"]["source"], "none")

    def test_일간_JSON이_하나도_없으면_present_0과_missing_7개다(self):
        self._write_cfg([])
        _, body = self._get("/weekly")
        self.assertEqual(body["week"]["present"], 0)
        self.assertEqual(len(body["week"]["missing"]), 7)

    def test_7일_중_2개만_있으면_present_2와_missing_5개다(self):
        self._write_cfg([])
        self._day("2026-03-10", {"date": "2026-03-10", "sessions": 2, "stuck": 1,
                                 "repos": [{"name": "r1", "commits": 3, "progress": ["p"]}],
                                 "cards": [{"summary": "s"}]})
        self._day("2026-03-08", {"sessions": 1, "stuck": 0,
                                 "repos": [{"name": "r1", "commits": 1, "progress": []}]})
        _, body = self._get("/weekly")
        w = body["week"]
        self.assertEqual(w["present"], 2)
        self.assertEqual(len(w["missing"]), 5)
        self.assertEqual(w["sessions"], 3)
        self.assertEqual(w["commits"], 4)
        self.assertEqual(w["days"], 7)

    def test_원문_키가_섞여도_응답에_없다(self):
        self._write_cfg([])
        self._day("2026-03-10", {"sessions": 1, "prompts": ["SECRET-PROMPT-TEXT"],
                                 "title": "SECRET-TITLE", "cwd": "/secret/cwd-path",
                                 "repos": [{"name": "r1", "commits": 1, "progress": [],
                                            "prompts": ["SECRET-PROMPT-TEXT"]}],
                                 "cards": [{"summary": "SECRET-CARD-SUMMARY"}]})
        text = self._get_text("/weekly")
        for secret in ("SECRET-PROMPT-TEXT", "SECRET-TITLE", "/secret/cwd-path",
                       "SECRET-CARD-SUMMARY"):
            self.assertNotIn(secret, text)

    def test_깨진_JSON과_객체가_아닌_JSON은_없는_날로_센다(self):
        self._write_cfg([])
        self._day("2026-03-10", "{깨짐")
        self._day("2026-03-09", "[1, 2]")
        self._day("2026-03-08", {"sessions": 1})
        _, body = self._get("/weekly")
        self.assertEqual(body["week"]["present"], 1)
        self.assertIn("2026-03-10", body["week"]["missing"])
        self.assertIn("2026-03-09", body["week"]["missing"])

    def test_daily_dir_밖이나_이름_규칙_밖_파일은_열지_않는다(self):
        self._write_cfg([])
        (self.daily / "notes.json").write_text(json.dumps({"sessions": 99}), encoding="utf-8")
        _, body = self._get("/weekly")
        self.assertEqual(body["week"]["present"], 0)
        self.assertEqual(body["week"]["sessions"], 0)

    def test_Host가_다르면_403이다(self):
        status, _ = self._get_raw_host("/weekly", "evil.example:80")
        self.assertEqual(status, 403)


class 통합_GET_repo_health(_WeeklyCase):
    def _repo(self, name):
        root = self.tmp / name
        root.mkdir()
        return root

    def _score(self, path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload if isinstance(payload, str) else json.dumps(payload),
                        encoding="utf-8")

    def test_설정이_없으면_source_none을_알리고_repos가_비어_있다(self):
        status, body = self._get("/repo-health")
        self.assertEqual(status, 200)
        self.assertEqual(body["config"]["source"], "none")
        self.assertEqual(body["repos"], [])

    def test_레포마다_4모양으로_나온다(self):
        ok = self._repo("ok-repo")
        self._score(ok / ".claude" / "reports" / "2026-03-01" / "ai-readiness-score.json",
                    {"total": 82, "grade": "B"})
        none = self._repo("none-repo")
        bad = self._repo("bad-repo")
        self._score(bad / "ai-readiness-score.json", "{깨짐")
        self._write_cfg([ok, none, bad, self.tmp / "ghost-repo"])
        _, body = self._get("/repo-health")
        rows = {r["repo"]: r for r in body["repos"]}
        self.assertEqual(rows["ok-repo"], {"repo": "ok-repo", "total": 82, "grade": "B",
                                           "scored_on": "2026-03-01", "age_days": 9})
        self.assertEqual(rows["none-repo"], {"repo": "none-repo", "missing": "채점 없음"})
        self.assertEqual(rows["bad-repo"], {"repo": "bad-repo", "missing": "형식 확인 필요"})
        self.assertEqual(rows["ghost-repo"], {"repo": "ghost-repo", "missing": "경로 없음"})

    def test_reports_날짜_폴더가_채점일이고_가장_최근_것이_이긴다(self):
        r = self._repo("dated-repo")
        self._score(r / ".claude" / "reports" / "2026-02-01" / "ai-readiness-score.json",
                    {"total": 50, "grade": "D"})
        self._score(r / ".claude" / "reports" / "2026-03-05" / "ai-readiness-score.json",
                    {"total": 70, "grade": "C"})
        self._write_cfg([r])
        _, body = self._get("/repo-health")
        row = body["repos"][0]
        self.assertEqual(row["scored_on"], "2026-03-05")
        self.assertEqual(row["age_days"], 5)
        self.assertEqual(row["total"], 70)

    def test_reports_밖_파일은_수정시각의_날짜가_채점일이다(self):
        r = self._repo("mtime-repo")
        f = r / "docs" / "ai-readiness-score.json"
        self._score(f, {"total": 60, "grade": "C"})
        ts = 1772755200  # 2026-03-06 00:00 UTC 근처
        os.utime(f, (ts, ts))
        self._write_cfg([r])
        _, body = self._get("/repo-health")
        row = body["repos"][0]
        self.assertEqual(row["scored_on"], date.fromtimestamp(ts).isoformat())
        self.assertEqual(row["age_days"], (TODAY - date.fromtimestamp(ts)).days)

    def _health_row(self, payload):
        r = self._repo("color-repo")
        self._score(r / "ai-readiness-score.json", payload)
        self._write_cfg([r])
        _, body = self._get("/repo-health")
        return body["repos"][0]

    def test_grade_color가_있으면_행에_같은_값으로_실린다(self):
        row = self._health_row({"total": 70, "grade": "C", "grade_color": "amber"})
        self.assertEqual(row["grade_color"], "amber")

    def test_grade_color가_없으면_행에_키가_없다(self):
        row = self._health_row({"total": 70, "grade": "C"})
        self.assertNotIn("grade_color", row)

    def test_모르는_색이면_행에_키가_없다(self):
        row = self._health_row({"total": 70, "grade": "C", "grade_color": "purple"})
        self.assertNotIn("grade_color", row)

    def test_Host가_다르면_403이다(self):
        status, _ = self._get_raw_host("/repo-health", "evil.example:80")
        self.assertEqual(status, 403)


class 금지_검사(unittest.TestCase):
    def test_desk와_page_소스에_프로세스_실행이_없다(self):
        root = Path(__file__).resolve().parent.parent
        for sub in ("desk", "page"):
            for f in (root / sub).glob("*.py"):
                text = f.read_text(encoding="utf-8")
                for word in ("subprocess", "os.system", "Popen"):
                    self.assertNotIn(word, text, f"{f.name}: {word}")


if __name__ == "__main__":
    unittest.main()
