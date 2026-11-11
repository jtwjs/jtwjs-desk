"""desk/ · page/ 회귀 방지 검사 — step 10 guard-test.

ARCHITECTURE 「읽기 규약」: desk/ · page/는 다른 프로세스를 실행하지 않는다.
「경계 · 의존 방향」: desk/ · page/는 hooks · scripts를 import하지 않는다.
소스 문자열이 아니라 ast로 본다(docstring · 주석의 단어에 오탐하지 않게).
대상 파일은 glob으로 모아 새 모듈에도 자동 적용된다. hooks/는 대상이 아니다.
"""

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN_IMPORT_ROOTS = {"subprocess"}
FORBIDDEN_DEP_ROOTS = {"hooks", "scripts"}


def target_files():
    return sorted(list((ROOT / "desk").glob("*.py")) + list((ROOT / "page").glob("*.py")))


def _dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _imports(tree):
    """(줄, 최상위 모듈 이름) 목록."""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.append((node.lineno, alias.name.split(".")[0]))
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.append((node.lineno, node.module.split(".")[0]))
    return found


def violations(source, name="<src>"):
    """소스 하나의 위반 목록(문자열)."""
    tree = ast.parse(source, filename=name)
    out = []
    for lineno, root in _imports(tree):
        if root in FORBIDDEN_IMPORT_ROOTS:
            out.append(f"{name}:{lineno} subprocess import")
        if root in FORBIDDEN_DEP_ROOTS:
            out.append(f"{name}:{lineno} {root} import (의존 방향 위반)")
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            dotted = _dotted(node.func)
            last = dotted.rsplit(".", 1)[-1]
            if dotted in ("os.system", "os.popen") or last == "Popen":
                out.append(f"{name}:{node.lineno} {dotted}() 호출")
    return out


class 대상_파일이_있다(unittest.TestCase):
    def test_desk와_page의_py를_모은다(self):
        names = {p.name for p in target_files()}
        self.assertIn("config.py", names)
        self.assertIn("server.py", names)


class 검사기_자체(unittest.TestCase):
    def test_docstring_속_단어는_오탐하지_않는다(self):
        self.assertEqual(violations('"""subprocess os.system Popen"""\n# import subprocess\n'), [])

    def test_위반을_줄_번호와_함께_잡는다(self):
        src = "import os\nimport subprocess\nos.system('x')\nfrom subprocess import Popen\nPopen([])\nos.popen('x')\nfrom hooks import a\n"
        got = violations(src, "f.py")
        for expect in ("f.py:2", "f.py:3", "f.py:4", "f.py:5", "f.py:6", "f.py:7"):
            self.assertTrue(any(g.startswith(expect) for g in got), (expect, got))


class 소스에_금지된_것이_없다(unittest.TestCase):
    def test_subprocess_os_system_popen_hooks_scripts_없음(self):
        bad = []
        for path in target_files():
            bad += violations(path.read_text(encoding="utf-8"), str(path.relative_to(ROOT)))
        self.assertEqual(bad, [], "\n" + "\n".join(bad))


if __name__ == "__main__":
    unittest.main()
