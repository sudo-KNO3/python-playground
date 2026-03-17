"""Tests for the AI wrapper generator."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from reverser.adapters.wrapper_gen import (
    generate_wrapper,
    generate_wrappers_for_actions,
    save_wrapper,
)
from reverser.db import Database


def _make_func_record(name="run_model", lang="Fortran"):
    """Return a minimal function record dict."""
    return {
        "id": 1,
        "name": name,
        "qualified_name": f"aermod.{name}",
        "signature": "(emission_rate: float, receptor_x: float)",
        "docstring": "Run the dispersion model.",
        "ai_description": "Runs AERMOD air dispersion calculation.",
        "source": None,
        "language": lang,
        "file_id": 1,
        "wrapper_path": None,
    }


class TestGenerateWrapper:
    """Tests for generate_wrapper()."""

    def test_returns_python_source(self):
        """Returns a string starting with 'def'."""
        mock_llm = MagicMock()
        mock_llm.complete.return_value = (
            "def run_model(emission_rate: float, receptor_x: float) -> dict:\n"
            "    '''Run AERMOD.'''\n"
            "    return {'result': 0.0}\n"
        )
        result = generate_wrapper(
            _make_func_record(), "/path/to/aermod.exe", "subprocess_cli", mock_llm
        )
        assert result is not None
        assert "def run_model" in result

    def test_strips_markdown_fences(self):
        """Strips markdown code fences from LLM response."""
        mock_llm = MagicMock()
        mock_llm.complete.side_effect = [
            # First call: wrapper function (with fences)
            "```python\ndef run_model(x: float) -> dict:\n    return {}\n```",
            # Second call: imports
            "import subprocess",
        ]
        result = generate_wrapper(
            _make_func_record(), "/path/aermod.exe", "subprocess_cli", mock_llm
        )
        assert result is not None
        assert "```" not in result

    def test_returns_none_on_llm_error(self):
        """Returns None when the LLM raises an exception."""
        mock_llm = MagicMock()
        mock_llm.complete.side_effect = RuntimeError("LLM unavailable")
        result = generate_wrapper(
            _make_func_record(), "/path/aermod.exe", "subprocess_cli", mock_llm
        )
        assert result is None

    def test_returns_none_if_no_def(self):
        """Returns None when LLM response has no function definition."""
        mock_llm = MagicMock()
        mock_llm.complete.return_value = "Sorry, I cannot help with that."
        result = generate_wrapper(
            _make_func_record(), "/path/aermod.exe", "subprocess_cli", mock_llm
        )
        assert result is None

    def test_includes_imports(self):
        """Generated module source includes import statements."""
        mock_llm = MagicMock()
        mock_llm.complete.side_effect = [
            "def run_model(x: float) -> dict:\n    import subprocess\n    return {}\n",
            "import subprocess\nimport os",
        ]
        result = generate_wrapper(
            _make_func_record(), "/path/aermod.exe", "subprocess_cli", mock_llm
        )
        assert result is not None
        assert "import" in result


class TestSaveWrapper:
    """Tests for save_wrapper()."""

    def test_creates_file(self, tmp_path):
        """Creates a .py file in the wrappers directory."""
        source = "def myfunc(x: int) -> int:\n    return x\n"
        path = save_wrapper(42, "myfunc", source, tmp_path)
        assert Path(path).exists()
        assert Path(path).read_text() == source

    def test_filename_includes_id_and_name(self, tmp_path):
        """Filename contains function id and name."""
        save_wrapper(99, "calculate", "def calculate(): pass\n", tmp_path)
        files = list(tmp_path.glob("*.py"))
        assert any("99" in f.name and "calculate" in f.name for f in files)

    def test_creates_directory_if_missing(self, tmp_path):
        """Creates the wrappers directory if it does not exist."""
        new_dir = tmp_path / "nested" / "wrappers"
        assert not new_dir.exists()
        save_wrapper(1, "func", "def func(): pass\n", new_dir)
        assert new_dir.exists()


class TestGenerateWrappersForActions:
    """Tests for generate_wrappers_for_actions()."""

    def _setup_db_with_action(self, tmp_path, language="Fortran") -> Database:
        """Create a DB with one action function."""
        db = Database(str(tmp_path / "test.db"))
        fid = db.upsert_file("/tmp/model.f90", language)
        func_id = db.upsert_function(
            file_id=fid,
            name="run_model",
            qualified_name="aermod.run_model",
            signature="(rate: float)",
            docstring="Run the model.",
            source=None,
            start_line=1,
            end_line=10,
            is_public=True,
        )
        db.update_tool_schema(func_id, "{}", "Runs AERMOD.", 0.9, is_action=True)
        return db

    def test_generates_wrapper_and_updates_db(self, tmp_path):
        """Generates a wrapper file and updates the DB."""
        db = self._setup_db_with_action(tmp_path)
        wrappers_dir = tmp_path / "wrappers"

        mock_llm = MagicMock()
        mock_llm.complete.side_effect = [
            "def run_model(rate: float) -> dict:\n    return {'result': 0.0}\n",
            "",  # imports call
        ]

        count = generate_wrappers_for_actions(
            db, mock_llm, "/path/aermod.exe", "subprocess_cli", wrappers_dir
        )
        assert count == 1
        wrapper_files = list(wrappers_dir.glob("*.py"))
        assert len(wrapper_files) == 1
        db.close()

    def test_skips_existing_wrapper(self, tmp_path):
        """Skips functions that already have a valid wrapper file."""
        db = self._setup_db_with_action(tmp_path)
        # Create a fake existing wrapper
        existing = tmp_path / "existing.py"
        existing.write_text("def run_model(): pass\n")
        func_id = db.get_function_id("aermod.run_model")
        db.update_wrapper(func_id, str(existing), "wrapper")

        mock_llm = MagicMock()
        count = generate_wrappers_for_actions(
            db, mock_llm, "/path/aermod.exe", "subprocess_cli", tmp_path / "w"
        )
        assert count == 0
        mock_llm.complete.assert_not_called()
        db.close()

    def test_language_filter(self, tmp_path):
        """Respects language_filter — skips functions in other languages."""
        db = self._setup_db_with_action(tmp_path, language="Python")
        mock_llm = MagicMock()

        count = generate_wrappers_for_actions(
            db, mock_llm, "/path/prog", "subprocess_cli",
            tmp_path / "w", language_filter="Fortran"
        )
        assert count == 0
        mock_llm.complete.assert_not_called()
        db.close()
