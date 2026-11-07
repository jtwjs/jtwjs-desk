"""scripts/desk.py 단위 · 통합 테스트 — step 3 desk-script.

엣지 5축 커버리지:
- 빈 값·경계: picks --new 후보 0개면 아무것도 출력하지 않음 · prune 대상 0개면 "pruned 0"
- 비정상 입력: ask에 검증 실패 필드가 있는 JSON · raw 파일 경로가 없는 경우 · raw가 JSON이 아닌 경우
- 실패 경로: 같은 id로 ask 두 번(거절) · applied 대상 질문 파일이 없는 경우(거절)
- 상태 전이: ask → pick(가짜 파일) → picks --new에 노출 → applied → picks --new에서 사라짐
  → prune으로 세 파일이 지워짐
- 동시성: 해당 없음 — 각 커맨드는 단일 프로세스 내 순차 실행이고, 쓰기는 전부
  write_json_atomic(os.replace) 하나로 통일된다(ARCHITECTURE "모든 쓰기는 같은 폴더
  임시 파일 + os.replace")

🔴 CRITICAL(ADR-006 "raw가 '-'면 stdin에서, 아니면 파일 경로에서 JSON을 읽는다"):
이 파일의 모든 cmd_ask 호출은 raw 인자로 **파일 경로 또는 "-"만** 넘긴다.
JSON 텍스트를 raw에 직접 넘기지 않는다(2026-11-07 step 3 재시도 — 이전 시도가
이 규약을 어겨 RED 커밋 뒤 테스트 파일을 고쳐야 했고 그래서 폐기됐다).
"""

import io
import json
import os
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from scripts import desk

VALID_ASK = {
    "id": "ask-1",
    "order": 1,
    "issue": None,
    "area": "test-area",
    "question": "선택지 중 뭐가 낫나?",
    "why": "테스트 이유",
    "options": [
        {"key": "a", "label": "선택 A", "recommended": True},
        {"key": "b", "label": "선택 B", "recommended": False},
    ],
    "see": [],
    "aiDecided": [],
    "premiseOpen": False,
}


def _run(argv):
    """desk.main(argv)를 돌리고 (반환값, stdout, stderr)를 돌려준다."""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        result = desk.main(argv)
    return result, out.getvalue(), err.getvalue()


