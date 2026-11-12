"""GET /competency/workflow · GET /competency/fullstack (step 6).

엣지 5축: 빈 값(설정 없음 · vault 없음) · 비정상 입력(friction 형식 불일치 · Host) ·
실패 경로(파일 없음 · 레포 폴더 없음) · 상태 전이(해당 없음 — 읽기 전용) · 동시성(해당 없음).
🔴 픽스처는 임시 폴더 안의 지어낸 파일이다.
"""
import json
import os
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

import test_desk_server as base

OBS = """# 관찰 (지어낸 픽스처)

## 열린 것
| 패턴 | 종류 | 횟수 | 마지막 | 근거 |
|---|---|---|---|---|
| 샘플 패턴 하나 | 반복 | 2 | 2026-01-01 | a |
| 샘플 패턴 둘 | 반복 | 4 | 2026-01-02 | b |

## 닫힌 것
| 패턴 | 종류 | 횟수 | 마지막 | 근거 |
|---|---|---|---|---|
| 닫힌 패턴 | 반복 | 9 | 2026-01-01 | c |
"""

FRICTION = """# friction (지어낸 픽스처)

| 패턴 | 상태 | 횟수 |
|---|---|---|
| 샘플 마찰 | 열림 | 3 |
| 닫힌 마찰 | 닫힘 | 8 |
"""

BAD_FRICTION = """# friction

| 아무 | 열 |
|---|---|
| SECRET-RAW-TEXT | 이상한 형식 |
"""

INBOX = """# 학습 수신함 (지어낸 픽스처)

## 2026-01-01 · 설명 가능 카드
- 종류: 기술 · 출처: AI 설명
- 이 레포 어디: `src/sample/view.tsx`
- 요지: 요지1
- 상태: 내 말로 설명 가능
- vault:

## 2026-01-02 · 모름 카드
- 종류: 기술 · 출처: AI 설명
- 이 레포 어디: `src/sample/other.tsx`
- 요지: 요지2
- 상태: 모름
- vault:

## 2026-01-03 · 들음 카드
- 종류: 기술 · 출처: AI 설명
- 이 레포 어디: `src/sample/view2.tsx`
- 요지: 요지3
- 상태: 설명 들음
- vault:

## 2026-01-04 · 백엔드 카드
- 종류: 기술 · 출처: AI 설명
- 이 레포 어디: `api/sample.py`
- 요지: 요지4
- 상태: 모름
- vault:

## 2026-01-05 · 도메인 카드
- 종류: 도메인 · 출처: 내가 물음
- 이 레포 어디: `docs/x.md`
- 요지: 요지5
- 상태: 모름
- vault:

## 2026-01-06 · 직무 카드
- 종류: 직무 · 출처: 내가 물음
- 이 레포 어디: `docs/y.md`
- 요지: 요지6
- 상태: 모름
- vault:

## 2026-01-07 · 막힘 카드
- 종류: 막힌 질문 · 출처: 내가 물음
- 이 레포 어디: `src/z.py`
- 요지: 요지7
- 상태: 모름
- vault:
"""


class _CompCase(base._ServerTestCase):
    def setUp(self):
        super().setUp()
        tmp = Path(self._tmp.name)
        self.tmp = tmp
        self.repo_root = tmp / "fake-repo"
        (self.repo_root / ".claude").mkdir(parents=True)
        (self.repo_root / ".claude" / "observations.md").write_text(OBS, encoding="utf-8")
        (self.repo_root / "_learn").mkdir()
        (self.repo_root / "_learn" / "inbox.md").write_text(INBOX, encoding="utf-8")
        self.vault = tmp / "vault"
        self.cfg_path = tmp / "config.json"
        env = patch.dict(os.environ, {
            "DESK_CONFIG": str(self.cfg_path),
            "DESK_CONDUCTOR": str(tmp / "no-conductor.json"),
        })
        env.start()
        self.addCleanup(env.stop)

    def _write_cfg(self, repos, vault=None):
        cfg = {"repos": [str(r) for r in repos]}
        if vault is not None:
            cfg["vault"] = str(vault)
        self.cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

    def _write_friction(self, text):
        d = self.vault / "1_MyBrain" / "brain" / "friction"
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.md").write_text(text, encoding="utf-8")

    def _raw(self, path):
        return urllib.request.urlopen(self._url(path), timeout=1).read().decode("utf-8")


