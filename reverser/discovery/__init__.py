"""Deep discovery engine: invasively maps programs on the host system."""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from reverser.db import Database

logger = logging.getLogger(__name__)


def discover(
    target: str,
    db: Database,
    llm: Optional[Any] = None,
) -> Dict[str, int]:
    """Run all applicable discovery strategies against a target.

    Tries each strategy in order and aggregates results into the database.
    Each strategy is attempted independently; failures are silently skipped.

    Args:
        target: Program identifier — one of:
            - A Python module/package name (e.g. 'flopy', 'autocad')
            - A COM ProgID (e.g. 'AutoCAD.Application')
            - A path to an executable or DLL (e.g. '/path/to/aermod.exe')
            - 'system' to scan all COM-registered programs
        db: Open database instance.
        llm: Optional LLM for AI-assisted description generation.

    Returns:
        Dict with counts: {'files': N, 'functions': N, 'strategies_used': N}.
    """
    from reverser.discovery.com_discovery import discover_com
    from reverser.discovery.python_discovery import discover_python_package
    from reverser.discovery.binary_discovery import discover_binary
    from reverser.discovery.process_discovery import discover_running_process

    strategies_used = 0
    total_functions = 0
    total_files = 0

    # --- Strategy 1: Python package ---
    try:
        result = discover_python_package(target, db, llm)
        if result["functions"] > 0:
            total_functions += result["functions"]
            total_files += result["files"]
            strategies_used += 1
    except Exception:
        logger.warning("Python package discovery failed for %r", target, exc_info=True)

    # --- Strategy 2: COM type library ---
    try:
        result = discover_com(target, db, llm)
        if result["functions"] > 0:
            total_functions += result["functions"]
            total_files += result["files"]
            strategies_used += 1
    except Exception:
        logger.warning("COM discovery failed for %r", target, exc_info=True)

    # --- Strategy 3: Binary/DLL export scan ---
    if Path(target).exists():
        try:
            result = discover_binary(target, db, llm)
            if result["functions"] > 0:
                total_functions += result["functions"]
                total_files += result["files"]
                strategies_used += 1
        except Exception:
            logger.warning("Binary discovery failed for %r", target, exc_info=True)

    # --- Strategy 4: Running process ---
    try:
        result = discover_running_process(target, db, llm)
        if result["functions"] > 0:
            total_functions += result["functions"]
            total_files += result["files"]
            strategies_used += 1
    except Exception:
        logger.warning("Process discovery failed for %r", target, exc_info=True)

    return {
        "files": total_files,
        "functions": total_functions,
        "strategies_used": strategies_used,
    }
