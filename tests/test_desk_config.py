"""desk/config.py · desk/paths.py 신규 경로 함수 단위 테스트 — step 1 desk-config.

엣지 5축: 빈 값(없는 파일 · 빈 목록) · 비정상 입력(깨진 JSON · 객체 아님 · 키 타입 오류)
· 실패 경로(예외를 던지지 않음) · 상태 전이(config → conductor → none 우선순위) · 동시성 해당 없음.
픽스처는 전부 지어낸 값.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

from desk import config, paths

ENV_KEYS = ("DESK_CONFIG", "DESK_CONDUCTOR", "DESK_HOME")


class _EnvBase(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.pop(k, None) for k in ENV_KEYS}
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        os.environ["DESK_CONFIG"] = str(self.tmp / "config.json")
        os.environ["DESK_CONDUCTOR"] = str(self.tmp / "conductor.json")

    def tearDown(self):
        self._tmp.cleanup()
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def write_config(self, data):
        text = data if isinstance(data, str) else json.dumps(data)
        (self.tmp / "config.json").write_text(text, encoding="utf-8")

    def write_conductor(self, data):
        (self.tmp / "conductor.json").write_text(json.dumps(data), encoding="utf-8")


class 경로_함수(_EnvBase):
    def test_config_path_환경변수가_우선(self):
        self.assertEqual(paths.config_path(), self.tmp / "config.json")

    def test_config_path_기본값(self):
        del os.environ["DESK_CONFIG"]
        self.assertEqual(
            paths.config_path(), Path.home() / ".config" / "jtwjs-desk" / "config.json"
        )

    def test_conductor_path_환경변수가_우선(self):
        self.assertEqual(paths.conductor_path(), self.tmp / "conductor.json")

    def test_conductor_path_기본값(self):
        del os.environ["DESK_CONDUCTOR"]
        self.assertEqual(paths.conductor_path(), Path.home() / ".claude" / "conductor.json")

    def test_review_dir_와_share_dir은_desk_home_아래(self):
        os.environ["DESK_HOME"] = str(self.tmp / "home")
        self.assertEqual(paths.review_dir("sample-repo"), self.tmp / "home" / "review" / "sample-repo")
        self.assertEqual(paths.share_dir("sample-repo"), self.tmp / "home" / "share" / "sample-repo")


class load_config(_EnvBase):
    def test_둘_다_없으면_none과_빈_repos(self):
        c = config.load_config()
        self.assertEqual(c["source"], "none")
        self.assertEqual(c["repos"], [])
        self.assertIsNone(c["vault"])
        self.assertIsNone(c["criteria_file"])
        self.assertEqual(c["evidence_globs"], [])
        self.assertEqual(c["daily_dir"], Path.home() / ".claude" / "daily")

    def test_설정_파일이_있으면_그것만_읽는다(self):
        self.write_config(
            {
                "repos": ["/work/sample-repo", "/work/other-repo"],
                "vault": "/work/vault",
                "criteria_file": "/work/criteria.md",
                "daily_dir": "/work/daily",
                "evidence_globs": ["docs/evidence.md"],
            }
        )
        self.write_conductor({"repos": ["/work/ignored"], "seat": "/work/ignored-vault"})
        c = config.load_config()
        self.assertEqual(c["source"], "config")
        self.assertEqual(c["repos"], [Path("/work/sample-repo"), Path("/work/other-repo")])
        self.assertEqual(c["vault"], Path("/work/vault"))
        self.assertEqual(c["criteria_file"], Path("/work/criteria.md"))
        self.assertEqual(c["daily_dir"], Path("/work/daily"))
        self.assertEqual(c["evidence_globs"], ["docs/evidence.md"])
        self.assertIsNone(c["error"])

    def test_설정_파일이_없으면_conductor로_폴백(self):
        self.write_conductor({"repos": ["/work/sample-repo"], "seat": "/work/vault"})
        c = config.load_config()
        self.assertEqual(c["source"], "conductor")
        self.assertEqual(c["repos"], [Path("/work/sample-repo")])
        self.assertEqual(c["vault"], Path("/work/vault"))
        self.assertIsNone(c["criteria_file"])

    def test_틸드를_펼친다(self):
        self.write_config({"repos": ["~/sample-repo"], "vault": "~/vault"})
        c = config.load_config()
        self.assertEqual(c["repos"], [Path.home() / "sample-repo"])
        self.assertEqual(c["vault"], Path.home() / "vault")

    def test_conductor의_틸드도_펼친다(self):
        self.write_conductor({"repos": ["~/sample-repo"], "seat": "~/vault"})
        c = config.load_config()
        self.assertEqual(c["repos"], [Path.home() / "sample-repo"])
        self.assertEqual(c["vault"], Path.home() / "vault")

    def test_evidence_globs_기본은_빈_목록(self):
        self.write_config({"repos": ["/work/sample-repo"]})
        self.assertEqual(config.load_config()["evidence_globs"], [])

    def test_깨진_JSON은_폴백하지_않고_error(self):
        self.write_config("{not json")
        self.write_conductor({"repos": ["/work/ignored"]})
        c = config.load_config()
        self.assertEqual(c["source"], "config")
        self.assertEqual(c["repos"], [])
        self.assertTrue(c["error"])

    def test_최상위가_객체가_아니면_폴백하지_않고_error(self):
        self.write_config(["a", "b"])
        self.write_conductor({"repos": ["/work/ignored"]})
        c = config.load_config()
        self.assertEqual(c["source"], "config")
        self.assertEqual(c["repos"], [])
        self.assertTrue(c["error"])

    def test_키_타입이_틀리면_그_키만_기본값과_error(self):
        self.write_config({"repos": "/work/sample-repo", "vault": "/work/vault"})
        c = config.load_config()
        self.assertEqual(c["source"], "config")
        self.assertEqual(c["repos"], [])
        self.assertEqual(c["vault"], Path("/work/vault"))
        self.assertTrue(c["error"])

    def test_깨진_conductor도_예외를_던지지_않는다(self):
        (self.tmp / "conductor.json").write_text("{broken", encoding="utf-8")
        c = config.load_config()
        self.assertEqual(c["source"], "conductor")
        self.assertEqual(c["repos"], [])
        self.assertTrue(c["error"])


class unregistered(unittest.TestCase):
    def test_repos에_없는_이름만_순서대로_중복_제거(self):
        repos = [Path("/work/sample-repo")]
        self.assertEqual(
            config.unregistered(["new-a", "sample-repo", "new-b", "new-a"], repos),
            ["new-a", "new-b"],
        )

    def test_빈_입력(self):
        self.assertEqual(config.unregistered([], []), [])
        self.assertEqual(config.unregistered(["x"], []), ["x"])


if __name__ == "__main__":
    unittest.main()
