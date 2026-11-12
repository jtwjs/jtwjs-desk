"""desk/config.py 우편함 경로 키 단위 테스트 — step 2 routine-config.

엣지 5축: 빈 값(키 없음 · 빈 문자열) · 비정상 입력(숫자·리스트 타입 오류)
· 실패 경로(깨진 config.json은 기존 동작 유지) · 상태 전이 해당 없음 · 동시성 해당 없음.
픽스처는 전부 지어낸 값.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

from desk import config

ENV_KEYS = ("DESK_CONFIG", "DESK_CONDUCTOR", "DESK_HOME")
KEYS = ("routine_questions", "routine_answers")


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


class 우편함_경로_키(_EnvBase):
    def test_키가_없으면_둘_다_None(self):
        self.write_config({"repos": []})
        cfg = config.load_config()
        for k in KEYS:
            self.assertIsNone(cfg[k])
        self.assertIsNone(cfg["error"])

    def test_설정_파일이_없어도_둘_다_None(self):
        cfg = config.load_config()
        for k in KEYS:
            self.assertIn(k, cfg)
            self.assertIsNone(cfg[k])

    def test_문자열이면_Path(self):
        self.write_config({"routine_questions": "/x/q.jsonl", "routine_answers": "/x/a.jsonl"})
        cfg = config.load_config()
        self.assertEqual(cfg["routine_questions"], Path("/x/q.jsonl"))
        self.assertEqual(cfg["routine_answers"], Path("/x/a.jsonl"))
        self.assertIsNone(cfg["error"])

    def test_틸드를_확장한다(self):
        self.write_config({"routine_questions": "~/q.jsonl"})
        cfg = config.load_config()
        self.assertEqual(cfg["routine_questions"], Path.home() / "q.jsonl")

    def test_하나만_있으면_다른_하나는_None(self):
        self.write_config({"routine_answers": "/x/a.jsonl"})
        cfg = config.load_config()
        self.assertIsNone(cfg["routine_questions"])
        self.assertEqual(cfg["routine_answers"], Path("/x/a.jsonl"))

    def test_빈_문자열은_None이고_오류_아님(self):
        self.write_config({"routine_questions": "", "routine_answers": ""})
        cfg = config.load_config()
        for k in KEYS:
            self.assertIsNone(cfg[k])
        self.assertIsNone(cfg["error"])

    def test_타입_오류는_None과_error에_이름(self):
        for bad in (123, ["a"], {"a": 1}, True, None):
            for k in KEYS:
                with self.subTest(key=k, bad=bad):
                    self.write_config({k: bad})
                    cfg = config.load_config()
                    self.assertIsNone(cfg[k])
                    self.assertIn(f"{k} 타입 오류", cfg["error"])

    def test_타입_오류가_다른_키를_망치지_않는다(self):
        self.write_config({"routine_questions": 5, "routine_answers": "/x/a.jsonl"})
        cfg = config.load_config()
        self.assertIsNone(cfg["routine_questions"])
        self.assertEqual(cfg["routine_answers"], Path("/x/a.jsonl"))

    def test_깨진_config는_기존_동작_유지(self):
        self.write_config("{not json")
        cfg = config.load_config()
        self.assertEqual(cfg["source"], "config")
        self.assertIn("config.json 읽기 실패", cfg["error"])
        for k in KEYS:
            self.assertIsNone(cfg[k])


class conductor_폴백(_EnvBase):
    def test_conductor_폴백에서는_None(self):
        (self.tmp / "conductor.json").write_text(
            json.dumps({"repos": ["/r"], "seat": "/v"}), encoding="utf-8"
        )
        cfg = config.load_config()
        self.assertEqual(cfg["source"], "conductor")
        for k in KEYS:
            self.assertIsNone(cfg[k])

    def test_폴백에_같은_이름_키가_있어도_무시(self):
        (self.tmp / "conductor.json").write_text(
            json.dumps({"repos": [], "routine_questions": "/x/q.jsonl"}), encoding="utf-8"
        )
        cfg = config.load_config()
        self.assertIsNone(cfg["routine_questions"])

    def test_둘_다_없으면_none_소스에서_None(self):
        cfg = config.load_config()
        self.assertEqual(cfg["source"], "none")
        for k in KEYS:
            self.assertIsNone(cfg[k])


class 기존_키_불변(_EnvBase):
    def test_기존_키_값이_안_바뀐다(self):
        self.write_config(
            {
                "repos": ["/r1"],
                "vault": "/v",
                "criteria_file": "/c.md",
                "daily_dir": "/d",
                "evidence_globs": ["*.md"],
                "routine_questions": "/x/q.jsonl",
                "routine_answers": "/x/a.jsonl",
            }
        )
        cfg = config.load_config()
        self.assertEqual(cfg["source"], "config")
        self.assertEqual(cfg["repos"], [Path("/r1")])
        self.assertEqual(cfg["vault"], Path("/v"))
        self.assertEqual(cfg["criteria_file"], Path("/c.md"))
        self.assertEqual(cfg["daily_dir"], Path("/d"))
        self.assertEqual(cfg["evidence_globs"], ["*.md"])
        self.assertIsNone(cfg["error"])


if __name__ == "__main__":
    unittest.main()
