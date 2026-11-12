"""hooks/desk_hook.py 단위 · 통합 테스트 — step 2 desk-hook.

엣지 5축 커버리지:
- 빈 값·경계: argv에 이벤트 이름이 없는 경우 · notification_type이 없는 경우
- 비정상 입력: stdin이 유효한 JSON이 아닌 경우 · 모르는 이벤트 이름 · 모르는 notification_type
- 실패 경로: 어떤 예외든 exit 0 · 빈 stdout(ADR-002 "예외가 나도 세션을 막지 않는다")
- 상태 전이: 이벤트별 상태 매핑(ADR-002 표) · SessionEnd에서 상태 파일 삭제
- 동시성: 해당 없음 — 상태 파일 하나 = 세션 하나. 세션마다 다른 파일에 원자적으로 쓴다
  (ARCHITECTURE "상태 파일 하나 = 세션 하나. 다른 세션 파일을 건드리지 않아서 잠금이 없다")
"""

import io
import json
import os
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from hooks import desk_hook


def _run_main(argv, payload):
    """main을 가짜 stdin으로 돌리고 (반환값, stdout 내용)을 돌려준다."""
    stdin_text = payload if isinstance(payload, str) else json.dumps(payload)
    out = io.StringIO()
    with patch("sys.stdin", io.StringIO(stdin_text)), redirect_stdout(out):
        result = desk_hook.main(argv)
    return result, out.getvalue()


class 코어_map_status_ADR_002_표(unittest.TestCase):
    def test_SessionStart는_입력대기다(self):
        self.assertEqual(desk_hook.map_status("SessionStart", None), "입력 대기")

    def test_UserPromptSubmit는_작업중이다(self):
        self.assertEqual(desk_hook.map_status("UserPromptSubmit", None), "작업 중")

    def test_PostToolUse는_작업중이다(self):
        self.assertEqual(desk_hook.map_status("PostToolUse", None), "작업 중")

    def test_PreCompact는_작업중이다(self):
        self.assertEqual(desk_hook.map_status("PreCompact", None), "작업 중")

    def test_Stop은_입력대기다(self):
        self.assertEqual(desk_hook.map_status("Stop", None), "입력 대기")

    def test_Notification_permission_prompt는_승인대기다(self):
        self.assertEqual(
            desk_hook.map_status("Notification", "permission_prompt"), "승인 대기"
        )

    def test_Notification_idle_prompt는_입력대기다(self):
        self.assertEqual(
            desk_hook.map_status("Notification", "idle_prompt"), "입력 대기"
        )

    def test_Notification_모르는_타입이면_None이다(self):
        self.assertIsNone(desk_hook.map_status("Notification", "etc"))

    def test_Notification_타입이_없으면_None이다(self):
        self.assertIsNone(desk_hook.map_status("Notification", None))

    def test_SessionEnd는_None이다(self):
        self.assertIsNone(desk_hook.map_status("SessionEnd", None))

    def test_모르는_이벤트는_None이다(self):
        self.assertIsNone(desk_hook.map_status("WeirdEvent", None))


class 코어_needs_server_check(unittest.TestCase):
    def test_SessionStart는_참이다(self):
        self.assertTrue(desk_hook.needs_server_check("SessionStart"))

    def test_그_밖_이벤트는_거짓이다(self):
        for event in (
            "UserPromptSubmit",
            "PostToolUse",
            "Notification",
            "PreCompact",
            "Stop",
            "SessionEnd",
        ):
            with self.subTest(event=event):
                self.assertFalse(desk_hook.needs_server_check(event))


class 코어_needs_ntfy(unittest.TestCase):
    def test_Notification_permission_prompt는_참이다(self):
        self.assertTrue(desk_hook.needs_ntfy("Notification", "permission_prompt"))

    def test_Notification_idle_prompt는_거짓이다(self):
        self.assertFalse(desk_hook.needs_ntfy("Notification", "idle_prompt"))

    def test_Notification_타입이_없으면_거짓이다(self):
        self.assertFalse(desk_hook.needs_ntfy("Notification", None))

    def test_SessionStart는_거짓이다(self):
        self.assertFalse(desk_hook.needs_ntfy("SessionStart", None))


