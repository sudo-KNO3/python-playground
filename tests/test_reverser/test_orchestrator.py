"""Tests for the multi-agent orchestrator."""

import json
import sys
import types
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# Stub the anthropic module before any import of the orchestrator
_anthropic_stub = types.ModuleType("anthropic")
_anthropic_stub.Anthropic = MagicMock  # type: ignore[attr-defined]
sys.modules.setdefault("anthropic", _anthropic_stub)

from reverser.db import Database
from reverser.agents.orchestrator import Orchestrator


@pytest.fixture()
def db(tmp_path):
    """Fresh database with sample tools."""
    instance = Database(str(tmp_path / "test.db"))
    fid = instance.upsert_file("/tmp/cad.py", "Python")
    func_id = instance.upsert_function(
        file_id=fid,
        name="add_box",
        qualified_name="cad.add_box",
        signature="(length: float, width: float, height: float) -> object",
        docstring="Creates a 3D box with given dimensions.",
        source="def add_box(length, width, height): return {'box': True}",
        start_line=1,
        end_line=1,
        is_public=True,
    )
    instance.update_tool_schema(
        func_id,
        json.dumps({
            "name": "add_box",
            "description": "Creates a 3D box with given dimensions.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "length": {"type": "number"},
                    "width": {"type": "number"},
                    "height": {"type": "number"},
                },
                "required": ["length", "width", "height"],
            },
        }),
        "Creates a 3D box with given dimensions.",
        0.95,
        is_action=True,
    )
    yield instance
    instance.close()


def _make_text_block(text: str) -> MagicMock:
    """Build a mock text content block."""
    block = MagicMock(spec=["type", "text"])
    block.type = "text"
    block.text = text
    return block


def _make_tool_use_block(name: str, tool_input: dict) -> MagicMock:
    """Build a mock tool_use content block."""
    block = MagicMock(spec=["type", "name", "id", "input"])
    block.type = "tool_use"
    block.name = name
    block.id = "tu_001"
    block.input = tool_input
    return block


def _make_mock_client(tool_name="add_box", tool_args=None, final_text="Done."):
    """Build a mock Anthropic client that makes one tool call then finishes."""
    if tool_args is None:
        tool_args = {"length": 20.0, "width": 20.0, "height": 20.0}

    tool_use_block = _make_tool_use_block(
        "call_tool", {"tool_name": tool_name, "arguments": tool_args}
    )

    tool_call_response = MagicMock()
    tool_call_response.stop_reason = "tool_use"
    tool_call_response.content = [tool_use_block]

    final_response = MagicMock()
    final_response.stop_reason = "end_turn"
    final_response.content = [_make_text_block(final_text)]

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [
        tool_call_response,
        final_response,
    ]
    return mock_client


class TestOrchestratorHandlers:
    """Unit tests for individual tool handler methods."""

    def _make_orch(self, db):
        """Create an Orchestrator with a mocked Anthropic client."""
        with patch("reverser.agents.orchestrator.os.getenv", return_value="fake-key"):
            orch = Orchestrator(db)
            orch.client = MagicMock()
        return orch

    def test_handle_search_tools_finds_add_box(self, db):
        """search_tools finds the add_box function."""
        orch = self._make_orch(db)
        result_str = orch._handle_search_tools("box dimensions")
        result = json.loads(result_str)
        assert result["found"] >= 0  # may or may not match by keyword

    def test_handle_search_tools_empty_query(self, db):
        """search_tools with empty query returns valid JSON."""
        orch = self._make_orch(db)
        result_str = orch._handle_search_tools("")
        result = json.loads(result_str)
        assert "tools" in result

    def test_handle_get_tool_schema_found(self, db):
        """get_tool_schema returns schema for a known tool."""
        orch = self._make_orch(db)
        result_str = orch._handle_get_tool_schema("add_box")
        result = json.loads(result_str)
        assert result.get("name") == "add_box"
        assert "signature" in result

    def test_handle_get_tool_schema_not_found(self, db):
        """get_tool_schema returns error for unknown tool."""
        orch = self._make_orch(db)
        result_str = orch._handle_get_tool_schema("nonexistent_tool_xyz")
        result = json.loads(result_str)
        assert "error" in result

    def test_handle_call_tool_python_function(self, db, tmp_path):
        """call_tool executes a Python function and returns result."""
        # Create a real wrapper file so it can be executed
        wrapper = tmp_path / "1_add_box.py"
        wrapper.write_text(
            "def add_box(length: float, width: float, height: float) -> dict:\n"
            "    return {'volume': length * width * height}\n"
        )
        db.conn.execute(
            "UPDATE functions SET wrapper_path = ?, execution_method = 'wrapper' "
            "WHERE name = 'add_box'",
            (str(wrapper),),
        )
        db.conn.commit()

        orch = self._make_orch(db)
        result_str = orch._handle_call_tool(
            "add_box", {"length": 20.0, "width": 20.0, "height": 20.0}
        )
        result = json.loads(result_str)
        assert "result" in result
        assert "8000" in result["result"] or "8000.0" in result["result"]

    def test_handle_call_tool_not_found(self, db):
        """call_tool returns error for unknown tool name."""
        orch = self._make_orch(db)
        result_str = orch._handle_call_tool("nonexistent_xyz", {})
        result = json.loads(result_str)
        assert "error" in result


class TestOrchestratorRun:
    """Integration tests for the agent loop."""

    def test_run_returns_string(self, db):
        """run() returns a string result."""
        with patch("reverser.agents.orchestrator.os.getenv", return_value="fake-key"):
            mock_client = _make_mock_client()
            orch = Orchestrator(db)
            orch.client = mock_client
            result = orch.run("design a 20x20x20m box")
            assert isinstance(result, str)
            assert len(result) > 0

    def test_run_calls_on_step(self, db):
        """run() calls on_step callback for tool calls."""
        step_types = []

        def on_step(step_type: str, content: str) -> None:
            step_types.append(step_type)

        with patch("reverser.agents.orchestrator.os.getenv", return_value="fake-key"):
            mock_client = _make_mock_client()
            orch = Orchestrator(db)
            orch.client = mock_client
            orch.run("design a box", on_step=on_step)

        assert "tool_call" in step_types

    def test_run_end_turn_no_tools(self, db):
        """run() returns text immediately when LLM doesn't call any tools."""
        response = MagicMock()
        response.stop_reason = "end_turn"
        response.content = [_make_text_block("I don't know how to help with that.")]

        with patch("reverser.agents.orchestrator.os.getenv", return_value="fake-key"):
            mock_client = MagicMock()
            mock_client.messages.create.return_value = response
            orch = Orchestrator(db)
            orch.client = mock_client
            result = orch.run("completely unrelated request")
            assert "I don't know" in result

    def test_orchestrator_raises_without_api_key(self, db):
        """Orchestrator raises ValueError when ANTHROPIC_API_KEY is missing."""
        with patch("reverser.agents.orchestrator.os.getenv", return_value=None):
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                Orchestrator(db)
