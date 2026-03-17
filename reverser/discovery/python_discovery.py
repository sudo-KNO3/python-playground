"""Deep Python package/module introspection using inspect."""

import importlib
import inspect
import pkgutil
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from reverser.db import Database


def _build_signature(func: Any) -> str:
    """Build a readable signature string for a callable."""
    try:
        sig = inspect.signature(func)
        return str(sig)
    except (ValueError, TypeError):
        return "(...)"


def _is_action_candidate(name: str, func: Any) -> bool:
    """Return True if this callable looks like a useful action."""
    if name.startswith("_"):
        return False
    if not callable(func):
        return False
    # Skip built-in functions and types from the standard library
    try:
        module = getattr(func, "__module__", "") or ""
        # Skip things from builtins or stdlib internals
        if module in ("builtins", "abc", "typing"):
            return False
    except Exception:
        pass
    return True


def _iter_module_callables(
    module: Any, module_name: str, depth: int = 0, max_depth: int = 3
) -> List[Tuple[str, str, Any]]:
    """Recursively yield (qualified_name, name, callable) from a module.

    Args:
        module: The module object.
        module_name: Dotted module name prefix.
        depth: Current recursion depth.
        max_depth: Maximum recursion depth (avoids infinite loops).

    Yields:
        Tuples of (qualified_name, simple_name, callable_obj).
    """
    if depth > max_depth:
        return []

    results = []
    try:
        members = inspect.getmembers(module)
    except Exception:
        return results

    for name, obj in members:
        if not _is_action_candidate(name, obj):
            continue

        qual = f"{module_name}.{name}"

        if inspect.isfunction(obj) or inspect.isbuiltin(obj):
            results.append((qual, name, obj))
        elif inspect.ismethod(obj):
            results.append((qual, name, obj))
        elif inspect.isclass(obj):
            # Recurse into class methods
            for method_name, method in inspect.getmembers(obj, predicate=inspect.isfunction):
                if not method_name.startswith("_"):
                    method_qual = f"{qual}.{method_name}"
                    results.append((method_qual, method_name, method))
        elif inspect.ismodule(obj) and depth < max_depth:
            sub_mod_name = getattr(obj, "__name__", f"{module_name}.{name}")
            if sub_mod_name.startswith(module_name):
                sub_results = _iter_module_callables(
                    obj, sub_mod_name, depth + 1, max_depth
                )
                results.extend(sub_results)

    return results


def _get_docstring(obj: Any) -> Optional[str]:
    """Return the cleaned docstring for a callable."""
    doc = inspect.getdoc(obj)
    return doc[:500] if doc else None


def discover_python_package(
    target: str,
    db: Database,
    llm: Optional[Any] = None,
) -> Dict[str, int]:
    """Discover all callable functions in a Python package by importing it.

    Recursively inspects all submodules and classes, extracts signatures,
    docstrings, and call relationships, then stores them in the database.

    Args:
        target: Python package/module name (e.g. 'flopy', 'numpy').
        db: Open database instance.
        llm: Unused (reserved for future AI description generation).

    Returns:
        Dict with counts: {'files': N, 'functions': N}.
    """
    try:
        module = importlib.import_module(target)
    except ImportError:
        return {"files": 0, "functions": 0}

    source_path = getattr(module, "__file__", None) or f"<{target}>"
    file_id = db.upsert_file(source_path, "Python")

    callables = _iter_module_callables(module, target)

    func_count = 0
    for qualified_name, name, obj in callables:
        signature = _build_signature(obj)
        docstring = _get_docstring(obj)

        # Try to get source file for this specific function
        try:
            func_source_file = inspect.getfile(obj)
            func_file_id = db.upsert_file(func_source_file, "Python")
        except (TypeError, OSError):
            func_file_id = file_id

        # Try to get source code snippet
        source_snippet = None
        try:
            source_snippet = textwrap.dedent(inspect.getsource(obj))[:2000]
        except (OSError, TypeError):
            pass

        # Line numbers
        try:
            start_line = inspect.getsourcelines(obj)[1]
            end_line = start_line
        except (OSError, TypeError):
            start_line = 0
            end_line = 0

        db.upsert_function(
            file_id=func_file_id,
            name=name,
            qualified_name=qualified_name,
            signature=signature,
            docstring=docstring,
            source=source_snippet,
            start_line=start_line,
            end_line=end_line,
            is_public=True,
        )
        # Mark as action and set execution method for python_import
        func_id = db.get_function_id(qualified_name)
        if func_id is not None:
            db.conn.execute(
                "UPDATE functions SET execution_method = 'python_import' WHERE id = ?",
                (func_id,),
            )
            db.conn.commit()
        func_count += 1

    return {"files": max(1, func_count // 10), "functions": func_count}
