"""Two-phase classifier: heuristics + AI to identify action functions."""

import json
from typing import Any, Dict, List, Optional

from reverser.db import Database
from reverser.llm import LLM

CLASSIFY_PROMPT = """\
Analyze the following Python function and decide whether it is a meaningful \
action that an AI agent could invoke to accomplish a task.

An "action function" should:
- Perform a meaningful, self-contained operation
- Accept inputs that an agent could reasonably provide
- Return a result or cause a side effect useful to an agent
- NOT be a helper, utility, or internal implementation detail

Function details:
Name: {name}
Qualified name: {qualified_name}
Signature: {signature}
Docstring: {docstring}

Source code:
```python
{source}
```

Called by: {callers}
Calls: {callees}

Respond with ONLY valid JSON (no markdown):
{{
  "is_action": true or false,
  "confidence": 0.0 to 1.0,
  "reason": "one sentence explanation"
}}
"""


def _passes_heuristics(func: Dict[str, Any]) -> bool:
    """Apply quick heuristic filters before calling the LLM.

    Args:
        func: Function record dict from the database.

    Returns:
        True if the function is a candidate for AI classification.
    """
    name: str = func.get("name", "")
    file_path: str = func.get("file_path", "") or ""
    signature: str = func.get("signature", "") or ""

    # Skip private/internal functions
    if name.startswith("_"):
        return False

    # Skip dunder methods
    if name.startswith("__") and name.endswith("__"):
        return False

    # Skip test functions
    if name.startswith("test_"):
        return False

    # Skip functions in test files
    if "test_" in file_path or "/tests/" in file_path:
        return False

    # Skip functions with no parameters (except self/cls)
    # A signature like "()" or "() -> None" has no useful inputs
    params_part = signature.split(")")[0].lstrip("(")
    params = [
        p.strip()
        for p in params_part.split(",")
        if p.strip() and p.strip() not in ("self", "cls")
    ]
    if not params:
        return False

    return True


def classify_functions(
    db: Database,
    llm: LLM,
    confidence_threshold: float = 0.6,
) -> int:
    """Classify all candidate functions in the database.

    Phase 1: Apply heuristic filters.
    Phase 2: For each candidate, ask the LLM to rate it.

    Args:
        db: Open database instance.
        llm: Configured LLM instance.
        confidence_threshold: Minimum confidence to mark as action (0–1).

    Returns:
        Number of functions marked as actions.
    """
    all_funcs = db.get_all_functions()
    candidates = [f for f in all_funcs if _passes_heuristics(f)]

    action_count = 0
    for func in candidates:
        function_id = func["id"]
        callers = db.get_function_callers(function_id)
        callees = db.get_function_calls(function_id)

        prompt = CLASSIFY_PROMPT.format(
            name=func.get("name", ""),
            qualified_name=func.get("qualified_name", ""),
            signature=func.get("signature", ""),
            docstring=func.get("docstring") or "None",
            source=func.get("source") or "(source not available)",
            callers=", ".join(callers) if callers else "none",
            callees=", ".join(callees) if callees else "none",
        )

        try:
            response = llm.complete(prompt)
            text = response.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
            data = json.loads(text)
        except Exception:
            # If the LLM call or JSON parsing fails, skip this function
            continue

        is_action: bool = bool(data.get("is_action", False))
        confidence: float = float(data.get("confidence", 0.0))
        reason: str = data.get("reason", "")

        if is_action and confidence >= confidence_threshold:
            db.update_tool_schema(
                function_id=function_id,
                schema_json="",
                description=reason,
                confidence=confidence,
                is_action=True,
            )
            action_count += 1
        else:
            db.update_tool_schema(
                function_id=function_id,
                schema_json="",
                description=reason,
                confidence=confidence,
                is_action=False,
            )

    return action_count