class 코어_ensure_server_주입된_함수로만_판단한다(unittest.TestCase):
    def test_check_fn이_거짓이면_spawn_fn을_부른다(self):
        calls = []
        desk_hook.ensure_server(
            check_fn=lambda: False, spawn_fn=lambda: calls.append(1)
        )
        self.assertEqual(calls, [1])

    def test_check_fn이_참이면_spawn_fn을_안_부른다(self):
        calls = []
        desk_hook.ensure_server(
            check_fn=lambda: True, spawn_fn=lambda: calls.append(1)
        )
        self.assertEqual(calls, [])


class _DeskEnvTestCase(unittest.TestCase):
    """DESK_RUN·DESK_HOME을 임시 폴더로 바꿔 끼우는 공용 셋업."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_path = Path(self._tmp.name)
        self.run_dir = self.tmp_path / "run"
        self.home_dir = self.tmp_path / "home"
        self.cwd_dir = self.tmp_path / "work"
        self.cwd_dir.mkdir()
        env_patch = patch.dict(
            os.environ,
            {"DESK_RUN": str(self.run_dir), "DESK_HOME": str(self.home_dir)},
        )
        env_patch.start()
        self.addCleanup(env_patch.stop)

    def _session_file(self, session_id):
        return self.run_dir / "sessions" / f"{session_id}.json"


class 메인_SessionStart_이벤트(_DeskEnvTestCase):
    def test_상태파일이_repo_branch_status_lastAt로_쓰이고_서버확인을_부른다(self):
        payload = {"session_id": "sess-1", "cwd": str(self.cwd_dir)}
        with patch.object(desk_hook, "ensure_server") as ensure_mock:
            result, stdout = _run_main(["desk_hook.py", "SessionStart"], payload)

        self.assertEqual(result, 0)
        self.assertEqual(stdout, "")
        ensure_mock.assert_called_once_with()

        data = json.loads(self._session_file("sess-1").read_text(encoding="utf-8"))
        self.assertEqual(data["repo"], self.cwd_dir.name)
        self.assertEqual(data["branch"], "")
        self.assertEqual(data["status"], "입력 대기")
        self.assertLessEqual(abs(data["lastAt"] - time.time()), 5)


class 메인_UserPromptSubmit_이벤트(_DeskEnvTestCase):
    def test_상태가_작업중으로_쓰이고_서버확인을_안_한다(self):
        payload = {"session_id": "sess-2", "cwd": str(self.cwd_dir)}
        with patch.object(desk_hook, "ensure_server") as ensure_mock:
            result, stdout = _run_main(
                ["desk_hook.py", "UserPromptSubmit"], payload
            )

        self.assertEqual(result, 0)
        self.assertEqual(stdout, "")
        ensure_mock.assert_not_called()

        data = json.loads(self._session_file("sess-2").read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "작업 중")


class 메인_PostToolUse_PreCompact_Stop_이벤트(_DeskEnvTestCase):
    def test_이벤트별로_맞는_상태가_쓰인다(self):
        cases = [
            ("PostToolUse", "sess-3", "작업 중"),
            ("PreCompact", "sess-4", "작업 중"),
            ("Stop", "sess-5", "입력 대기"),
        ]
        for event, session_id, expected_status in cases:
            with self.subTest(event=event):
                payload = {"session_id": session_id, "cwd": str(self.cwd_dir)}
                result, stdout = _run_main(["desk_hook.py", event], payload)
                self.assertEqual(result, 0)
                self.assertEqual(stdout, "")
                data = json.loads(
                    self._session_file(session_id).read_text(encoding="utf-8")
                )
                self.assertEqual(data["status"], expected_status)


class 메인_Notification_승인대기_알림(_DeskEnvTestCase):
    def test_토픽파일이_있으면_send_ntfy를_레포_상태만으로_부른다(self):
        topic_path = self.tmp_path / "ntfy-topic"
        topic_path.write_text("my-topic\n", encoding="utf-8")
        payload = {
            "session_id": "sess-6",
            "cwd": str(self.cwd_dir),
            "notification_type": "permission_prompt",
        }
        with patch.object(
            desk_hook.paths, "ntfy_topic_path", lambda: topic_path
        ), patch.object(desk_hook, "send_ntfy") as send_mock:
            result, stdout = _run_main(["desk_hook.py", "Notification"], payload)

        self.assertEqual(result, 0)
        self.assertEqual(stdout, "")
        send_mock.assert_called_once_with("my-topic", self.cwd_dir.name, "승인 대기")

    def test_토픽파일이_없으면_send_ntfy를_안_부른다(self):
        missing_topic = self.tmp_path / "no-such-topic"
        payload = {
            "session_id": "sess-7",
            "cwd": str(self.cwd_dir),
            "notification_type": "permission_prompt",
        }
        with patch.object(
            desk_hook.paths, "ntfy_topic_path", lambda: missing_topic
        ), patch.object(desk_hook, "send_ntfy") as send_mock:
            result, stdout = _run_main(["desk_hook.py", "Notification"], payload)

        self.assertEqual(result, 0)
        self.assertEqual(stdout, "")
        send_mock.assert_not_called()

    def test_idle_prompt는_send_ntfy를_안_부른다(self):
        topic_path = self.tmp_path / "ntfy-topic-2"
        topic_path.write_text("topic\n", encoding="utf-8")
        payload = {
            "session_id": "sess-8",
            "cwd": str(self.cwd_dir),
            "notification_type": "idle_prompt",
        }
        with patch.object(
            desk_hook.paths, "ntfy_topic_path", lambda: topic_path
        ), patch.object(desk_hook, "send_ntfy") as send_mock:
            result, stdout = _run_main(["desk_hook.py", "Notification"], payload)

        self.assertEqual(result, 0)
        send_mock.assert_not_called()
        data = json.loads(self._session_file("sess-8").read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "입력 대기")


class 메인_SessionEnd_이벤트(_DeskEnvTestCase):
    def test_상태파일이_있으면_지운다(self):
        session_file = self._session_file("sess-9")
        session_file.parent.mkdir(parents=True)
        session_file.write_text("{}", encoding="utf-8")

        result, stdout = _run_main(
            ["desk_hook.py", "SessionEnd"], {"session_id": "sess-9"}
        )

        self.assertEqual(result, 0)
        self.assertEqual(stdout, "")
        self.assertFalse(session_file.exists())

    def test_상태파일이_없어도_예외없이_끝난다(self):
        result, stdout = _run_main(
            ["desk_hook.py", "SessionEnd"], {"session_id": "sess-does-not-exist"}
        )
        self.assertEqual(result, 0)
        self.assertEqual(stdout, "")


class 메인_실패_경로(_DeskEnvTestCase):
    def test_유효하지않은_JSON이면_0을_반환하고_stdout이_빈다(self):
        result, stdout = _run_main(["desk_hook.py", "UserPromptSubmit"], "not json")
        self.assertEqual(result, 0)
        self.assertEqual(stdout, "")

    def test_이벤트이름이_없으면_0을_반환하고_stdout이_빈다(self):
        result, stdout = _run_main(["desk_hook.py"], {})
        self.assertEqual(result, 0)
        self.assertEqual(stdout, "")

    def test_모르는_이벤트는_상태파일을_안_쓰고_0을_반환한다(self):
        payload = {"session_id": "sess-10", "cwd": str(self.cwd_dir)}
        result, stdout = _run_main(["desk_hook.py", "WeirdEvent"], payload)
        self.assertEqual(result, 0)
        self.assertEqual(stdout, "")
        self.assertFalse(self._session_file("sess-10").exists())


if __name__ == "__main__":
    unittest.main()
