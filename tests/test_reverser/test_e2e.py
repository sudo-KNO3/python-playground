"""End-to-end integration tests for the full reverser pipeline.

Exercises: scan → index → classify → schema generation → search → adapter execution.
All LLM calls are mocked so the test suite runs without an API key.
"""

import json
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from reverser.db import Database
from reverser.scanner import scan_directory, detect_language
from reverser.parser import parse_file
from reverser.graph import NetworkBuilder
from reverser.classifier import classify_functions
from reverser.schema_gen import generate_schemas_for_actions
from reverser.adapters.subprocess_adapter import SubprocessAdapter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(tmp_path):
    """Fresh database backed by a temp file."""
    instance = Database(str(tmp_path / "test.db"))
    yield instance
    instance.close()


@pytest.fixture()
def sample_project(tmp_path) -> Path:
    """Create a minimal Python project for scanning."""
    src = tmp_path / "myproject"
    src.mkdir()
    (src / "__init__.py").write_text("")
    (src / "calculator.py").write_text(
        textwrap.dedent("""\
            \"\"\"Simple calculator module.\"\"\"

            def add(a: float, b: float) -> float:
                \"\"\"Add two numbers and return the result.\"\"\"
                return a + b

            def multiply(a: float, b: float) -> float:
                \"\"\"Multiply two numbers and return the result.\"\"\"
                return a * b

            def _internal_helper(x):
                \"\"\"Private helper — should not be classified as an action.\"\"\"
                return x * 2
        """)
    )
    return src


@pytest.fixture()
def mock_llm():
    """LLM mock that returns valid classification and schema JSON."""
    llm = MagicMock()

    def _complete(prompt: str) -> str:
        if "is_action" in prompt or "action function" in prompt.lower():
            return json.dumps({
                "is_action": True,
                "confidence": 0.9,
                "reason": "Performs a meaningful arithmetic operation.",
            })
        # schema generation prompt
        return json.dumps({
            "name": "add_numbers",
            "description": "Add two numbers and return the result.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "First operand."},
                    "b": {"type": "number", "description": "Second operand."},
                },
                "required": ["a", "b"],
            },
        })

    llm.complete.side_effect = _complete
    return llm


# ---------------------------------------------------------------------------
# Pipeline tests
# ---------------------------------------------------------------------------


class TestScanAndIndex:
    """Scanning a Python project populates the database correctly."""

    def test_scan_finds_python_files(self, sample_project):
        files = list(scan_directory(sample_project))
        assert any("calculator.py" in str(f) for f in files)

    def test_parse_extracts_functions(self, sample_project):
        calc = sample_project / "calculator.py"
        file_info = parse_file(calc, "Python", llm=None)
        names = [f.name for f in file_info.functions]
        assert "add" in names
        assert "multiply" in names

    def test_index_stores_functions_in_db(self, db, sample_project):
        calc = sample_project / "calculator.py"
        file_info = parse_file(calc, "Python", llm=None)
        file_id = db.upsert_file(file_info.path, file_info.language)
        for func in file_info.functions:
            db.upsert_function(
                file_id=file_id,
                name=func.name,
                qualified_name=func.qualified_name,
                signature=func.signature,
                docstring=func.docstring,
                source=func.source,
                start_line=func.start_line,
                end_line=func.end_line,
                is_public=func.is_public,
            )
        stats = db.get_stats()
        assert stats["functions"] >= 3  # add, multiply, _internal_helper


