"""COM/ActiveX adapter for Windows automation (HYSYS, AutoCAD, etc.)."""

import json
from typing import Any, Dict, Optional

from reverser.adapters import BaseAdapter


class COMAdapter(BaseAdapter):
    """Controls a Windows COM/ActiveX application via win32com.

    The `wrapper_path` column on the function record is interpreted as the
    COM ProgID (e.g. 'HYSYS.Application', 'AutoCAD.Application').

    This adapter is a no-op on non-Windows systems: it returns an
    informational message instead of raising an exception.
    """

    def execute(
        self, func_record: Dict[str, Any], arguments: Dict[str, Any]
    ) -> str:
        """Call a COM method and return the result.

        Args:
            func_record: Function dict. `wrapper_path` is the COM ProgID.
                         `name` is the method name to call on the COM object.
            arguments: Keyword arguments for the COM method.

        Returns:
            String representation of the COM call result, or error message.
        """
        try:
            import win32com.client  # type: ignore[import]
        except ImportError:
            return (
                "COM execution requires the pywin32 package on Windows. "
                "Run: pip install pywin32"
            )

        progid = func_record.get("wrapper_path") or ""
        if not progid:
            return (
                "Error: no COM ProgID configured for this tool. "
                "Set wrapper_path to the COM ProgID (e.g. 'HYSYS.Application')."
            )

        method_name = func_record.get("name", "")
        if not method_name:
            return "Error: no method name found in function record."

        try:
            app = win32com.client.Dispatch(progid)  # type: ignore[attr-defined]
        except Exception as exc:
            return f"Error connecting to COM object '{progid}': {exc}"

        # Navigate dotted method path (e.g. "Flowsheet.Operations.Add")
        obj = app
        parts = method_name.split(".")
        for part in parts[:-1]:
            obj = getattr(obj, part, None)
            if obj is None:
                return f"Error: attribute '{part}' not found on COM object."

        method = getattr(obj, parts[-1], None)
        if method is None:
            return f"Error: method '{parts[-1]}' not found on COM object."

        try:
            result = method(**arguments)
            return json.dumps(result, default=str) if result is not None else "(no return value)"
        except Exception as exc:
            return f"Error calling COM method '{method_name}': {exc}"
