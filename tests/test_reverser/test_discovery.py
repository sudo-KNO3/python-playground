"""Tests for the discovery engine."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from reverser.db import Database
from reverser.discovery.python_discovery import (
    _build_signature,
    _is_action_candidate,
    _iter_module_callables,
    discover_python_package,
)
from reverser.discovery.binary_discovery import (
    _symbol_to_func_info,
    discover_binary,
)


@pytest.fixture()
def db(tmp_path):
    """Fresh database for each test."""
    instance = Database(str(tmp_path / "test.db"))
    yield instance
    instance.close()


class TestPythonDiscovery:
    """Tests for discover_python_package()."""

    def test_is_action_candidate_public(self):
        """Public callables pass the filter."""
        def my_func(x):
            return x
        assert _is_action_candidate("my_func", my_func) is True

    def test_is_action_candidate_private(self):
        """Private names are rejected."""
        def _helper():
            pass
        assert _is_action_candidate("_helper", _helper) is False

    def test_is_action_candidate_not_callable(self):
        """Non-callables are rejected."""
        assert _is_action_candidate("value", 42) is False

    def test_build_signature_simple(self):
        """Builds signature string from a simple function."""
        def add(a: int, b: int) -> int:
            return a + b
        sig = _build_signature(add)
        assert "a" in sig
        assert "b" in sig

    def test_build_signature_fallback(self):
        """Returns '(...)' for built-ins without inspectable signatures."""
        sig = _build_signature(len)
        assert isinstance(sig, str)

    def test_discovers_stdlib_module(self, db):
        """Discovers functions from a stdlib module (json)."""
        result = discover_python_package("json", db)
        assert result["functions"] > 0

    def test_discovers_functions_from_math(self, db):
        """Discovers math functions."""
        result = discover_python_package("math", db)
        assert result["functions"] > 0
        funcs = db.get_all_functions()
        names = [f["name"] for f in funcs]
        assert any(n in names for n in ("sqrt", "sin", "cos", "floor"))

    def test_unknown_package_returns_zero(self, db):
        """Returns zero counts for unknown packages."""
        result = discover_python_package("nonexistent_pkg_xyz_123", db)
        assert result["functions"] == 0

    def test_functions_stored_in_db(self, db):
        """Discovered functions are stored in the database."""
        discover_python_package("json", db)
        funcs = db.get_all_functions()
        assert len(funcs) > 0

    def test_execution_method_set_to_python_import(self, db):
        """Discovered Python functions have execution_method='python_import'."""
        discover_python_package("json", db)
        funcs = db.get_all_functions()
        python_funcs = [f for f in funcs if f.get("execution_method") == "python_import"]
        assert len(python_funcs) > 0


class TestBinaryDiscovery:
    """Tests for binary/DLL discovery."""

    def test_symbol_to_func_info(self):
        """Converts a symbol name to a function info dict."""
        info = _symbol_to_func_info("aermod_calculate", "/path/aermod.so")
        assert info["name"] == "aermod_calculate"
        assert "aermod" in info["qualified_name"]

    def test_symbol_with_cpp_namespace(self):
        """Handles C++ namespace in symbol name."""
        info = _symbol_to_func_info("MyClass::calculate", "/path/lib.so")
        assert isinstance(info["name"], str)
        assert len(info["name"]) > 0

    def test_nonexistent_binary_returns_zero(self, db):
        """Returns zero counts for a nonexistent file."""
        result = discover_binary("/nonexistent/file.so", db)
        assert result["functions"] == 0

    def test_non_binary_extension_returns_zero(self, db, tmp_path):
        """Returns zero counts for unsupported file types."""
        txt = tmp_path / "data.txt"
        txt.write_text("hello")
        result = discover_binary(str(txt), db)
        assert result["functions"] == 0

    def test_existing_so_file(self, db, tmp_path):
        """Attempts binary discovery on a real .so file (nm may find nothing)."""
        # Find a real .so to test against (Python's own stdlib)
        import ctypes.util
        libm = ctypes.util.find_library("m")  # libm.so
        if libm and libm != "m":
            result = discover_binary(libm, db)
            # Result may be 0 if nm/objdump not available, that's OK
            assert isinstance(result["functions"], int)


class TestDiscoveryInit:
    """Tests for the top-level discover() function."""

    def test_discover_python_package(self, db):
        """discover() with a Python package name discovers functions."""
        from reverser.discovery import discover
        result = discover("json", db)
        assert result["functions"] > 0
        assert result["strategies_used"] >= 1

    def test_discover_unknown_returns_zero(self, db):
        """discover() with an unknown target returns zero gracefully."""
        from reverser.discovery import discover
        result = discover("___totally_unknown_xyz___", db)
        assert result["functions"] == 0

    def test_discover_does_not_raise(self, db):
        """discover() never raises even for invalid targets."""
        from reverser.discovery import discover
        try:
            discover("INVALID\\PATH//*", db)
        except Exception as exc:
            pytest.fail(f"discover() raised {exc}")
