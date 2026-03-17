"""Execution adapters for calling functions in different program types."""

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseAdapter(ABC):
    """Abstract base class for program execution adapters."""

    @abstractmethod
    def execute(self, func_record: Dict[str, Any], arguments: Dict[str, Any]) -> str:
        """Execute a function and return its output as a string.

        Args:
            func_record: Function dict from the database.
            arguments: Keyword arguments to pass to the function.

        Returns:
            String representation of the function output.
        """
        ...


def get_adapter(execution_method: str) -> "BaseAdapter":
    """Return the appropriate adapter for the given execution method.

    Args:
        execution_method: One of 'subprocess', 'com', 'wrapper', 'python_import'.

    Returns:
        A BaseAdapter instance.

    Raises:
        ValueError: If the execution method is unknown.
    """
    if execution_method == "subprocess":
        from reverser.adapters.subprocess_adapter import SubprocessAdapter

        return SubprocessAdapter()
    elif execution_method == "com":
        from reverser.adapters.com_adapter import COMAdapter

        return COMAdapter()
    elif execution_method in ("wrapper", "python_import"):
        from reverser.adapters.wrapper_adapter import WrapperAdapter

        return WrapperAdapter()
    else:
        raise ValueError(f"Unknown execution method: '{execution_method}'")