class TestClassification:
    """Classification correctly identifies action functions."""

    def _seed_db(self, db, sample_project):
        """Helper: scan and index the sample project into db."""
        calc = sample_project / "calculator.py"
        file_info = parse_file(calc, "Python", llm=None)
        file_id = db.upsert_file(file_info.path, file_info.language)
        for func in file_info.functions:
            db.upsert_function(
                file_id=file_id,
                name=func.name,
                qualified_name=func.qualified_name,
                signature=func.signature,
                docstring=func.docstring,
                source=func.source,
                start_line=func.start_line,
                end_line=func.end_line,
                is_public=func.is_public,
            )

    def test_classify_marks_public_functions_as_actions(self, db, sample_project, mock_llm):
        self._seed_db(db, sample_project)
        count = classify_functions(db, mock_llm, confidence_threshold=0.5)
        assert count >= 1

    def test_classify_skips_private_functions(self, db, sample_project, mock_llm):
        self._seed_db(db, sample_project)
        classify_functions(db, mock_llm)
        actions = db.get_action_functions()
        action_names = [f["name"] for f in actions]
        assert "_internal_helper" not in action_names

    def test_classify_bad_llm_response_skips_gracefully(self, db, sample_project):
        self._seed_db(db, sample_project)
        bad_llm = MagicMock()
        bad_llm.complete.return_value = "not valid json {{{"
        # Should not raise — just skips functions with bad responses
        count = classify_functions(db, bad_llm)
        assert count == 0

    def test_classify_llm_exception_skips_gracefully(self, db, sample_project):
        self._seed_db(db, sample_project)
        error_llm = MagicMock()
        error_llm.complete.side_effect = RuntimeError("API error")
        count = classify_functions(db, error_llm)
        assert count == 0


class TestSchemaGeneration:
    """Schema generation produces valid MCP tool schemas."""

    def _seed_and_classify(self, db, sample_project, mock_llm):
        calc = sample_project / "calculator.py"
        file_info = parse_file(calc, "Python", llm=None)
        file_id = db.upsert_file(file_info.path, file_info.language)
        for func in file_info.functions:
            db.upsert_function(
                file_id=file_id,
                name=func.name,
                qualified_name=func.qualified_name,
                signature=func.signature,
                docstring=func.docstring,
                source=func.source,
                start_line=func.start_line,
                end_line=func.end_line,
                is_public=func.is_public,
            )
        classify_functions(db, mock_llm, confidence_threshold=0.5)

    def test_generate_schemas_for_actions(self, db, sample_project, mock_llm):
        self._seed_and_classify(db, sample_project, mock_llm)
        count = generate_schemas_for_actions(db, mock_llm)
        assert count >= 1

    def test_generated_schema_is_valid_json(self, db, sample_project, mock_llm):
        self._seed_and_classify(db, sample_project, mock_llm)
        generate_schemas_for_actions(db, mock_llm)
        actions = db.get_action_functions()
        for func in actions:
            if func.get("tool_schema"):
                schema = json.loads(func["tool_schema"])
                assert "name" in schema
                assert "inputSchema" in schema


class TestSearch:
    """Search returns relevant results after indexing."""

    def test_search_finds_function_by_keyword(self, db, sample_project, mock_llm):
        calc = sample_project / "calculator.py"
        file_info = parse_file(calc, "Python", llm=None)
        file_id = db.upsert_file(file_info.path, file_info.language)
        for func in file_info.functions:
            db.upsert_function(
                file_id=file_id,
                name=func.name,
                qualified_name=func.qualified_name,
                signature=func.signature,
                docstring=func.docstring,
                source=func.source,
                start_line=func.start_line,
                end_line=func.end_line,
                is_public=func.is_public,
            )
        classify_functions(db, mock_llm, confidence_threshold=0.5)
        results = db.search_tools("add")
        assert any("add" in r["name"] for r in results)


class TestSubprocessAdapterSecurity:
    """Subprocess adapter rejects malicious argument keys."""

    def test_safe_key_passes_through(self):
        adapter = SubprocessAdapter()
        func_record = {"wrapper_path": "/bin/echo", "name": "echo"}
        result = adapter.execute(func_record, {"message": "hello"})
        # Should not raise and should contain some output or echo result
        assert isinstance(result, str)

    def test_unsafe_key_is_skipped(self):
        adapter = SubprocessAdapter()
        func_record = {"wrapper_path": "/bin/echo", "name": "echo"}
        # Key with shell metacharacters should be silently dropped
        result = adapter.execute(func_record, {"safe": "ok", "bad;key": "malicious"})
        assert isinstance(result, str)
        assert "bad;key" not in result

    def test_missing_wrapper_path_returns_error(self):
        adapter = SubprocessAdapter()
        result = adapter.execute({"wrapper_path": "", "name": "noop"}, {})
        assert "Error" in result
