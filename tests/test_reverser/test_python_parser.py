"""Tests for the Python AST parser."""

from pathlib import Path

import pytest

from reverser.parser.python_parser import parse_python_file


SIMPLE_SOURCE = '''\
"""A simple test module."""


def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


def _private(x):
    return x * 2


class Calculator:
    """A calculator class."""

    def multiply(self, a: int, b: int) -> int:
        """Multiply two numbers."""
        return a * b

    def __init__(self):
        pass
'''


class TestParsePythonFile:
    """Tests for parse_python_file()."""

    def _write_and_parse(self, tmp_path, source):
        """Write source to a temp file and parse it."""
        f = tmp_path / "test_mod.py"
        f.write_text(source)
        return parse_python_file(f)

    def test_language_is_python(self, tmp_path):
        """Returns FileInfo with language='Python'."""
        info = self._write_and_parse(tmp_path, SIMPLE_SOURCE)
        assert info.language == "Python"

    def test_finds_top_level_function(self, tmp_path):
        """Finds the top-level 'add' function."""
        info = self._write_and_parse(tmp_path, SIMPLE_SOURCE)
        names = [f.name for f in info.functions]
        assert "add" in names

    def test_finds_private_function(self, tmp_path):
        """Finds private functions (is_public=False)."""
        info = self._write_and_parse(tmp_path, SIMPLE_SOURCE)
        private = next(f for f in info.functions if f.name == "_private")
        assert private.is_public is False

    def test_finds_method(self, tmp_path):
        """Finds class methods with correct class_name."""
        info = self._write_and_parse(tmp_path, SIMPLE_SOURCE)
        multiply = next(f for f in info.functions if f.name == "multiply")
        assert multiply.class_name == "Calculator"

    def test_qualified_name_for_method(self, tmp_path):
        """Method qualified_name includes class name."""
        info = self._write_and_parse(tmp_path, SIMPLE_SOURCE)
        multiply = next(f for f in info.functions if f.name == "multiply")
        assert "Calculator.multiply" in multiply.qualified_name

    def test_docstring_extraction(self, tmp_path):
        """Extracts docstring from function."""
        info = self._write_and_parse(tmp_path, SIMPLE_SOURCE)
        add = next(f for f in info.functions if f.name == "add")
        assert add.docstring == "Add two numbers."

    def test_signature_extraction(self, tmp_path):
        """Extracts parameter signature."""
        info = self._write_and_parse(tmp_path, SIMPLE_SOURCE)
        add = next(f for f in info.functions if f.name == "add")
        assert "a" in add.signature
        assert "b" in add.signature

    def test_imports_extracted(self, tmp_path):
        """Extracts import statements."""
        source = "import os\nfrom pathlib import Path\n\ndef f(): pass\n"
        info = self._write_and_parse(tmp_path, source)
        modules = [imp.module for imp in info.imports]
        assert "os" in modules
        assert "pathlib" in modules

    def test_syntax_error_returns_empty(self, tmp_path):
        """Returns empty FileInfo on SyntaxError."""
        info = self._write_and_parse(tmp_path, "def broken(:\n")
        assert info.functions == []

    def test_call_extraction(self, tmp_path):
        """Records function calls made within a function."""
        source = "def caller():\n    helper()\n    other_func()\n"
        info = self._write_and_parse(tmp_path, source)
        caller = next(f for f in info.functions if f.name == "caller")
        assert "helper" in caller.calls_made or "other_func" in caller.calls_made
