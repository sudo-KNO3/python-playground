"""Tests for the database module."""

import os

import pytest

from reverser.db import Database


@pytest.fixture()
def db(tmp_path):
    """Create a fresh in-memory-backed database for each test."""
    db_file = str(tmp_path / "test.db")
    instance = Database(db_file)
    yield instance
    instance.close()


class TestDatabase:
    """Tests for Database CRUD operations."""

    def test_initialize_creates_tables(self, db):
        """Database initializes with all expected tables."""
        tables = db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        names = {r[0] for r in tables}
        assert {"files", "functions", "calls", "imports"}.issubset(names)

    def test_upsert_file_returns_id(self, db):
        """upsert_file returns an integer id."""
        fid = db.upsert_file("/tmp/foo.py", "Python")
        assert isinstance(fid, int)
        assert fid > 0

    def test_upsert_file_idempotent(self, db):
        """Upserting the same file twice returns the same id."""
        id1 = db.upsert_file("/tmp/foo.py", "Python")
        id2 = db.upsert_file("/tmp/foo.py", "Python")
        assert id1 == id2

    def test_upsert_function_returns_id(self, db):
        """upsert_function returns a positive integer."""
        fid = db.upsert_file("/tmp/foo.py", "Python")
        func_id = db.upsert_function(
            file_id=fid,
            name="add",
            qualified_name="foo.add",
            signature="(a: int, b: int) -> int",
            docstring="Adds two numbers.",
            source="def add(a, b): return a + b",
            start_line=1,
            end_line=1,
            is_public=True,
        )
        assert isinstance(func_id, int)
        assert func_id > 0

    def test_get_function_id(self, db):
        """get_function_id returns the correct id."""
        fid = db.upsert_file("/tmp/foo.py", "Python")
        func_id = db.upsert_function(
            file_id=fid,
            name="add",
            qualified_name="foo.add",
            signature="()",
            docstring=None,
            source=None,
            start_line=1,
            end_line=1,
            is_public=True,
        )
        assert db.get_function_id("foo.add") == func_id

    def test_get_function_id_missing(self, db):
        """Returns None for unknown qualified names."""
        assert db.get_function_id("does.not.exist") is None

    def test_insert_call(self, db):
        """insert_call stores a call edge."""
        fid = db.upsert_file("/tmp/foo.py", "Python")
        caller_id = db.upsert_function(
            fid, "caller", "foo.caller", "()", None, None, 1, 2, True
        )
        db.insert_call(caller_id, "callee_func", None)
        calls = db.get_function_calls(caller_id)
        assert "callee_func" in calls

    def test_search_tools_finds_by_name(self, db):
        """search_tools matches by function name."""
        fid = db.upsert_file("/tmp/foo.py", "Python")
        func_id = db.upsert_function(
            fid, "calculate", "foo.calculate", "(n: int)", None, None, 1, 2, True
        )
        db.update_tool_schema(func_id, '{"name": "calculate"}', "Calculates.", 0.9)
        results = db.search_tools("calculate")
        assert len(results) == 1
        assert results[0]["name"] == "calculate"

    def test_search_tools_no_results(self, db):
        """Returns empty list when nothing matches."""
        assert db.search_tools("nonexistent_xyz") == []

    def test_update_tool_schema(self, db):
        """update_tool_schema persists schema, description, and confidence."""
        fid = db.upsert_file("/tmp/foo.py", "Python")
        func_id = db.upsert_function(
            fid, "func", "foo.func", "()", None, None, 1, 1, True
        )
        db.update_tool_schema(func_id, '{"name":"func"}', "Does stuff.", 0.8)
        funcs = db.get_action_functions()
        assert any(f["id"] == func_id for f in funcs)
        func = next(f for f in funcs if f["id"] == func_id)
        assert func["ai_description"] == "Does stuff."
        assert abs(func["action_confidence"] - 0.8) < 0.001

    def test_get_stats(self, db):
        """get_stats returns counts for all tables."""
        stats = db.get_stats()
        assert set(stats.keys()) == {"files", "functions", "actions", "calls", "imports"}
        assert all(v == 0 for v in stats.values())

    def test_get_function_callers(self, db):
        """get_function_callers returns qualified names of callers."""
        fid = db.upsert_file("/tmp/foo.py", "Python")
        caller_id = db.upsert_function(
            fid, "caller", "foo.caller", "()", None, None, 1, 1, True
        )
        callee_id = db.upsert_function(
            fid, "callee", "foo.callee", "()", None, None, 2, 2, True
        )
        db.insert_call(caller_id, "callee", callee_id)
        callers = db.get_function_callers(callee_id)
        assert "foo.caller" in callers
