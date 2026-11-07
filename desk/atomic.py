"""파일 쓰기의 유일한 방법 — 같은 디렉터리에 임시 파일을 쓰고 `os.replace`로 교체한다.

읽는 쪽이 반쯤 쓴 파일을 보지 않는다(ADR-001 "쓰기는 전부 임시 파일 + os.replace").
"""

import json
import os
import tempfile
from pathlib import Path


def write_json_atomic(path: Path, obj: dict) -> None:
    """obj를 path에 원자적으로 쓴다. path의 디렉터리가 없으면 만든다."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