class _DeskHomeTestCase(unittest.TestCase):
    """DESK_HOME을 임시 폴더로 바꿔 끼우는 공용 셋업."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_path = Path(self._tmp.name)
        self.home_dir = self.tmp_path / "home"
        env_patch = patch.dict(os.environ, {"DESK_HOME": str(self.home_dir)})
        env_patch.start()
        self.addCleanup(env_patch.stop)
        self._raw_counter = 0

    def _inbox(self, repo):
        return self.home_dir / "inbox" / repo

    def _write_raw_file(self, data):
        """data를 임시 파일에 쓰고 그 경로(str)를 돌려준다 — raw는 늘 파일 경로다."""
        self._raw_counter += 1
        path = self.tmp_path / f"raw-{self._raw_counter}.json"
        if isinstance(data, str):
            path.write_text(data, encoding="utf-8")
        else:
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return str(path)

    def _ask(self, repo, id_, **overrides):
        """ask 커맨드를 파일 경로로 실제로 호출해 질문 파일을 만든다."""
        data = {**VALID_ASK, "id": id_, **overrides}
        raw_path = self._write_raw_file(data)
        result, out, err = _run(["desk.py", "ask", repo, raw_path])
        if result != 0:
            raise AssertionError(f"_ask 실패: {err}")
        return result

    def _drop_pick(self, repo, id_, at="2026-11-07T10:00:00+09:00", **fields):
        """픽 파일을 직접 떨어뜨린다(지휘·서버를 거치지 않는 테스트 전용 지름길)."""
        pick = {"at": at, "choice": "a", **fields}
        path = self._inbox(repo) / f"{id_}.pick.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(pick, ensure_ascii=False), encoding="utf-8")
        return pick

    def _drop_applied(self, repo, id_, **fields):
        applied = {"appliedAt": time.time(), "issue": None, "followUp": [], **fields}
        path = self._inbox(repo) / f"{id_}.applied.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(applied, ensure_ascii=False), encoding="utf-8")
        return applied


class 지휘가_ask로_판정을_올리는_경우(_DeskHomeTestCase):
    def test_파일경로로_ask하면_inbox에_질문파일이_생긴다(self):
        raw_path = self._write_raw_file(VALID_ASK)
        result, out, err = _run(["desk.py", "ask", "repo-a", raw_path])

        self.assertEqual(result, 0)
        self.assertEqual(err, "")
        ask_file = self._inbox("repo-a") / "ask-1.json"
        self.assertTrue(ask_file.exists())
        data = json.loads(ask_file.read_text(encoding="utf-8"))
        self.assertEqual(data["id"], "ask-1")
        self.assertEqual(data["question"], VALID_ASK["question"])
        self.assertIn("createdAt", data)
        self.assertIsInstance(data["createdAt"], float)

    def test_stdin으로_ask하면_생긴다(self):
        stdin_text = json.dumps({**VALID_ASK, "id": "ask-stdin"})
        with patch("sys.stdin", io.StringIO(stdin_text)):
            result, out, err = _run(["desk.py", "ask", "repo-a", "-"])

        self.assertEqual(result, 0)
        self.assertTrue((self._inbox("repo-a") / "ask-stdin.json").exists())

    def test_같은_id로_두번_ask하면_거절된다(self):
        raw_path_1 = self._write_raw_file(VALID_ASK)
        result_1, _, _ = _run(["desk.py", "ask", "repo-a", raw_path_1])
        self.assertEqual(result_1, 0)
        ask_file = self._inbox("repo-a") / "ask-1.json"
        first_created_at = json.loads(ask_file.read_text(encoding="utf-8"))[
            "createdAt"
        ]

        raw_path_2 = self._write_raw_file(
            {**VALID_ASK, "question": "다른 질문"}
        )
        result_2, out_2, err_2 = _run(["desk.py", "ask", "repo-a", raw_path_2])

        self.assertEqual(result_2, 1)
        self.assertNotEqual(err_2, "")
        data = json.loads(ask_file.read_text(encoding="utf-8"))
        self.assertEqual(data["question"], VALID_ASK["question"])
        self.assertEqual(data["createdAt"], first_created_at)

    def test_검증을_어기면_거절되고_위반필드가_stderr에_있다(self):
        invalid = dict(VALID_ASK)
        del invalid["why"]
        raw_path = self._write_raw_file(invalid)

        result, out, err = _run(["desk.py", "ask", "repo-a", raw_path])

        self.assertEqual(result, 1)
        self.assertIn("why", err)
        self.assertFalse((self._inbox("repo-a") / "ask-1.json").exists())

    def test_raw_파일이_없으면_거절된다(self):
        missing_path = str(self.tmp_path / "no-such-file.json")

        result, out, err = _run(["desk.py", "ask", "repo-a", missing_path])

        self.assertEqual(result, 1)
        self.assertNotEqual(err, "")

    def test_raw가_JSON이_아니면_거절된다(self):
        raw_path = self._write_raw_file("이건 JSON이 아니다")

        result, out, err = _run(["desk.py", "ask", "repo-a", raw_path])

        self.assertEqual(result, 1)
        self.assertNotEqual(err, "")


class picks_new_커맨드(_DeskHomeTestCase):
    def test_반영안된_pick만_한_줄씩_출력한다(self):
        self._ask("repo-a", "ask-1")
        self._drop_pick("repo-a", "ask-1")

        result, out, err = _run(["desk.py", "picks", "--new"])

        self.assertEqual(result, 0)
        lines = [json.loads(line) for line in out.splitlines() if line]
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["repo"], "repo-a")
        self.assertEqual(lines[0]["id"], "ask-1")
        self.assertEqual(lines[0]["choice"], "a")

    def test_후보0개면_아무것도_출력하지_않고_0을_반환한다(self):
        result, out, err = _run(["desk.py", "picks", "--new"])

        self.assertEqual(result, 0)
        self.assertEqual(out, "")

    def test_pick이_없는_ask는_나오지_않는다(self):
        self._ask("repo-a", "ask-1")

        result, out, err = _run(["desk.py", "picks", "--new"])

        self.assertEqual(result, 0)
        self.assertEqual(out, "")

    def test_applied_파일이_있으면_나오지_않는다(self):
        self._ask("repo-a", "ask-1")
        self._drop_pick("repo-a", "ask-1")
        self._drop_applied("repo-a", "ask-1")

        result, out, err = _run(["desk.py", "picks", "--new"])

        self.assertEqual(result, 0)
        self.assertEqual(out, "")

    def test_repo로_필터링한다(self):
        self._ask("repo-a", "ask-1")
        self._drop_pick("repo-a", "ask-1")
        self._ask("repo-b", "ask-2")
        self._drop_pick("repo-b", "ask-2")

        result, out, err = _run(["desk.py", "picks", "--new", "--repo", "repo-a"])

        lines = [json.loads(line) for line in out.splitlines() if line]
        self.assertEqual({line["repo"] for line in lines}, {"repo-a"})

    def test_since_이후에_갱신된_pick만_나온다(self):
        self._ask("repo-a", "ask-1")
        self._ask("repo-a", "ask-2")
        earlier = datetime(2026, 11, 7, 10, 0, 0, tzinfo=timezone.utc)
        later = datetime(2026, 11, 7, 12, 0, 0, tzinfo=timezone.utc)
        self._drop_pick("repo-a", "ask-1", at=earlier.isoformat())
        self._drop_pick("repo-a", "ask-2", at=later.isoformat())
        since = (earlier + timedelta(hours=1)).timestamp()

        result, out, err = _run(
            ["desk.py", "picks", "--new", "--since", str(since)]
        )

        lines = [json.loads(line) for line in out.splitlines() if line]
        self.assertEqual({line["id"] for line in lines}, {"ask-2"})

    def test_다시_고른_선택은_since_이후로_다시_걸린다(self):
        self._ask("repo-a", "ask-1")
        older = datetime(2026, 11, 7, 9, 0, 0, tzinfo=timezone.utc)
        self._drop_pick("repo-a", "ask-1", at=older.isoformat())
        since = older.timestamp()  # 이미 읽은 시점

        # 다시 고른 선택 — at이 갱신된다(PRD desk-repick)
        repicked = older + timedelta(hours=1)
        self._drop_pick("repo-a", "ask-1", at=repicked.isoformat())

        result, out, err = _run(
            ["desk.py", "picks", "--new", "--since", str(since)]
        )

        lines = [json.loads(line) for line in out.splitlines() if line]
        self.assertEqual({line["id"] for line in lines}, {"ask-1"})


class applied_커맨드(_DeskHomeTestCase):
    def test_질문파일이_없으면_거절된다(self):
        result, out, err = _run(["desk.py", "applied", "repo-a", "no-such-id"])

        self.assertEqual(result, 1)
        self.assertNotEqual(err, "")
        self.assertFalse(
            (self._inbox("repo-a") / "no-such-id.applied.json").exists()
        )

    def test_applied_파일이_issue_followup과_함께_생긴다(self):
        self._ask("repo-a", "ask-1")

        result, out, err = _run(
            [
                "desk.py",
                "applied",
                "repo-a",
                "ask-1",
                "--issue",
                "https://example.test/issues/1",
                "--follow-up",
                "#2",
                "--follow-up",
                "#3",
            ]
        )

        self.assertEqual(result, 0)
        applied_path = self._inbox("repo-a") / "ask-1.applied.json"
        self.assertTrue(applied_path.exists())
        data = json.loads(applied_path.read_text(encoding="utf-8"))
        self.assertEqual(data["issue"], "https://example.test/issues/1")
        self.assertEqual(data["followUp"], ["#2", "#3"])
        self.assertIn("appliedAt", data)

    def test_issue_followup_없이도_생긴다(self):
        self._ask("repo-a", "ask-1")

        result, out, err = _run(["desk.py", "applied", "repo-a", "ask-1"])

        self.assertEqual(result, 0)
        data = json.loads(
            (self._inbox("repo-a") / "ask-1.applied.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertIsNone(data["issue"])
        self.assertEqual(data["followUp"], [])

    def test_재반영하면_덮어쓴다(self):
        self._ask("repo-a", "ask-1")
        _run(["desk.py", "applied", "repo-a", "ask-1", "--issue", "first"])

        result, out, err = _run(
            ["desk.py", "applied", "repo-a", "ask-1", "--issue", "second"]
        )

        self.assertEqual(result, 0)
        data = json.loads(
            (self._inbox("repo-a") / "ask-1.applied.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(data["issue"], "second")


class prune_커맨드(_DeskHomeTestCase):
    def test_대상0개면_pruned_0을_출력한다(self):
        result, out, err = _run(["desk.py", "prune", "--days", "7"])

        self.assertEqual(result, 0)
        self.assertEqual(out.strip(), "pruned 0")

    def test_inbox가_아예_없어도_pruned_0을_출력한다(self):
        result, out, err = _run(["desk.py", "prune"])

        self.assertEqual(result, 0)
        self.assertEqual(out.strip(), "pruned 0")

    def test_days_0이면_방금_반영된_판정도_즉시_지워진다(self):
        self._ask("repo-a", "ask-1")
        self._drop_pick("repo-a", "ask-1")
        _run(["desk.py", "applied", "repo-a", "ask-1"])

        result, out, err = _run(["desk.py", "prune", "--days", "0"])

        self.assertEqual(result, 0)
        self.assertEqual(out.strip(), "pruned 1")
        repo_dir = self._inbox("repo-a")
        self.assertFalse((repo_dir / "ask-1.json").exists())
        self.assertFalse((repo_dir / "ask-1.pick.json").exists())
        self.assertFalse((repo_dir / "ask-1.applied.json").exists())

    def test_반영안된_판정은_지우지_않는다(self):
        self._ask("repo-a", "ask-1")

        result, out, err = _run(["desk.py", "prune", "--days", "0"])

        self.assertEqual(result, 0)
        self.assertEqual(out.strip(), "pruned 0")
        self.assertTrue((self._inbox("repo-a") / "ask-1.json").exists())

    def test_pick_파일이_없어도_무시하고_지운다(self):
        self._ask("repo-a", "ask-1")
        _run(["desk.py", "applied", "repo-a", "ask-1"])

        result, out, err = _run(["desk.py", "prune", "--days", "0"])

        self.assertEqual(result, 0)
        self.assertEqual(out.strip(), "pruned 1")
        repo_dir = self._inbox("repo-a")
        self.assertFalse((repo_dir / "ask-1.json").exists())
        self.assertFalse((repo_dir / "ask-1.applied.json").exists())

    def test_기간이_지나지_않았으면_지우지_않는다(self):
        self._ask("repo-a", "ask-1")
        _run(["desk.py", "applied", "repo-a", "ask-1"])

        result, out, err = _run(["desk.py", "prune", "--days", "7"])

        self.assertEqual(result, 0)
        self.assertEqual(out.strip(), "pruned 0")
        self.assertTrue((self._inbox("repo-a") / "ask-1.applied.json").exists())


class 왕복_시나리오(_DeskHomeTestCase):
    def test_ask_pick_picks_applied_prune_한_바퀴(self):
        self._ask("repo-a", "ask-1")

        result, out, err = _run(["desk.py", "picks", "--new"])
        self.assertEqual(result, 0)
        self.assertEqual(out, "")  # pick이 아직 없다

        self._drop_pick("repo-a", "ask-1")
        result, out, err = _run(["desk.py", "picks", "--new"])
        self.assertEqual(result, 0)
        lines = [json.loads(line) for line in out.splitlines() if line]
        self.assertEqual([line["id"] for line in lines], ["ask-1"])

        result, out, err = _run(["desk.py", "applied", "repo-a", "ask-1"])
        self.assertEqual(result, 0)

        result, out, err = _run(["desk.py", "picks", "--new"])
        self.assertEqual(result, 0)
        self.assertEqual(out, "")  # 반영됐으니 더는 안 나온다

        result, out, err = _run(["desk.py", "prune", "--days", "0"])
        self.assertEqual(result, 0)
        self.assertEqual(out.strip(), "pruned 1")
        repo_dir = self._inbox("repo-a")
        self.assertFalse((repo_dir / "ask-1.json").exists())
        self.assertFalse((repo_dir / "ask-1.pick.json").exists())
        self.assertFalse((repo_dir / "ask-1.applied.json").exists())


class main_인자_오류(_DeskHomeTestCase):
    def test_모르는_커맨드는_2로_종료한다(self):
        err = io.StringIO()
        with redirect_stderr(err):
            with self.assertRaises(SystemExit) as ctx:
                desk.main(["desk.py", "weird-command"])
        self.assertEqual(ctx.exception.code, 2)

    def test_커맨드없이_부르면_2로_종료한다(self):
        err = io.StringIO()
        with redirect_stderr(err):
            with self.assertRaises(SystemExit) as ctx:
                desk.main(["desk.py"])
        self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
