"""Binary/DLL export discovery using ctypes and optional pefile."""

import ctypes
import ctypes.util
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from reverser.db import Database


def _get_exports_ctypes(lib_path: str) -> List[str]:
    """Load a shared library and attempt to list exported symbols via nm/dumpbin."""
    symbols = []

    if sys.platform == "win32":
        # Use dumpbin /EXPORTS (requires MSVC tools) or fallback to pefile
        symbols = _get_exports_pefile(lib_path)
    else:
        # Use nm on Linux/Mac
        try:
            result = subprocess.run(
                ["nm", "-D", "--defined-only", lib_path],
                capture_output=True,
                text=True,
                timeout=30,
            )
            for line in result.stdout.splitlines():
                parts = line.strip().split()
                if len(parts) >= 3 and parts[1] in ("T", "W"):
                    name = parts[2]
                    if not name.startswith("_") or name.startswith("__Z"):
                        symbols.append(name)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        if not symbols:
            # Fallback: use objdump
            try:
                result = subprocess.run(
                    ["objdump", "-T", lib_path],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                for line in result.stdout.splitlines():
                    if " g " in line and ".text" in line:
                        parts = line.strip().split()
                        if parts:
                            name = parts[-1]
                            if name and not name.startswith("."):
                                symbols.append(name)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

    return list(set(symbols))


def _get_exports_pefile(lib_path: str) -> List[str]:
    """Use pefile (Windows PE parser) to get exported function names."""
    symbols = []
    try:
        import pefile  # type: ignore[import]

        pe = pefile.PE(lib_path)
        if hasattr(pe, "DIRECTORY_ENTRY_EXPORT"):
            for exp in pe.DIRECTORY_ENTRY_EXPORT.symbols:
                if exp.name:
                    name = exp.name.decode("utf-8", errors="replace")
                    symbols.append(name)
    except ImportError:
        # pefile not installed — try dumpbin
        try:
            result = subprocess.run(
                ["dumpbin", "/EXPORTS", lib_path],
                capture_output=True,
                text=True,
                timeout=30,
            )
            for line in result.stdout.splitlines():
                parts = line.strip().split()
                if len(parts) >= 4 and parts[0].isdigit():
                    symbols.append(parts[3])
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    except Exception:
        pass
    return symbols


def _demangle(name: str) -> str:
    """Attempt to demangle a C++ symbol name using c++filt."""
    try:
        result = subprocess.run(
            ["c++filt", name],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() or name
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return name


def _symbol_to_func_info(symbol: str, lib_path: str) -> Dict[str, Any]:
    """Convert an exported symbol name to a minimal function info dict."""
    demangled = _demangle(symbol)
    # Extract a readable name: take the part before '(' or use as-is
    readable = demangled.split("(")[0].split("::")[-1] if "::" in demangled else demangled
    return {
        "name": readable,
        "qualified_name": f"{Path(lib_path).stem}.{readable}",
        "signature": "()",
        "docstring": f"Exported symbol: {demangled}",
        "source": None,
    }


def discover_binary(
    target: str,
    db: Database,
    llm: Optional[Any] = None,
) -> Dict[str, int]:
    """Discover exported functions from a compiled binary/DLL.

    Uses nm/objdump on Linux/Mac and pefile/dumpbin on Windows to extract
    the export table from the binary, then stores each symbol as a function
    record with execution_method='subprocess'.

    Args:
        target: Path to the .so, .dll, or .exe file.
        db: Open database instance.
        llm: Unused (reserved for future AI description generation).

    Returns:
        Dict with counts: {'files': N, 'functions': N}.
    """
    path = Path(target)
    if not path.exists():
        return {"files": 0, "functions": 0}

    suffix = path.suffix.lower()
    if suffix not in (".so", ".dll", ".exe", ".dylib", ""):
        return {"files": 0, "functions": 0}

    symbols = _get_exports_ctypes(str(path))
    if not symbols:
        return {"files": 0, "functions": 0}

    # Determine language from binary type
    language = "C/C++" if suffix in (".dll", ".so", ".dylib") else "Binary"
    file_id = db.upsert_file(str(path.resolve()), language)

    func_count = 0
    for symbol in symbols:
        info = _symbol_to_func_info(symbol, str(path))
        func_id = db.upsert_function(
            file_id=file_id,
            name=info["name"],
            qualified_name=info["qualified_name"],
            signature=info["signature"],
            docstring=info["docstring"],
            source=None,
            start_line=0,
            end_line=0,
            is_public=True,
        )
        # Set execution method to subprocess and store the binary path
        db.conn.execute(
            """
            UPDATE functions
            SET execution_method = 'subprocess', wrapper_path = ?
            WHERE id = ?
            """,
            (str(path.resolve()), func_id),
        )
        db.conn.commit()
        func_count += 1

    return {"files": 1, "functions": func_count}
