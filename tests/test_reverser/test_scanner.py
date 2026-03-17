"""Tests for the scanner module."""

from pathlib import Path

import pytest

from reverser.scanner import LANGUAGE_MAP, detect_language, scan_directory


class TestDetectLanguage:
    """Tests for detect_language()."""

    def test_python_extension(self):
        """Detects Python from .py extension."""
        assert detect_language(Path("foo.py")) == "Python"

    def test_javascript_extension(self):
        """Detects JavaScript from .js extension."""
        assert detect_language(Path("foo.js")) == "JavaScript"

    def test_typescript_extension(self):
        """Detects TypeScript from .ts extension."""
        assert detect_language(Path("foo.ts")) == "TypeScript"

    def test_go_extension(self):
        """Detects Go from .go extension."""
        assert detect_language(Path("foo.go")) == "Go"

    def test_unknown_extension(self):
        """Returns 'Unknown' for unrecognized extensions."""
        assert detect_language(Path("foo.xyz")) == "Unknown"

    def test_no_extension(self):
        """Returns 'Unknown' for files without an extension."""
        assert detect_language(Path("Makefile")) == "Unknown"

    def test_case_insensitive(self):
        """Extension detection is case-insensitive."""
        assert detect_language(Path("foo.PY")) == "Python"


class TestScanDirectory:
    """Tests for scan_directory()."""

    def test_finds_python_files(self, tmp_path):
        """Yields .py files from a directory."""
        (tmp_path / "main.py").write_text("x = 1")
        (tmp_path / "helper.py").write_text("y = 2")
        results = list(scan_directory(tmp_path))
        names = {p.name for p in results}
        assert "main.py" in names
        assert "helper.py" in names

    def test_skips_unknown_extensions(self, tmp_path):
        """Does not yield files with unknown extensions."""
        (tmp_path / "data.txt").write_text("hello")
        (tmp_path / "code.py").write_text("x = 1")
        results = list(scan_directory(tmp_path))
        names = {p.name for p in results}
        assert "data.txt" not in names
        assert "code.py" in names

    def test_skips_pycache(self, tmp_path):
        """Skips __pycache__ directories."""
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "module.cpython-38.pyc").write_bytes(b"")
        (tmp_path / "real.py").write_text("x = 1")
        results = list(scan_directory(tmp_path))
        paths = [str(p) for p in results]
        assert not any("__pycache__" in p for p in paths)

    def test_skips_hidden_files(self, tmp_path):
        """Skips files starting with a dot."""
        (tmp_path / ".hidden.py").write_text("x = 1")
        (tmp_path / "visible.py").write_text("y = 2")
        results = list(scan_directory(tmp_path))
        names = {p.name for p in results}
        assert ".hidden.py" not in names
        assert "visible.py" in names

    def test_recursive_scan(self, tmp_path):
        """Recursively scans subdirectories."""
        sub = tmp_path / "subpkg"
        sub.mkdir()
        (sub / "module.py").write_text("z = 3")
        results = list(scan_directory(tmp_path))
        names = {p.name for p in results}
        assert "module.py" in names
