"""desk/config.py 가설 원장 키 단위 테스트 — step 2 signal-config.

엣지 5축: 빈 값(키 없음 · 빈 문자열) · 비정상 입력(숫자 경로 · 문자열/0/bool 임계값)
· 실패 경로(config 파일 없음) · 상태 전이 해당 없음 · 동시성 해당 없음.
픽스처는 전부 지어낸 값.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

from desk import config

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
        (self.tmp / "config.json").write_text(json.dumps(data), encoding="utf-8")


class 원장_경로_키(_EnvBase):
    def test_키가_없으면_둘_다_None(self):
        self.write_config({"repos": []})
        cfg = config.load_config()
        self.assertIsNone(cfg["hypothesis_ledger"])
        self.assertIsNone(cfg["hypothesis_streak_threshold"])
        self.assertIsNone(cfg["error"])

    def test_설정_파일이_없어도_None(self):
        cfg = config.load_config()
        self.assertIsNone(cfg["hypothesis_ledger"])
        self.assertIsNone(cfg["hypothesis_streak_threshold"])

    def test_경로_문자열은_그대로(self):
        self.write_config({"hypothesis_ledger": "/tmp/ledger.jsonl"})
        cfg = config.load_config()
        self.assertEqual(cfg["hypothesis_ledger"], Path("/tmp/ledger.jsonl"))
        self.assertIsNone(cfg["error"])

    def test_빈_문자열은_None(self):
        self.write_config({"hypothesis_ledger": ""})
        cfg = config.load_config()
        self.assertIsNone(cfg["hypothesis_ledger"])
        self.assertIsNone(cfg["error"])

    def test_숫자_경로는_타입_오류(self):
        self.write_config({"hypothesis_ledger": 5})
        cfg = config.load_config()
        self.assertIsNone(cfg["hypothesis_ledger"])
        self.assertIn("hypothesis_ledger 타입 오류", cfg["error"])


class 연속_기준_횟수_키(_EnvBase):
    def test_정수_2는_그대로(self):
        self.write_config({"hypothesis_streak_threshold": 2})
        cfg = config.load_config()
        self.assertEqual(cfg["hypothesis_streak_threshold"], 2)
        self.assertIsNone(cfg["error"])

    def test_문자열_0_bool은_None과_오류(self):
        for bad in ("2", 0, True):
            with self.subTest(bad=bad):
                self.write_config({"hypothesis_streak_threshold": bad})
                cfg = config.load_config()
                self.assertIsNone(cfg["hypothesis_streak_threshold"])
                self.assertIn("hypothesis_streak_threshold 타입 오류", cfg["error"])


if __name__ == "__main__":
    unittest.main()
