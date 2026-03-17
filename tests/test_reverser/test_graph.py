"""Tests for the graph/network builder."""

import pytest

from reverser.graph import NetworkBuilder
from reverser.models import FileInfo, FunctionInfo


def _make_func(name: str, qualified_name: str, calls=None) -> FunctionInfo:
    """Helper: create a minimal FunctionInfo."""
    return FunctionInfo(
        name=name,
        qualified_name=qualified_name,
        signature="()",
        docstring=None,
        source=None,
        start_line=1,
        end_line=1,
        is_public=True,
        class_name=None,
        calls_made=calls or [],
    )


class TestNetworkBuilder:
    """Tests for NetworkBuilder."""

    def test_add_file_indexes_functions(self):
        """add_file makes functions available via get_qualified_name."""
        nb = NetworkBuilder()
        func = _make_func("add", "module.add")
        nb.add_file(FileInfo(path="/tmp/m.py", language="Python", functions=[func]))
        assert nb.get_qualified_name("add") == "module.add"

    def test_resolve_calls_returns_edges(self):
        """resolve_calls returns CallEdge for each function call."""
        nb = NetworkBuilder()
        caller = _make_func("a", "mod.a", calls=["b"])
        callee = _make_func("b", "mod.b")
        nb.add_file(
            FileInfo(
                path="/tmp/m.py",
                language="Python",
                functions=[caller, callee],
            )
        )
        edges = nb.resolve_calls()
        assert any(e.caller_qualified_name == "mod.a" for e in edges)
        callee_names = [e.callee_name for e in edges]
        assert "b" in callee_names

    def test_all_functions_unique(self):
        """all_functions does not return duplicates."""
        nb = NetworkBuilder()
        func = _make_func("add", "module.add")
        nb.add_file(FileInfo(path="/tmp/m.py", language="Python", functions=[func]))
        nb.add_file(FileInfo(path="/tmp/m.py", language="Python", functions=[func]))
        funcs = nb.all_functions
        qualified_names = [f.qualified_name for f in funcs]
        assert len(qualified_names) == len(set(qualified_names))

    def test_empty_builder(self):
        """Empty builder returns no edges and no functions."""
        nb = NetworkBuilder()
        assert nb.resolve_calls() == []
        assert nb.all_functions == []

    def test_get_qualified_name_unknown(self):
        """Returns None for unknown function names."""
        nb = NetworkBuilder()
        assert nb.get_qualified_name("nonexistent") is None
