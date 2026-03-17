"""COM/ActiveX type library discovery (Windows only)."""

import json
import sys
from typing import Any, Dict, List, Optional

from reverser.db import Database

_VIRTUAL_PATH = "<COM:{progid}>"


def _is_windows() -> bool:
    return sys.platform == "win32"


def _get_type_info(dispatch_obj: Any) -> List[Dict[str, Any]]:
    """Extract method information from a COM dispatch object.

    Uses the _oleobj_ type info to enumerate all methods and properties.

    Args:
        dispatch_obj: A win32com Dispatch object.

    Returns:
        List of dicts with keys: name, description, params.
    """
    methods = []
    try:
        type_info = dispatch_obj._oleobj_.GetTypeInfo()
        type_attr = type_info.GetTypeAttr()
        for i in range(type_attr.cFuncs):
            func_desc = type_info.GetFuncDesc(i)
            names = type_info.GetNames(func_desc.memid)
            if not names:
                continue
            name = names[0]
            # Skip hidden / restricted members
            if func_desc.wFuncFlags & 0x41:  # FUNCFLAG_FRESTRICTED | FUNCFLAG_FHIDDEN
                continue
            doc = ""
            try:
                doc = type_info.GetDocumentation(func_desc.memid)[1] or ""
            except Exception:
                pass
            params = names[1:]  # parameter names follow method name
            methods.append({"name": name, "description": doc, "params": params})
    except Exception:
        pass
    return methods


def _scan_com_registry() -> List[str]:
    """Enumerate COM-registered ProgIDs from the Windows registry."""
    progids = []
    try:
        import winreg  # type: ignore[import]

        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "") as root:
            i = 0
            while True:
                try:
                    subkey = winreg.EnumKey(root, i)
                    i += 1
                    # ProgIDs contain a dot (e.g. AutoCAD.Application)
                    if "." in subkey and not subkey.startswith("."):
                        progids.append(subkey)
                except OSError:
                    break
    except Exception:
        pass
    return progids


def discover_com(
    target: str,
    db: Database,
    llm: Optional[Any] = None,
) -> Dict[str, int]:
    """Discover functions from a COM/ActiveX application.

    If target == 'system', scans ALL COM-registered programs.
    Otherwise, target should be a COM ProgID (e.g. 'AutoCAD.Application').

    Args:
        target: COM ProgID or 'system' for full registry scan.
        db: Open database instance.
        llm: Unused (reserved for future description generation).

    Returns:
        Dict with counts: {'files': N, 'functions': N}.
    """
    if not _is_windows():
        return {"files": 0, "functions": 0}

    try:
        import win32com.client  # type: ignore[import]
    except ImportError:
        return {"files": 0, "functions": 0}

    progids = _scan_com_registry() if target == "system" else [target]

    total_funcs = 0
    total_files = 0

    for progid in progids:
        try:
            dispatch = win32com.client.Dispatch(progid)
        except Exception:
            continue

        methods = _get_type_info(dispatch)
        if not methods:
            continue

        virtual_path = _VIRTUAL_PATH.format(progid=progid)
        file_id = db.upsert_file(virtual_path, "COM")
        total_files += 1

        for method in methods:
            name = method["name"]
            qualified_name = f"{progid}.{name}"
            params = method.get("params", [])
            signature = f"({', '.join(params)})"
            docstring = method.get("description") or None

            func_id = db.upsert_function(
                file_id=file_id,
                name=name,
                qualified_name=qualified_name,
                signature=signature,
                docstring=docstring,
                source=None,
                start_line=0,
                end_line=0,
                is_public=True,
            )
            # Set execution method and wrapper_path (the COM ProgID)
            db.conn.execute(
                """
                UPDATE functions
                SET execution_method = 'com', wrapper_path = ?
                WHERE id = ?
                """,
                (progid, func_id),
            )
            db.conn.commit()
            total_funcs += 1

    return {"files": total_files, "functions": total_funcs}
