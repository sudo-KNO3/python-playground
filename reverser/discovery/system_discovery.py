"""Low-level Linux system scanner: processes, loaded modules, ELF exports."""

import os
import re
import struct
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple

from reverser.db import Database

# ELF magic bytes
_ELF_MAGIC = b"\x7fELF"


# ── /proc helpers ────────────────────────────────────────────────────────────

def iter_processes() -> Iterator[Dict[str, Any]]:
    """Yield info dicts for every accessible process in /proc.

    Each dict contains: pid, name, exe, cmdline.
    Processes we cannot read (permission denied) are silently skipped.
    """
    proc_root = Path("/proc")
    for entry in proc_root.iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        info: Dict[str, Any] = {"pid": pid, "name": "", "exe": "", "cmdline": ""}

        # Process name from /proc/{pid}/comm
        try:
            info["name"] = (entry / "comm").read_text().strip()
        except (PermissionError, FileNotFoundError):
            pass

        # Executable path
        try:
            info["exe"] = str((entry / "exe").resolve())
        except (PermissionError, OSError):
            pass

        # Command line
        try:
            cmdline = (entry / "cmdline").read_bytes()
            info["cmdline"] = cmdline.replace(b"\x00", b" ").decode("utf-8", errors="replace").strip()
        except (PermissionError, FileNotFoundError):
            pass

        yield info


def get_mapped_libraries(pid: int) -> Set[str]:
    """Return the set of shared library paths loaded by a process.

    Reads /proc/{pid}/maps and extracts all .so file paths.

    Args:
        pid: Process ID.

    Returns:
        Set of absolute paths to loaded shared libraries.
    """
    libs: Set[str] = []
    maps_file = Path(f"/proc/{pid}/maps")
    try:
        for line in maps_file.read_text(errors="replace").splitlines():
            # Format: addr perms offset dev inode pathname
            parts = line.split()
            if len(parts) >= 6:
                path = parts[5]
                if path.startswith("/") and ".so" in path:
                    libs.append(path)
    except (PermissionError, FileNotFoundError):
        pass
    return set(libs)


# ── ELF export extraction ────────────────────────────────────────────────────

def _read_elf_exports_pyelftools(path: str) -> List[str]:
    """Use pyelftools to extract exported symbol names from an ELF binary."""
    symbols: List[str] = []
    try:
        from elftools.elf.elffile import ELFFile  # type: ignore[import]
        from elftools.elf.sections import SymbolTableSection  # type: ignore[import]

        with open(path, "rb") as f:
            elf = ELFFile(f)
            for section in elf.iter_sections():
                if isinstance(section, SymbolTableSection):
                    for sym in section.iter_symbols():
                        name = sym.name
                        if (
                            name
                            and sym["st_info"]["type"] == "STT_FUNC"
                            and sym["st_shndx"] != "SHN_UNDEF"
                            and not name.startswith("_")
                        ):
                            symbols.append(name)
    except (ImportError, Exception):
        pass
    return symbols


def _read_elf_exports_nm(path: str) -> List[str]:
    """Use nm -D to extract exported symbol names from a shared library."""
    symbols: List[str] = []
    try:
        result = subprocess.run(
            ["nm", "-D", "--defined-only", "--format=posix", path],
            capture_output=True,
            text=True,
            timeout=15,
        )
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[1] in ("T", "W", "t"):
                name = parts[0]
                if name and not name.startswith("_"):
                    symbols.append(name)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return symbols


def get_elf_exports(path: str) -> List[str]:
    """Extract exported function names from an ELF binary or shared library.

    Tries pyelftools first (more accurate), falls back to nm.

    Args:
        path: Absolute path to the ELF file.

    Returns:
        List of exported function names (deduped, non-empty).
    """
    if not Path(path).exists():
        return []

    # Check ELF magic
    try:
        with open(path, "rb") as f:
            magic = f.read(4)
        if magic != _ELF_MAGIC:
            return []
    except (OSError, PermissionError):
        return []

    symbols = _read_elf_exports_pyelftools(path)
    if not symbols:
        symbols = _read_elf_exports_nm(path)

    return list(dict.fromkeys(symbols))  # dedupe, preserve order


# ── Demangle ─────────────────────────────────────────────────────────────────

