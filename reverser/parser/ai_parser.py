"""AI-driven parser for non-Python source files."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from reverser.llm import LLM
from reverser.models import FileInfo, FunctionInfo, ImportEdge

logger = logging.getLogger(__name__)

PARSE_PROMPT = """\
You are analyzing a {language} source file. Extract all function and method \
definitions from the code below.

Return ONLY valid JSON (no markdown, no explanation) with this structure:
{{
  "functions": [
    {{
      "name": "function_name",
      "qualified_name": "module_or_class.function_name",
      "signature": "(param1: type, param2: type) -> return_type",
      "docstring": "description if present, else null",
      "start_line": 1,
      "end_line": 10,
      "calls": ["other_func", "helper"],
      "is_public": true
    }}
  ],
  "imports": [
    {{
      "module": "module_name",
      "alias": null,
      "imported_names": []
    }}
  ]
}}

Source file path: {path}

```{language}
{source}
```
"""


def _parse_function(raw: Dict[str, Any], file_path: str) -> FunctionInfo:
    """Convert a raw dict from LLM JSON into a FunctionInfo."""
    return FunctionInfo(
        name=raw.get("name", "unknown"),
        qualified_name=raw.get("qualified_name", raw.get("name", "unknown")),
        signature=raw.get("signature", "()"),
        docstring=raw.get("docstring"),
        source=None,
        start_line=int(raw.get("start_line", 0)),
        end_line=int(raw.get("end_line", 0)),
        is_public=bool(raw.get("is_public", True)),
        class_name=None,
        calls_made=raw.get("calls", []),
    )


def _parse_import(raw: Dict[str, Any], file_path: str) -> ImportEdge:
    """Convert a raw dict from LLM JSON into an ImportEdge."""
    return ImportEdge(
        file_path=file_path,
        module=raw.get("module", ""),
        alias=raw.get("alias"),
        imported_names=raw.get("imported_names", []),
    )


def parse_with_ai(path: Path, language: str, llm: LLM) -> FileInfo:
    """Parse a non-Python source file using an LLM.

    Sends the file content to the LLM and asks it to extract function
    definitions and import statements as structured JSON.

    Args:
        path: Path to the source file.
        language: Human-readable language name (e.g. 'Go', 'Ruby').
        llm: Configured LLM instance to use for parsing.

    Returns:
        FileInfo with extracted functions and imports (best-effort).
    """
    source = path.read_text(encoding="utf-8", errors="replace")
    # Truncate very large files to avoid token limits
    max_chars = 12_000
    if len(source) > max_chars:
        source = source[:max_chars] + "\n... [truncated]"

    prompt = PARSE_PROMPT.format(
        language=language,
        path=str(path),
        source=source,
    )

    try:
        response = llm.complete(prompt)
    except Exception:
        logger.warning("LLM call failed while parsing %s", path, exc_info=True)
        return FileInfo(path=str(path), language=language)

    # Strip any markdown fences the LLM might add
    text = response.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last fence lines
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else text

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning(
            "Failed to parse LLM response for %s: %s", path, response[:200]
        )
        return FileInfo(path=str(path), language=language)

    functions = [
        _parse_function(f, str(path))
        for f in data.get("functions", [])
    ]
    imports = [
        _parse_import(i, str(path))
        for i in data.get("imports", [])
    ]

    return FileInfo(
        path=str(path),
        language=language,
        functions=functions,
        imports=imports,
    )
