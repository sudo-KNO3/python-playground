"""Generates MCP-compatible tool schemas for action functions."""

import json
import re
from typing import Any, Dict, Optional

from reverser.db import Database
from reverser.llm import LLM
from reverser.models import ToolSchema

SCHEMA_PROMPT = """\
Generate an MCP (Model Context Protocol) tool schema for the following \
Python function so that an AI agent can call it.

Function details:
Name: {name}
Qualified name: {qualified_name}
Signature: {signature}
Docstring: {docstring}
Description: {description}

Source code:
```python
{source}
```

Return ONLY valid JSON (no markdown, no explanation) with this exact structure:
{{
  "name": "snake_case_tool_name",
  "description": "Clear one or two sentence description of what this tool does.",
  "inputSchema": {{
    "type": "object",
    "properties": {{
      "param_name": {{
        "type": "string|integer|number|boolean|array|object",
        "description": "What this parameter is for."
      }}
    }},
    "required": ["param_name"]
  }}
}}

Rules:
- Tool name must be snake_case and start with a verb (e.g. calculate_factorial)
- Only include parameters that a caller would pass (exclude self, cls)
- Use Python type hints in the signature to infer JSON schema types
- If a parameter has a default value, omit it from "required"
"""


def _infer_json_type(python_type: str) -> str:
    """Map a Python type annotation string to a JSON Schema type."""
    type_map = {
        "int": "integer",
        "float": "number",
        "str": "string",
        "bool": "boolean",
        "list": "array",
        "dict": "object",
        "List": "array",
        "Dict": "object",
        "Any": "string",
        "None": "null",
    }
    for py_type, json_type in type_map.items():
        if py_type in python_type:
            return json_type
    return "string"


def generate_tool_schema(
    func: Dict[str, Any], llm: LLM
) -> Optional[ToolSchema]:
    """Generate an MCP tool schema for a function using the LLM.

    Args:
        func: Function record dict from the database.
        llm: Configured LLM instance.

    Returns:
        ToolSchema if successful, None on failure.
    """
    prompt = SCHEMA_PROMPT.format(
        name=func.get("name", ""),
        qualified_name=func.get("qualified_name", ""),
        signature=func.get("signature", ""),
        docstring=func.get("docstring") or "None",
        description=func.get("ai_description") or "None",
        source=func.get("source") or "(source not available)",
    )

    try:
        response = llm.complete(prompt)
        text = response.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
        data = json.loads(text)
    except Exception:
        return None

    return ToolSchema(
        name=data.get("name", func.get("name", "unknown_tool")),
        description=data.get("description", ""),
        input_schema=data.get("inputSchema", {"type": "object", "properties": {}}),
        function_id=func["id"],
    )


def generate_schemas_for_actions(db: Database, llm: LLM) -> int:
    """Generate and store MCP tool schemas for all action functions.

    Skips functions that already have a non-empty tool_schema.

    Args:
        db: Open database instance.
        llm: Configured LLM instance.

    Returns:
        Number of schemas successfully generated.
    """
    actions = db.get_action_functions()
    count = 0
    for func in actions:
        if func.get("tool_schema"):
            continue  # already generated

        schema = generate_tool_schema(func, llm)
        if schema is None:
            continue

        db.update_tool_schema(
            function_id=func["id"],
            schema_json=json.dumps(
                {
                    "name": schema.name,
                    "description": schema.description,
                    "inputSchema": schema.input_schema,
                }
            ),
            description=schema.description,
            confidence=func.get("action_confidence") or 0.8,
            is_action=True,
        )
        count += 1

    return count
