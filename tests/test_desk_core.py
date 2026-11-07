"""desk/ 패키지(paths · atomic · validate · sort) 단위 테스트 — step 1 desk-core.

엣지 5축 커버리지:
- 빈 값·경계: 빈 dict · 빈 리스트 · 빈 문자열 · is_idle의 정확히 600초 경계
- 비정상 입력: dict가 아닌 입력(None · 문자열) · 잘못된 타입
- 실패 경로: 필수 필드 누락 · 타입 오류 → 예외를 던지지 않고 값(위반 필드 목록)으로 반환
- 상태 전이: is_idle/effective_status의 상태 전이, sort_sessions의 우선순위 재배치
- 동시성: 해당 없음 — desk/ 전부 순수 함수이거나 단일 원자적 파일 쓰기(os.replace)라
  동시 접근이 생기는 지점이 없다(ARCHITECTURE "입출력 대기 안 함")
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from desk import atomic, paths, sort, validate


class 환경변수가_없는_경우(unittest.TestCase):
    def setUp(self):
        self._saved = {}
        for key in ("DESK_RUN", "DESK_HOME"):
            self._saved[key] = os.environ.pop(key, None)

    def tearDown(self):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_sessions_dir_기본경로는_tmp_jtwjs_desk_sessions(self):
        self.assertEqual(paths.sessions_dir(), Path("/tmp/jtwjs-desk/sessions"))

    def test_inbox_dir_기본경로는_홈아래_jtwjs_desk_inbox_레포(self):
        self.assertEqual(
            paths.inbox_dir("jtwjs-desk"),
            Path.home() / ".jtwjs-desk" / "inbox" / "jtwjs-desk",
        )

    def test_server_meta_path_기본경로는_홈아래_jtwjs_desk_server_json(self):
        self.assertEqual(
            paths.server_meta_path(), Path.home() / ".jtwjs-desk" / "server.json"
        )

    def test_hook_error_log_path_기본경로는_홈아래_jtwjs_desk_hook_errors_log(self):
        self.assertEqual(
            paths.hook_error_log_path(),
            Path.home() / ".jtwjs-desk" / "hook-errors.log",
        )

    def test_ntfy_topic_path_는_항상_홈아래_config_jtwjs_desk(self):
        self.assertEqual(
            paths.ntfy_topic_path(),
            Path.home() / ".config" / "jtwjs-desk" / "ntfy-topic",
        )


class 환경변수가_설정된_경우(unittest.TestCase):
    def test_sessions_dir_desk_run이_있으면_그_아래_sessions를_쓴다(self):
        with patch.dict(os.environ, {"DESK_RUN": "/tmp/desk-test-run"}):
            self.assertEqual(paths.sessions_dir(), Path("/tmp/desk-test-run/sessions"))

    def test_inbox_dir_desk_home이_있으면_그_아래_inbox_레포를_쓴다(self):
        with patch.dict(os.environ, {"DESK_HOME": "/tmp/desk-test-home"}):
            self.assertEqual(
                paths.inbox_dir("repo-a"), Path("/tmp/desk-test-home/inbox/repo-a")
            )

    def test_ntfy_topic_path_는_desk_home을_바꿔도_변하지_않는다(self):
        with patch.dict(os.environ, {"DESK_HOME": "/tmp/desk-test-home"}):
            self.assertEqual(
                paths.ntfy_topic_path(),
                Path.home() / ".config" / "jtwjs-desk" / "ntfy-topic",
            )


class 원자적_쓰기(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def test_write_json_atomic_디렉터리가_없으면_만들고_파일을_쓴다(self):
        target = self.dir / "nested" / "a.json"
        atomic.write_json_atomic(target, {"x": 1})
        self.assertTrue(target.exists())
        self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"x": 1})

    def test_write_json_atomic_기존_파일이_있으면_교체한다(self):
        target = self.dir / "b.json"
        atomic.write_json_atomic(target, {"x": 1})
        atomic.write_json_atomic(target, {"x": 2})
        self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"x": 2})

    def test_write_json_atomic_빈_딕셔너리도_쓴다(self):
        target = self.dir / "c.json"
        atomic.write_json_atomic(target, {})
        self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {})

    def test_write_json_atomic_쓴_뒤_임시파일이_남지_않는다(self):
        target = self.dir / "d.json"
        atomic.write_json_atomic(target, {"x": 1})
        leftovers = [p for p in target.parent.iterdir() if p != target]
        self.assertEqual(leftovers, [])


def _valid_ask():
    return {
        "id": "q-1",
        "order": 1,
        "issue": None,
        "area": "desk",
        "question": "어떤 쪽?",
        "why": "결정 때문",
        "options": [{"key": "a", "label": "A안", "recommended": True}],
        "see": [],
        "aiDecided": [],
        "premiseOpen": False,
    }


class 질문_형식_검증_올바른_데이터인_경우(unittest.TestCase):
    def test_validate_ask_모든_필드가_올바르면_빈_리스트를_반환한다(self):
        self.assertEqual(validate.validate_ask(_valid_ask()), [])


class 질문_형식_검증_필드가_빠지거나_틀린_경우(unittest.TestCase):
    def test_validate_ask_id가_없으면_id를_포함한다(self):
        data = _valid_ask()
        del data["id"]
        self.assertIn("id", validate.validate_ask(data))

    def test_validate_ask_id가_빈문자열이면_id를_포함한다(self):
        data = _valid_ask()
        data["id"] = ""
        self.assertIn("id", validate.validate_ask(data))

    def test_validate_ask_order가_문자열이면_order를_포함한다(self):
        data = _valid_ask()
        data["order"] = "1"
        self.assertIn("order", validate.validate_ask(data))

    def test_validate_ask_options가_빈_리스트면_options를_포함한다(self):
        data = _valid_ask()
        data["options"] = []
        self.assertIn("options", validate.validate_ask(data))

    def test_validate_ask_options_항목에_key가_없으면_options를_포함한다(self):
        data = _valid_ask()
        data["options"] = [{"label": "A안", "recommended": True}]
        self.assertIn("options", validate.validate_ask(data))

    def test_validate_ask_premiseOpen이_불리언이_아니면_premiseOpen을_포함한다(self):
        data = _valid_ask()
        data["premiseOpen"] = "false"
        self.assertIn("premiseOpen", validate.validate_ask(data))

    def test_validate_ask_여러_필드가_틀리면_전부_포함한다(self):
        data = _valid_ask()
        del data["id"]
        data["order"] = "x"
        violations = validate.validate_ask(data)
        self.assertIn("id", violations)
        self.assertIn("order", violations)

    def test_validate_ask_빈_딕셔너리여도_예외를_던지지_않는다(self):
        try:
            validate.validate_ask({})
        except Exception as e:  # noqa: BLE001
            self.fail(f"예외가 발생했다: {e}")


class 질문_형식_검증_dict가_아닌_입력인_경우(unittest.TestCase):
    def test_validate_ask_None이면_모든_필수_필드를_반환한다(self):
        violations = validate.validate_ask(None)
        for field in (
            "id",
            "order",
            "issue",
            "area",
            "question",
            "why",
            "options",
            "see",
            "aiDecided",
            "premiseOpen",
        ):
            self.assertIn(field, violations)

    def test_validate_ask_문자열이어도_예외를_던지지_않고_리스트를_반환한다(self):
        try:
            result = validate.validate_ask("not a dict")
        except Exception as e:  # noqa: BLE001
            self.fail(f"예외가 발생했다: {e}")
        self.assertIsInstance(result, list)


def _valid_pick():
    return {
        "at": "2026-11-07T18:00:00+09:00",
        "choice": "a",
        "customText": None,
        "note": None,
        "noteKind": None,
        "aiRejected": [],
    }


class 선택_형식_검증_올바른_데이터인_경우(unittest.TestCase):
    def test_validate_pick_옵션을_고른_경우_빈_리스트를_반환한다(self):
        self.assertEqual(validate.validate_pick(_valid_pick()), [])

    def test_validate_pick_custom을_고르고_customText가_있으면_빈_리스트를_반환한다(self):
        data = {
            "at": "2026-11-07T18:00:00+09:00",
            "choice": "custom",
            "customText": "직접 쓴 선택",
            "note": "이유 메모",
            "noteKind": "reason",
            "aiRejected": ["a"],
        }
        self.assertEqual(validate.validate_pick(data), [])


class 선택_형식_검증_필드가_빠지거나_틀린_경우(unittest.TestCase):
    def test_validate_pick_at가_없으면_at를_포함한다(self):
        data = _valid_pick()
        del data["at"]
        self.assertIn("at", validate.validate_pick(data))

    def test_validate_pick_choice가_빈문자열이면_choice를_포함한다(self):
        data = _valid_pick()
        data["choice"] = ""
        self.assertIn("choice", validate.validate_pick(data))

    def test_validate_pick_choice가_custom인데_customText가_없으면_customText를_포함한다(self):
        data = _valid_pick()
        data["choice"] = "custom"
        data["customText"] = None
        self.assertIn("customText", validate.validate_pick(data))

    def test_validate_pick_note가_있는데_noteKind가_없으면_noteKind를_포함한다(self):
        data = _valid_pick()
        data["note"] = "이유"
        data["noteKind"] = None
        self.assertIn("noteKind", validate.validate_pick(data))

    def test_validate_pick_noteKind가_허용값이_아니면_noteKind를_포함한다(self):
        data = _valid_pick()
        data["note"] = "이유"
        data["noteKind"] = "etc"
        self.assertIn("noteKind", validate.validate_pick(data))

    def test_validate_pick_aiRejected가_리스트가_아니면_aiRejected를_포함한다(self):
        data = _valid_pick()
        data["aiRejected"] = "a"
        self.assertIn("aiRejected", validate.validate_pick(data))

    def test_validate_pick_빈_딕셔너리여도_예외를_던지지_않는다(self):
        try:
            validate.validate_pick({})
        except Exception as e:  # noqa: BLE001
            self.fail(f"예외가 발생했다: {e}")


class 선택_형식_검증_dict가_아닌_입력인_경우(unittest.TestCase):
    def test_validate_pick_None이면_필수_필드를_반환한다(self):
        violations = validate.validate_pick(None)
        self.assertIn("at", violations)
        self.assertIn("choice", violations)


class 유휴_판정_작업중_상태인_경우(unittest.TestCase):
    def test_is_idle_10분을_넘으면_참이다(self):
        now = 1000.0
        self.assertTrue(sort.is_idle("작업 중", now - 601, now))

    def test_is_idle_정확히_600초면_거짓이다(self):
        now = 1000.0
        self.assertFalse(sort.is_idle("작업 중", now - 600, now))

    def test_is_idle_10분_이내면_거짓이다(self):
        now = 1000.0
        self.assertFalse(sort.is_idle("작업 중", now - 599, now))


class 유휴_판정_작업중이_아닌_상태인_경우(unittest.TestCase):
    def test_is_idle_승인대기면_10분을_넘어도_거짓이다(self):
        now = 1000.0
        self.assertFalse(sort.is_idle("승인 대기", now - 601, now))

    def test_is_idle_완료면_10분을_넘어도_거짓이다(self):
        now = 1000.0
        self.assertFalse(sort.is_idle("완료", now - 601, now))


class 유효상태_계산(unittest.TestCase):
    def test_effective_status_유휴면_신호없음을_반환한다(self):
        now = 1000.0
        self.assertEqual(sort.effective_status("작업 중", now - 601, now), "신호 없음")

    def test_effective_status_유휴가_아니면_원래_상태를_반환한다(self):
        now = 1000.0
        self.assertEqual(sort.effective_status("작업 중", now - 10, now), "작업 중")

    def test_effective_status_작업중이_아닌_상태는_항상_그대로_반환한다(self):
        now = 1000.0
        self.assertEqual(sort.effective_status("승인 대기", now - 100000, now), "승인 대기")


class 정렬_순서_매핑(unittest.TestCase):
    def test_sort_key_승인대기는_0이다(self):
        self.assertEqual(sort.sort_key("승인 대기"), 0)

    def test_sort_key_신호없음은_1이다(self):
        self.assertEqual(sort.sort_key("신호 없음"), 1)

    def test_sort_key_입력대기는_2이다(self):
        self.assertEqual(sort.sort_key("입력 대기"), 2)

    def test_sort_key_작업중은_3이다(self):
        self.assertEqual(sort.sort_key("작업 중"), 3)

    def test_sort_key_완료는_4이다(self):
        self.assertEqual(sort.sort_key("완료"), 4)

    def test_sort_key_모르는_값은_5다(self):
        self.assertEqual(sort.sort_key("알수없음"), 5)


class 세션_정렬(unittest.TestCase):
    def test_sort_sessions_상태_우선순위대로_정렬한다(self):
        now = 1000.0
        sessions = [
            {"status": "작업 중", "lastAt": now - 1},
            {"status": "승인 대기", "lastAt": now - 1},
            {"status": "완료", "lastAt": now - 1},
            {"status": "입력 대기", "lastAt": now - 1},
        ]
        result = sort.sort_sessions(sessions, now)
        self.assertEqual(
            [s["effectiveStatus"] for s in result],
            ["승인 대기", "입력 대기", "작업 중", "완료"],
        )

    def test_sort_sessions_유휴_세션은_신호없음_자리로_올라온다(self):
        now = 1000.0
        sessions = [
            {"status": "작업 중", "lastAt": now - 1, "tag": "busy"},
            {"status": "작업 중", "lastAt": now - 601, "tag": "idle"},
            {"status": "입력 대기", "lastAt": now - 1, "tag": "waiting"},
        ]
        result = sort.sort_sessions(sessions, now)
        self.assertEqual([s["tag"] for s in result], ["idle", "waiting", "busy"])
        self.assertEqual(result[0]["effectiveStatus"], "신호 없음")

    def test_sort_sessions_빈_리스트면_빈_리스트를_반환한다(self):
        self.assertEqual(sort.sort_sessions([], 1000.0), [])

    def test_sort_sessions_원본_리스트와_세션_딕셔너리는_바뀌지_않는다(self):
        now = 1000.0
        sessions = [
            {"status": "완료", "lastAt": now},
            {"status": "승인 대기", "lastAt": now},
        ]
        original_order = [s["status"] for s in sessions]
        sort.sort_sessions(sessions, now)
        self.assertEqual([s["status"] for s in sessions], original_order)
        self.assertNotIn("effectiveStatus", sessions[0])

    def test_sort_sessions_동일_순위면_원래_순서를_유지한다(self):
        now = 1000.0
        sessions = [
            {"status": "작업 중", "lastAt": now, "tag": "first"},
            {"status": "작업 중", "lastAt": now, "tag": "second"},
        ]
        result = sort.sort_sessions(sessions, now)
        self.assertEqual([s["tag"] for s in result], ["first", "second"])


if __name__ == "__main__":
    unittest.main()
