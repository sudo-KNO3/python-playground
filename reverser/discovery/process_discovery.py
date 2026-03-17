"""Running process introspection: discover loaded modules in live processes."""

import importlib
import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from reverser.db import Database


def _find_process_by_name(name: str) -> Optional[int]:
    """Find the PID of a running process by name.

    Returns the first matching PID, or None if not found.
    """
    try:
        import psutil  # type: ignore[import]

        name_lower = name.lower()
        for proc in psutil.process_iter(["pid", "name"]):
            proc_name = (proc.info.get("name") or "").lower()
            if name_lower in proc_name:
                return proc.info["pid"]
    except ImportError:
        pass
    return None


def _get_loaded_modules_from_pid(pid: int) -> List[str]:
    """List Python-importable module paths loaded by a process.

    Uses /proc/{pid}/maps on Linux or psutil.Process.memory_maps() on Windows.
    """
    module_paths: List[str] = []

    # Linux: parse /proc/{pid}/maps
    maps_path = Path(f"/proc/{pid}/maps")
    if maps_path.exists():
        try:
            text = maps_path.read_text(errors="replace")
            for line in text.splitlines():
                if ".py" in line or ".so" in line:
                    parts = line.strip().split()
                    if parts:
                        path = parts[-1]
                        if path.startswith("/") and Path(path).exists():
                            module_paths.append(path)
        except PermissionError:
            pass
        return list(set(module_paths))

    # Windows/Other: try psutil
    try:
        import psutil  # type: ignore[import]

        proc = psutil.Process(pid)
        for mmap in proc.memory_maps():
            path = getattr(mmap, "path", "")
            if path and (".py" in path or ".dll" in path or ".so" in path):
                module_paths.append(path)
    except Exception:
        pass

    return list(set(module_paths))


def _path_to_module_name(path: str) -> Optional[str]:
    """Convert a file path to an importable module name, if possible."""
    p = Path(path)
    if not p.exists() or p.suffix not in (".py", ".so", ".pyd"):
        return None
    # Walk up to find the package root
    parts = [p.stem]
    current = p.parent
    while (current / "__init__.py").exists():
        parts.insert(0, current.name)
        current = current.parent
    return ".".join(parts)


def discover_running_process(
    target: str,
    db: Database,
    llm: Optional[Any] = None,
) -> Dict[str, int]:
    """Inspect a running process and discover Python modules it has loaded.

    Finds the process by name, reads its loaded module paths, imports each
    Python module, and runs the Python package discovery on it.

    Also discovers any Python objects currently loaded in the current
    interpreter that match the target name (useful for in-process tools).

    Args:
        target: Process name (e.g. 'autocad', 'hysys') or Python module name.
        db: Open database instance.
        llm: Unused.

    Returns:
        Dict with counts: {'files': N, 'functions': N}.
    """
    from reverser.discovery.python_discovery import discover_python_package

    total_funcs = 0
    total_files = 0

    # --- Try the current Python interpreter first ---
    # If target is already a loaded module, introspect it directly
    if target in sys.modules:
        result = discover_python_package(target, db, llm)
        total_funcs += result["functions"]
        total_files += result["files"]
        return {"files": total_files, "functions": total_funcs}

    # --- Try to find a running process by name ---
    pid = _find_process_by_name(target)
    if pid is None:
        return {"files": 0, "functions": 0}

    loaded_paths = _get_loaded_modules_from_pid(pid)
    for path in loaded_paths:
        module_name = _path_to_module_name(path)
        if module_name is None:
            continue
        try:
            result = discover_python_package(module_name, db, llm)
            total_funcs += result["functions"]
            total_files += result["files"]
        except Exception:
            continue

    return {"files": total_files, "functions": total_funcs}
