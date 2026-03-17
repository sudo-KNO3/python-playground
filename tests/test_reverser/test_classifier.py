"""Tests for the classifier module."""

import json
from unittest.mock import MagicMock

import pytest

from reverser.classifier import _passes_heuristics, classify_functions
from reverser.db import Database


def _make_func_record(
    name="calculate",
    qualified_name="mod.calculate",
    signature="(n: int) -> int",
    file_path="/tmp/mod.py",
) -> dict:
    """Helper: build a minimal function record dict."""
    return {
        "id": 1,
        "name": name,
        "qualified_name": qualified_name,
        "signature": signature,
        "docstring": "Does something.",
        "source": f"def {name}(n: int) -> int:\n    return n",
        "file_path": file_path,
        "is_public": 1,
    }


class TestPassesHeuristics:
    """Tests for the heuristic filter."""

    def test_public_with_params_passes(self):
        """A public function with parameters passes."""
        assert _passes_heuristics(_make_func_record()) is True

    def test_private_function_fails(self):
        """Private functions (name starts with _) are filtered out."""
        rec = _make_func_record(name="_helper", qualified_name="mod._helper")
        assert _passes_heuristics(rec) is False

    def test_dunder_fails(self):
        """Dunder methods are filtered out."""
        rec = _make_func_record(name="__init__")
        assert _passes_heuristics(rec) is False

    def test_test_function_fails(self):
        """Functions named test_* are filtered out."""
        rec = _make_func_record(name="test_foo", qualified_name="mod.test_foo")
        assert _passes_heuristics(rec) is False

    def test_function_in_test_file_fails(self):
        """Functions in test files are filtered out."""
        rec = _make_func_record(file_path="/tests/test_mod.py")
        assert _passes_heuristics(rec) is False

    def test_no_params_fails(self):
        """Functions with no parameters (except self/cls) are filtered."""
        rec = _make_func_record(signature="()")
        assert _passes_heuristics(rec) is False

    def test_only_self_fails(self):
        """Functions with only self parameter are filtered."""
        rec = _make_func_record(signature="(self)")
        assert _passes_heuristics(rec) is False


class TestClassifyFunctions:
    """Tests for classify_functions() with mocked LLM."""

    def _setup_db(self, tmp_path, func_record) -> Database:
        """Create a DB with one function."""
        db = Database(str(tmp_path / "test.db"))
        fid = db.upsert_file(func_record.get("file_path", "/tmp/mod.py"), "Python")
        func_id = db.upsert_function(
            file_id=fid,
            name=func_record["name"],
            qualified_name=func_record["qualified_name"],
            signature=func_record.get("signature", "()"),
            docstring=func_record.get("docstring"),
            source=func_record.get("source"),
            start_line=1,
            end_line=2,
            is_public=True,
        )
        return db

    def test_classify_marks_action(self, tmp_path):
        """classify_functions marks functions as actions when LLM agrees."""
        rec = _make_func_record()
        db = self._setup_db(tmp_path, rec)

        mock_llm = MagicMock()
        mock_llm.complete.return_value = json.dumps(
            {"is_action": True, "confidence": 0.9, "reason": "It does something."}
        )

        count = classify_functions(db, mock_llm)
        assert count == 1

        actions = db.get_action_functions()
        assert len(actions) == 1
        db.close()

    def test_classify_skips_low_confidence(self, tmp_path):
        """Functions with confidence below threshold are not marked as actions."""
        rec = _make_func_record()
        db = self._setup_db(tmp_path, rec)

        mock_llm = MagicMock()
        mock_llm.complete.return_value = json.dumps(
            {"is_action": True, "confidence": 0.3, "reason": "Borderline."}
        )

        count = classify_functions(db, mock_llm, confidence_threshold=0.6)
        assert count == 0
        db.close()

    def test_classify_handles_llm_error(self, tmp_path):
        """classify_functions skips functions when the LLM raises an error."""
        rec = _make_func_record()
        db = self._setup_db(tmp_path, rec)

        mock_llm = MagicMock()
        mock_llm.complete.side_effect = RuntimeError("LLM unavailable")

        count = classify_functions(db, mock_llm)
        assert count == 0
        db.close()
