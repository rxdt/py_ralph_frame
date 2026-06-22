"""Tests for AST-based structural style checks."""

from __future__ import annotations

import ast

import pytest

# preferences.py is optional — humans may delete it; skip its tests when it is gone.
preferences = pytest.importorskip("harness.preferences")
class_violations = preferences.class_violations_must_be_pydantic
preferences_violations = preferences.preferences_violations
star_violations = preferences.star_violations
underscore_violations = preferences.underscore_violations


def parse(source: str) -> ast.Module:
    """Parse source text into an AST module."""
    return ast.parse(source)


def test_underscore_names_flagged() -> None:
    """Function, argument, and assigned names starting with underscore are flagged."""
    source = "def _hidden(_arg):\n    _value = 1\n    return _value\n"
    problems = underscore_violations("m.py", parse(source))
    assert len(problems) == 3
    assert any("'_hidden'" in problem for problem in problems)
    assert any("'_arg'" in problem for problem in problems)
    assert any("'_value'" in problem for problem in problems)


def test_bare_underscore_flagged() -> None:
    """The throwaway underscore variable is also banned."""
    source = "for _ in [1]:\n    pass\n"
    assert len(underscore_violations("m.py", parse(source))) == 1


def test_dunder_names_exempt() -> None:
    """Dunder names like __all__ and __init__ are not flagged."""
    source = "__all__ = []\n\n\nclass Box(dict):\n    def __init__(self):\n        super().__init__()\n"
    assert underscore_violations("m.py", parse(source)) == []


def test_star_unpacking_flagged() -> None:
    """Call splats, double-star splats, and starred assignment are flagged."""
    source = "f(*items)\ng(**options)\nfirst, *rest = [1, 2]\n"
    problems = star_violations("m.py", parse(source))
    assert len(problems) == 3


def test_star_signatures_flagged() -> None:
    """*args and **kwargs parameters are flagged."""
    source = "def f(*args):\n    return args\n\n\ndef g(**kwargs):\n    return kwargs\n"
    problems = star_violations("m.py", parse(source))
    assert len(problems) == 2
    assert all("signature" in problem for problem in problems)


def test_pointless_class_flagged() -> None:
    """A class with no base, decorator, and one method is flagged."""
    source = "class Holder:\n    def get(self):\n        return 1\n"
    problems = class_violations("m.py", parse(source))
    assert len(problems) == 1
    assert "'Holder'" in problems[0]


def test_useful_classes_pass() -> None:
    """Dataclasses, subclasses, keyword-based classes, and stateful classes pass."""
    source = (
        "from dataclasses import dataclass\n\n\n"
        "@dataclass\n"
        "class Point:\n    x: int\n\n\n"
        "class CustomError(Exception):\n    pass\n\n\n"
        "class Meta(metaclass=type):\n    pass\n\n\n"
        "class Machine:\n"
        "    def start(self):\n        return 1\n\n"
        "    def stop(self):\n        return 0\n"
    )
    assert class_violations("m.py", parse(source)) == []


def test_function_count_limit() -> None:
    """More top-level functions than the limit is flagged."""
    source = "".join(f"def f{i}():\n    return {i}\n\n\n" for i in range(6))
    problems = preferences_violations("m.py", source, 5)
    assert problems == ["m.py: 6 top-level functions exceeds limit 5; split the module"]


def test_function_count_skipped_when_unlimited() -> None:
    """A zero limit disables only the function count check."""
    source = "def f():\n    return 1\n\n\ndef g():\n    return 2\n"
    assert preferences_violations("m.py", source, 0) == []


def test_syntax_error_reported() -> None:
    """Unparseable files are reported instead of crashing the gate."""
    problems = preferences_violations("m.py", "def broken(:\n", 5)
    assert len(problems) == 1
    assert "could not parse" in problems[0]


def test_clean_file_passes() -> None:
    """A compliant module produces no violations."""
    source = (
        '"""Module."""\n\n'
        "VALUE = 1\n\n\n"
        "def double(number: int) -> int:\n"
        '    """Double the number."""\n'
        "    return number * 2\n"
    )
    assert preferences_violations("m.py", source, 5) == []
