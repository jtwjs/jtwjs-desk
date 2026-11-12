"""desk 설정 읽기(ADR-008). 설정 파일 외에는 열지 않고 쓰지 않는다.

`~/.config/jtwjs-desk/config.json`이 있으면 그것만 읽고, 없을 때만
`conductor.json`(`repos` · `seat`→`vault`)으로 폴백한다. 예외는 밖으로 던지지 않는다.
"""

import json
from pathlib import Path

from desk import paths


def _default_daily_dir() -> Path:
    return Path.home() / ".claude" / "daily"


def _path_list(value):
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return [Path(v).expanduser() for v in value]
    return None


def _path(value):
    return Path(value).expanduser() if isinstance(value, str) and value else None


def _read_json(path: Path):
    """(데이터, 오류 한 줄). 파일이 없으면 (None, None)."""
    if not path.is_file():
        return None, None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"{path.name} 읽기 실패: {type(exc).__name__}"
    if not isinstance(data, dict):
        return None, f"{path.name} 최상위가 객체가 아님"
    return data, None


def load_config() -> dict:
    result = {
        "source": "none",
        "repos": [],
        "vault": None,
        "criteria_file": None,
        "daily_dir": _default_daily_dir(),
        "evidence_globs": [],
        "routine_questions": None,
        "routine_answers": None,
        "trends_items": None,
        "trends_reads": None,
        "trends_marks": None,
        "error": None,
    }
    try:
        cfg_path = paths.config_path()
        if cfg_path.is_file():
            result["source"] = "config"
            data, err = _read_json(cfg_path)
            keys = {"repos": "repos", "vault": "vault"}
        else:
            cond_path = paths.conductor_path()
            if not cond_path.is_file():
                return result
            result["source"] = "conductor"
            data, err = _read_json(cond_path)
            keys = {"repos": "repos", "seat": "vault"}
        errors = [err] if err else []
        for src_key, dst_key in keys.items():
            if data is None or src_key not in data:
                continue
            if dst_key == "repos":
                val = _path_list(data[src_key])
                if val is None:
                    errors.append("repos 타입 오류")
                else:
                    result["repos"] = val
            else:
                val = _path(data[src_key])
                if val is None:
                    errors.append(f"{src_key} 타입 오류")
                else:
                    result["vault"] = val
        if result["source"] == "config" and data is not None:
            if "criteria_file" in data:
                val = _path(data["criteria_file"])
                if val is None:
                    errors.append("criteria_file 타입 오류")
                else:
                    result["criteria_file"] = val
            if "daily_dir" in data:
                val = _path(data["daily_dir"])
                if val is None:
                    errors.append("daily_dir 타입 오류")
                else:
                    result["daily_dir"] = val
            if "evidence_globs" in data:
                g = data["evidence_globs"]
                if isinstance(g, list) and all(isinstance(x, str) for x in g):
                    result["evidence_globs"] = list(g)
                else:
                    errors.append("evidence_globs 타입 오류")
            for key in (
                "routine_questions",
                "routine_answers",
                "trends_items",
                "trends_reads",
                "trends_marks",
            ):
                if key in data:
                    if not isinstance(data[key], str):
                        errors.append(f"{key} 타입 오류")
                    else:  # 빈 문자열은 설정 없음(None)
                        result[key] = _path(data[key])
        if errors:
            result["error"] = "; ".join(errors)
    except Exception as exc:  # 서버가 요청마다 부른다 — 밖으로 던지지 않는다
        result["error"] = f"설정 읽기 실패: {type(exc).__name__}"
    return result


def unregistered(live_repo_names: list, repos: list) -> list:
    """repos에 없는 살아 있는 세션의 레포 이름. 중복 제거, 입력 순서 유지."""
    known = {Path(r).name for r in repos}
    out = []
    for name in live_repo_names:
        if name not in known and name not in out:
            out.append(name)
    return out
