"""Background service: system scan on boot, then MCP server."""

import json
import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Optional

from reverser.db import Database

log = logging.getLogger("reverser.service")

# State file: marks whether initial scan is complete
_SCAN_DONE_MARKER = ".reverser_scan_done"


def _setup_logging(log_file: Optional[str] = None) -> None:
    """Configure logging for the service."""
    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )


def _run_system_scan(db: Database, force: bool = False) -> None:
    """Run the one-time system scan if not already done.

    Args:
        db: Open database instance.
        force: Re-run even if scan marker exists.
    """
    db_dir = Path(db.db_path).parent
    marker = db_dir / _SCAN_DONE_MARKER

    if marker.exists() and not force:
        log.info("System scan already completed (delete %s to rescan).", marker)
        return

    log.info("Starting full system scan (this may take a few minutes)...")

    from reverser.discovery.system_discovery import discover_system

    def progress(msg: str) -> None:
        log.info(msg)

    stats = discover_system(db, progress_cb=progress)
    log.info(
        "System scan complete: %d processes, %d libraries, %d functions indexed.",
        stats["processes"],
        stats["libraries"],
        stats["functions"],
    )

    # Write marker so we don't re-scan on every start
    marker.write_text(
        json.dumps(
            {
                "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "stats": stats,
            },
            indent=2,
        )
    )
    log.info("Scan marker written to %s", marker)


def _run_classifier(db: Database, backend: str) -> None:
    """Run AI classification + schema generation on discovered functions."""
    from reverser.llm import LLM
    from reverser.classifier import classify_functions
    from reverser.schema_gen import generate_schemas_for_actions

    api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        log.warning("No LLM API key found — skipping AI classification.")
        return

    try:
        llm = LLM(backend=backend)
    except (ValueError, ImportError) as exc:
        log.warning("LLM init failed (%s) — skipping classification.", exc)
        return

    log.info("Classifying action functions...")
    action_count = classify_functions(db, llm)
    log.info("Identified %d action functions.", action_count)

    log.info("Generating MCP tool schemas...")
    schema_count = generate_schemas_for_actions(db, llm)
    log.info("Generated %d tool schemas.", schema_count)


def run_service(
    db_path: str,
    backend: str = "claude",
    skip_scan: bool = False,
    skip_classify: bool = False,
    force_rescan: bool = False,
    log_file: Optional[str] = None,
    mcp_port: Optional[int] = None,
) -> None:
    """Main service entry point.

    Phases:
    1. System scan — enumerate all /proc processes and loaded .so files
    2. AI classification — mark action functions and generate MCP schemas
    3. MCP server — start serving tools (stdio or TCP socket)

    Designed to be run as a systemd service (ExecStart).

    Args:
        db_path: Path to the SQLite database file.
        backend: LLM backend for classification ('claude', 'openai', 'ollama').
        skip_scan: Skip the system discovery phase.
        skip_classify: Skip AI classification (faster, no API key needed).
        force_rescan: Re-run system scan even if already done.
        log_file: Optional path to write log output.
        mcp_port: If set, start MCP server on a Unix socket at this port
                  instead of stdio. (Currently stdio only.)
    """
    _setup_logging(log_file)
    log.info("=== Code Reverser Service starting ===")
    log.info("Database: %s", db_path)

    # Ensure DB directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    db = Database(db_path)

    # Handle signals gracefully
    def _shutdown(signum: int, frame: object) -> None:
        log.info("Received signal %d, shutting down.", signum)
        db.close()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    # Phase 1: System scan
    if not skip_scan:
        _run_system_scan(db, force=force_rescan)
    else:
        log.info("System scan skipped (--skip-scan).")

    # Phase 2: AI classification
    if not skip_classify:
        _run_classifier(db, backend)
    else:
        log.info("AI classification skipped (--skip-classify).")

    stats = db.get_stats()
    log.info(
        "Ready: %d functions (%d actions) in database.",
        stats["functions"],
        stats["actions"],
    )

    # Phase 3: Start MCP server (blocks until killed)
    log.info("Starting MCP server (stdio)...")
    try:
        from reverser.mcp_server import run_mcp_server

        run_mcp_server(db_path)
    except ImportError:
        log.warning(
            "mcp package not installed — running in idle mode. "
            "Install with: pip install mcp"
        )
        # Fall back to idle loop so systemd keeps the service alive
        log.info("Service idle. Use 'reverser chat --db %s' to interact.", db_path)
        while True:
            time.sleep(3600)
    except Exception as exc:
        log.error("MCP server error: %s", exc)
        db.close()
        sys.exit(1)
