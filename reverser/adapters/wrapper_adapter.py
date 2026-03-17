"""Adapter that executes AI-generated Python wrapper functions."""

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from reverser.adapters import BaseAdapter


class WrapperAdapter(BaseAdapter):
    """Imports and calls an AI-generated Python wrapper file.

    The `wrapper_path` column on the function record is the path to a
    generated .py file containing the wrapper function.
    """

    def execute(
        self, func_record: Dict[str, Any], arguments: Dict[str, Any]
    ) -> str:
        """Load and call the wrapper function.

        Args:
            func_record: Function dict. `wrapper_path` is the path to the
                         wrapper .py file. `name` is the function to call.
            arguments: Keyword arguments to pass to the wrapper function.

        Returns:
            String representation of the result, or error message.
        """
        wrapper_path = func_record.get("wrapper_path") or ""
        if not wrapper_path:
            return (
                "Error: no wrapper file configured for this tool. "
                "Run 'reverser generate-wrappers' to generate wrappers."
            )

        path = Path(wrapper_path)
        if not path.exists():
            return f"Error: wrapper file not found at '{wrapper_path}'."

        func_name = func_record.get("name", "")
        callable_obj = self._load_wrapper_function(path, func_name)
        if callable_obj is None:
            return (
                f"Error: function '{func_name}' not found in "
                f"wrapper file '{wrapper_path}'."
            )

        try:
            result = callable_obj(**arguments)
        except Exception as exc:
            return f"Error executing wrapper '{func_name}': {type(exc).__name__}: {exc}"

        if isinstance(result, (dict, list)):
            return json.dumps(result, indent=2, default=str)
        return str(result)

    def _load_wrapper_function(
        self, path: Path, func_name: str
    ) -> Optional[Any]:
        """Dynamically load a function from a wrapper .py file."""
        module_name = f"_reverser_wrapper_{path.stem}_{abs(hash(str(path)))}"
        if module_name not in sys.modules:
            spec = importlib.util.spec_from_file_location(module_name, str(path))
            if spec is None or spec.loader is None:
                return None
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            try:
                spec.loader.exec_module(module)  # type: ignore[union-attr]
            except Exception:
                del sys.modules[module_name]
                return None
        else:
            module = sys.modules[module_name]

        obj = getattr(module, func_name, None)
        return obj if callable(obj) else None
