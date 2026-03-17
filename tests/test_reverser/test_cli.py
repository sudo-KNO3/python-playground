"""Tests for the CLI commands using CliRunner."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from reverser.cli import cli


@pytest.fixture()
def runner():
    """Return a Click test runner."""
    return CliRunner()


class TestScanCommand:
    """Tests for the `scan` command."""

    def test_scan_no_classify(self, runner, tmp_path):
        """scan --no-classify runs without calling the LLM."""
        project = tmp_path / "myproject"
        project.mkdir()
        (project / "mod.py").write_text("def foo(x: int) -> int:\n    return x\n")
        db_path = str(tmp_path / "tools.db")

        result = runner.invoke(
            cli,
            ["scan", str(project), "--db", db_path, "--no-classify", "--no-color"],
        )
        assert result.exit_code == 0, result.output
        assert Path(db_path).exists()

    def test_scan_creates_db(self, runner, tmp_path):
        """scan creates the database file."""
        project = tmp_path / "proj"
        project.mkdir()
        (project / "a.py").write_text("def bar(n: int): return n")
        db_path = str(tmp_path / "out.db")

        runner.invoke(
            cli,
            ["scan", str(project), "--db", db_path, "--no-classify", "--no-color"],
        )
        assert Path(db_path).exists()

    def test_scan_missing_project(self, runner, tmp_path):
        """scan with non-existent path exits with error."""
        result = runner.invoke(
            cli,
            ["scan", "/nonexistent/path", "--db", str(tmp_path / "t.db")],
        )
        assert result.exit_code != 0


class TestSearchCommand:
    """Tests for the `search` command."""

    def test_search_missing_db(self, runner, tmp_path):
        """search with missing DB shows error."""
        result = runner.invoke(
            cli, ["search", "foo", "--db", str(tmp_path / "missing.db")]
        )
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_search_returns_results(self, runner, tmp_path):
        """search finds indexed action functions."""
        from reverser.db import Database

        db_path = str(tmp_path / "tools.db")
        db = Database(db_path)
        fid = db.upsert_file("/tmp/foo.py", "Python")
        func_id = db.upsert_function(
            fid, "calculate", "foo.calculate", "(n: int)", None, None, 1, 1, True
        )
        db.update_tool_schema(
            func_id, '{"name": "calculate"}', "Calculates things.", 0.9
        )
        db.close()

        result = runner.invoke(
            cli,
            ["search", "calculate", "--db", db_path, "--no-color"],
        )
        assert result.exit_code == 0
        assert "calculate" in result.output

    def test_search_no_results(self, runner, tmp_path):
        """search shows message when nothing is found."""
        from reverser.db import Database

        db_path = str(tmp_path / "tools.db")
        Database(db_path).close()

        result = runner.invoke(
            cli,
            ["search", "zzznomatch", "--db", db_path, "--no-color"],
        )
        assert result.exit_code == 0
        assert "No tools found" in result.output


class TestNetworkCommand:
    """Tests for the `network` command."""

    def test_network_missing_db(self, runner, tmp_path):
        """network with missing DB shows error."""
        result = runner.invoke(
            cli,
            [
                "network",
                "--db",
                str(tmp_path / "missing.db"),
                "--function",
                "mod.func",
            ],
        )
        assert result.exit_code != 0

    def test_network_unknown_function(self, runner, tmp_path):
        """network shows error for unknown function name."""
        from reverser.db import Database

        db_path = str(tmp_path / "t.db")
        Database(db_path).close()

        result = runner.invoke(
            cli,
            [
                "network",
                "--db",
                db_path,
                "--function",
                "does.not.exist",
                "--no-color",
            ],
        )
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_network_shows_function(self, runner, tmp_path):
        """network displays info for a known function."""
        from reverser.db import Database

        db_path = str(tmp_path / "t.db")
        db = Database(db_path)
        fid = db.upsert_file("/tmp/foo.py", "Python")
        db.upsert_function(
            fid, "myfunc", "foo.myfunc", "(x: int)", None, None, 1, 1, True
        )
        db.close()

        result = runner.invoke(
            cli,
            [
                "network",
                "--db",
                db_path,
                "--function",
                "foo.myfunc",
                "--no-color",
            ],
        )
        assert result.exit_code == 0
        assert "myfunc" in result.output
