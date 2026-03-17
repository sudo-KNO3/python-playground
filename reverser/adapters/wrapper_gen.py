"""AI-driven Python wrapper generator for non-Python programs."""

import re
from pathlib import Path
from typing import Any, Dict, Optional

from reverser.db import Database
from reverser.llm import LLM

WRAPPER_PROMPT = """\
You are writing a Python wrapper function that lets an AI agent interact with \
a {language} program.

Original function details:
  Name: {name}
  Qualified name: {qualified_name}
  Signature: {signature}
  Description: {description}
  Language: {language}

Program details:
  Program path: {program_path}
  Execution method: {exec_method}

Write a complete, standalone Python function named exactly `{name}` that \
wraps this functionality for an AI agent to call.

Execution method guide:
- subprocess_cli: The program is a command-line executable. Create any required
  input files in a temp directory, run the program via subprocess.run(),
  parse the output files or stdout, and return a meaningful result dict.
- com: Connect via win32com.client.Dispatch("{program_path}"), call the
  appropriate method(s), return the result.
- python_sdk: Import the Python SDK (e.g. flopy for MODFLOW, pyautocad for
  AutoCAD, pyhysys for HYSYS) and call the appropriate function. If the SDK
  is not installed, raise ImportError with install instructions.
- generic: Use subprocess or file I/O as appropriate for the program.

Requirements:
1. The function must have proper type-annotated parameters matching the original
2. Include a clear docstring explaining what the function does and its parameters
3. Handle errors gracefully with descriptive messages
4. Return a dict, string, float, or int — NOT None
5. Use only stdlib + these allowed packages: subprocess, pathlib, tempfile,
   json, os, re, shutil, win32com (Windows COM), flopy, httpx, requests

Return ONLY the Python function source code (starting with `def {name}(`).
No imports, no explanation, no markdown fences.
"""

IMPORTS_PROMPT = """\
Given this Python function body, what imports does it need?
Return ONLY the import statements (one per line), nothing else.

```python
{source}
```
"""


def _extract_imports_from_wrapper(source: str, llm: LLM) -> str:
    """Ask the LLM what imports the wrapper function needs."""
    try:
        response = llm.complete(IMPORTS_PROMPT.format(source=source))
        lines = [
            line.strip()
            for line in response.strip().splitlines()
            if line.strip().startswith(("import ", "from "))
        ]
        return "\n".join(lines)
    except Exception:
        return ""


def generate_wrapper(
    func_record: Dict[str, Any],
    program_path: str,
    exec_method: str,
    llm: LLM,
) -> Optional[str]:
    """Generate a Python wrapper function for a non-Python function.

    Args:
        func_record: Function record dict from the database.
        program_path: Path to the executable or COM ProgID.
        exec_method: One of 'subprocess_cli', 'com', 'python_sdk', 'generic'.
        llm: Configured LLM instance.

    Returns:
        Complete Python source code for the wrapper module, or None on failure.
    """
    prompt = WRAPPER_PROMPT.format(
        name=func_record.get("name", "unknown"),
        qualified_name=func_record.get("qualified_name", ""),
        signature=func_record.get("signature", "()"),
        description=func_record.get("ai_description") or func_record.get("docstring") or "No description available.",
        language=func_record.get("language", "Unknown"),
        program_path=program_path,
        exec_method=exec_method,
    )

    try:
        response = llm.complete(prompt)
    except Exception:
        return None

    # Clean up response
    text = response.strip()
    # Strip markdown fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else text

    if not text.startswith("def "):
        # Try to extract the function def from anywhere in the response
        match = re.search(r"^def \w+\(", text, re.MULTILINE)
        if match:
            text = text[match.start():]
        else:
            return None

    # Get the imports needed for the wrapper
    imports = _extract_imports_from_wrapper(text, llm)

    # Build the complete module source
    module_source = ""
    if imports:
        module_source += imports + "\n\n"
    module_source += text + "\n"

    return module_source


def save_wrapper(
    function_id: int,
    func_name: str,
    wrapper_source: str,
    wrappers_dir: Path,
) -> str:
    """Write a wrapper function to a .py file and return its path.

    Args:
        function_id: Database ID of the function.
        func_name: Python-safe function name.
        wrapper_source: Full Python module source code for the wrapper.
        wrappers_dir: Directory to save wrappers in.

    Returns:
        Absolute path to the saved wrapper file.
    """
    wrappers_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{function_id}_{func_name}.py"
    file_path = wrappers_dir / filename
    file_path.write_text(wrapper_source, encoding="utf-8")
    return str(file_path.resolve())


def generate_wrappers_for_actions(
    db: Database,
    llm: LLM,
    program_path: str,
    exec_method: str,
    wrappers_dir: Path,
    language_filter: Optional[str] = None,
) -> int:
    """Generate and save Python wrappers for all action functions.

    Generates wrappers for functions where:
    - is_action = 1
    - wrapper_path is not already set (or no existing file)
    - Language matches language_filter (if provided)

    Args:
        db: Open database instance.
        llm: Configured LLM instance.
        program_path: Executable path or COM ProgID.
        exec_method: Execution method ('subprocess_cli', 'com', 'python_sdk').
        wrappers_dir: Directory to save generated wrapper files.
        language_filter: If set, only generate wrappers for this language.

    Returns:
        Number of wrappers successfully generated.
    """
    actions = db.get_action_functions()
    count = 0

    for func in actions:
        # Skip if already has a valid wrapper
        existing = func.get("wrapper_path")
        if existing and Path(existing).exists():
            continue

        # Apply language filter
        if language_filter:
            # Look up the file language
            row = db.conn.execute(
                "SELECT language FROM files WHERE id = ?",
                (func["file_id"],),
            ).fetchone()
            if row and row["language"] != language_filter:
                continue

        # Get language for prompt
        lang_row = db.conn.execute(
            "SELECT language FROM files WHERE id = ?",
            (func["file_id"],),
        ).fetchone()
        language = lang_row["language"] if lang_row else "Unknown"

        func_with_lang = dict(func)
        func_with_lang["language"] = language

        wrapper_source = generate_wrapper(func_with_lang, program_path, exec_method, llm)
        if wrapper_source is None:
            continue

        wrapper_path = save_wrapper(
            func["id"], func["name"], wrapper_source, wrappers_dir
        )
        db.update_wrapper(func["id"], wrapper_path, "wrapper")
        count += 1

    return count