def _demangle(name: str) -> str:
    """Demangle a C++ symbol name using c++filt, or return as-is."""
    try:
        result = subprocess.run(
            ["c++filt", name],
            capture_output=True,
            text=True,
            timeout=5,
        )
        demangled = result.stdout.strip()
        return demangled if demangled else name
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return name


def _readable_name(symbol: str) -> str:
    """Convert a symbol to a clean, readable function name."""
    demangled = _demangle(symbol)
    # Strip namespace prefixes for a simple name
    clean = demangled.split("(")[0].split("::")[-1]
    # Replace non-identifier chars
    clean = re.sub(r"[^a-zA-Z0-9_]", "_", clean)
    return clean or symbol


# ── Main system discovery ────────────────────────────────────────────────────

def discover_system(
    db: Database,
    llm: Optional[Any] = None,
    progress_cb: Optional[Any] = None,
) -> Dict[str, int]:
    """Full low-level Linux system scan.

    Enumerates every running process, collects all .so libraries loaded
    by those processes, extracts ELF exported symbols, and stores them
    in the database. Also indexes Python modules loaded in the current
    interpreter.

    Args:
        db: Open database instance.
        llm: Unused (reserved for future description generation).
        progress_cb: Optional callable(message: str) for progress output.

    Returns:
        Dict with counts: {'processes': N, 'libraries': N, 'functions': N}.
    """

    def _log(msg: str) -> None:
        if progress_cb:
            progress_cb(msg)

    processes_seen: Set[int] = set()
    libraries_seen: Set[str] = set()
    func_count = 0
    proc_count = 0
    lib_count = 0

    _log("Enumerating running processes...")

    all_lib_paths: Set[str] = set()

    for proc_info in iter_processes():
        pid = proc_info["pid"]
        processes_seen.add(pid)
        proc_count += 1

        # Collect .so paths from this process's memory maps
        libs = get_mapped_libraries(pid)
        all_lib_paths.update(libs)

    _log(f"Found {proc_count} processes, {len(all_lib_paths)} unique libraries.")

    # Deduplicate: map canonical paths
    canonical_libs: Set[str] = set()
    for lib_path in all_lib_paths:
        try:
            canon = str(Path(lib_path).resolve())
            canonical_libs.add(canon)
        except OSError:
            canonical_libs.add(lib_path)

    _log(f"Scanning {len(canonical_libs)} unique shared libraries for exports...")

    for lib_path in sorted(canonical_libs):
        if lib_path in libraries_seen:
            continue
        libraries_seen.add(lib_path)

        exports = get_elf_exports(lib_path)
        if not exports:
            continue

        lib_count += 1
        lib_name = Path(lib_path).name
        _log(f"  {lib_name}: {len(exports)} exports")

        file_id = db.upsert_file(lib_path, "C/C++")

        for symbol in exports:
            readable = _readable_name(symbol)
            qualified_name = f"{Path(lib_path).stem}.{readable}"

            func_id = db.upsert_function(
                file_id=file_id,
                name=readable,
                qualified_name=qualified_name,
                signature="(...)",
                docstring=f"Exported from {lib_name}: {symbol}",
                source=None,
                start_line=0,
                end_line=0,
                is_public=True,
            )
            # Mark execution method as subprocess (call via wrapper)
            db.conn.execute(
                "UPDATE functions SET execution_method='subprocess', wrapper_path=? WHERE id=?",
                (lib_path, func_id),
            )
            func_count += 1

    db.conn.commit()

    # Also index Python's own loaded modules from the current interpreter
    _log("Indexing loaded Python modules...")
    py_funcs = 0
    from reverser.discovery.python_discovery import discover_python_package

    python_mods_seen: Set[str] = set()
    for mod_name in list(sys.modules.keys()):
        # Only top-level packages, skip internal/private
        if "." in mod_name or mod_name.startswith("_"):
            continue
        if mod_name in python_mods_seen:
            continue
        python_mods_seen.add(mod_name)
        try:
            result = discover_python_package(mod_name, db)
            py_funcs += result.get("functions", 0)
        except Exception:
            pass

    _log(f"Indexed {py_funcs} Python functions from loaded modules.")

    return {
        "processes": proc_count,
        "libraries": lib_count,
        "functions": func_count + py_funcs,
    }
