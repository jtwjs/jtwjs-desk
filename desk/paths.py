"""desk 상태 · 판정 파일의 경로를 계산한다.

환경변수는 모듈 레벨이 아니라 호출 시점에 `os.environ.get`으로 읽는다 —
테스트가 `DESK_RUN` · `DESK_HOME`을 임시 폴더로 바꿔 끼울 수 있게 한다
(ARCHITECTURE "테스트 전략").
"""

import os
from pathlib import Path


def desk_run_dir() -> Path:
    """세션 상태 디렉터리 루트. `DESK_RUN`이 없으면 `/tmp/jtwjs-desk`(ADR-001)."""
    return Path(os.environ.get("DESK_RUN", "/tmp/jtwjs-desk"))


def desk_home_dir() -> Path:
    """판정 · 서버 메타 디렉터리 루트. `DESK_HOME`이 없으면 `~/.jtwjs-desk`(ADR-001)."""
    return Path(os.environ.get("DESK_HOME", str(Path.home() / ".jtwjs-desk")))


def sessions_dir() -> Path:
    """세션 상태 파일들이 쌓이는 디렉터리: `<DESK_RUN>/sessions`."""
    return desk_run_dir() / "sessions"


def inbox_dir(repo: str) -> Path:
    """판정 inbox 디렉터리: `<DESK_HOME>/inbox/<repo>`. repo는 git 최상위 폴더 이름."""
    return desk_home_dir() / "inbox" / repo


def server_meta_path() -> Path:
    """페이지 서버 메타(포트 · pid · 버전 · 토큰) 파일: `<DESK_HOME>/server.json`."""
    return desk_home_dir() / "server.json"


def hook_error_log_path() -> Path:
    """훅 예외를 한 줄씩 남기는 로그 파일: `<DESK_HOME>/hook-errors.log`."""
    return desk_home_dir() / "hook-errors.log"


def ntfy_topic_path() -> Path:
    """ntfy 토픽 파일. `DESK_HOME`과 무관하게 항상 이 경로(ADR-005)."""
    return Path.home() / ".config" / "jtwjs-desk" / "ntfy-topic"