class 통합_GET_workflow(_CompCase):
    def test_설정이_없으면_source_none과_빈_rows다(self):
        status, body = self._get("/competency/workflow")
        self.assertEqual(status, 200)
        self.assertEqual(body["config"]["source"], "none")
        self.assertEqual(body["rows"], [])

    def test_observations_행이_횟수_내림차순이고_3회_이상만_강조된다(self):
        self._write_cfg([self.repo_root])
        _, body = self._get("/competency/workflow")
        obs = [r for r in body["rows"] if r["source"] == "observations"]
        self.assertEqual([r["count"] for r in obs], [4, 2])
        self.assertEqual([r["highlight"] for r in obs], [True, False])
        self.assertTrue(all(r["repo"] == "fake-repo" for r in obs))
        self.assertNotIn("닫힌 패턴", json.dumps(body, ensure_ascii=False))

    def test_friction_열림_보류_행이_같은_목록에_섞인다(self):
        self._write_friction(FRICTION)
        self._write_cfg([self.repo_root], self.vault)
        _, body = self._get("/competency/workflow")
        fr = [r for r in body["rows"] if r["source"] == "friction"]
        self.assertEqual(len(fr), 1)
        self.assertEqual(fr[0]["pattern"], "샘플 마찰")
        self.assertNotIn("repo", fr[0])
        self.assertEqual([r["count"] for r in body["rows"]], [4, 3, 2])

    def test_friction_형식이_다르면_unparsed_행이고_원문은_응답에_없다(self):
        self._write_friction(BAD_FRICTION)
        self._write_cfg([self.repo_root], self.vault)
        text = self._raw("/competency/workflow")
        self.assertNotIn("SECRET-RAW-TEXT", text)
        rows = json.loads(text)["rows"]
        self.assertTrue(any(r["source"] == "friction" and r.get("unparsed") for r in rows))

    def test_vault가_설정됐는데_friction_파일이_없으면_missing에_파일_없음이다(self):
        self._write_cfg([self.repo_root], self.vault)
        _, body = self._get("/competency/workflow")
        self.assertIn({"repo": "(vault)", "what": "friction", "missing": "파일 없음"},
                      body["missing"])

    def test_vault가_없으면_friction_missing_행을_내지_않는다(self):
        self._write_cfg([self.repo_root])
        _, body = self._get("/competency/workflow")
        self.assertFalse(any(m["repo"] == "(vault)" for m in body["missing"]))

    def test_파일_없는_레포와_폴더_없는_레포가_missing에_들어간다(self):
        bare = self.tmp / "bare-repo"
        bare.mkdir()
        self._write_cfg([bare, self.tmp / "ghost-repo"])
        _, body = self._get("/competency/workflow")
        self.assertIn({"repo": "bare-repo", "what": "observations", "missing": "파일 없음"},
                      body["missing"])
        self.assertIn({"repo": "ghost-repo", "what": "repo", "missing": "경로 없음"},
                      body["missing"])

    def test_Host가_다르면_403이다(self):
        status, _ = self._get_raw_host("/competency/workflow", "evil.example:80")
        self.assertEqual(status, 403)


class 통합_GET_fullstack(_CompCase):
    def test_설정이_없으면_빈_영역_키가_모두_있다(self):
        status, body = self._get("/competency/fullstack")
        self.assertEqual(status, 200)
        self.assertEqual(body["config"]["source"], "none")
        self.assertEqual(body["groups"],
                         {"fe": [], "be": [], "infra": [], "domain": [], "미분류": []})

    def test_카드가_영역별로_묶이고_상태_순서로_정렬된다(self):
        self._write_cfg([self.repo_root])
        _, body = self._get("/competency/fullstack")
        g = body["groups"]
        self.assertEqual([c["title"] for c in g["fe"]], ["모름 카드", "들음 카드", "설명 가능 카드"])
        self.assertEqual([c["status"] for c in g["fe"]],
                         ["모름", "설명 들음", "내 말로 설명 가능"])
        self.assertEqual([c["title"] for c in g["be"]], ["백엔드 카드"])
        self.assertEqual([c["title"] for c in g["domain"]], ["도메인 카드"])
        self.assertEqual(g["infra"], [])
        self.assertEqual(g["미분류"], [])

    def test_카드_항목은_정해진_키만_가진다(self):
        self._write_cfg([self.repo_root])
        _, body = self._get("/competency/fullstack")
        card = body["groups"]["be"][0]
        self.assertEqual(set(card), {"repo", "title", "kind", "status", "where", "summary"})
        self.assertEqual(card["repo"], "fake-repo")
        self.assertEqual(card["kind"], "기술")

    def test_직무와_막힌_질문_카드는_빠진다(self):
        self._write_cfg([self.repo_root])
        _, body = self._get("/competency/fullstack")
        titles = [c["title"] for g in body["groups"].values() for c in g]
        self.assertNotIn("직무 카드", titles)
        self.assertNotIn("막힘 카드", titles)
        self.assertEqual(len(titles), 5)

    def test_inbox가_없거나_레포_폴더가_없으면_missing이다(self):
        bare = self.tmp / "bare-repo"
        bare.mkdir()
        self._write_cfg([bare, self.tmp / "ghost-repo"])
        _, body = self._get("/competency/fullstack")
        self.assertIn({"repo": "bare-repo", "what": "inbox", "missing": "파일 없음"},
                      body["missing"])
        self.assertIn({"repo": "ghost-repo", "what": "repo", "missing": "경로 없음"},
                      body["missing"])

    def test_Host가_다르면_403이다(self):
        status, _ = self._get_raw_host("/competency/fullstack", "evil.example:80")
        self.assertEqual(status, 403)


if __name__ == "__main__":
    unittest.main()
