"""Generates and installs the systemd unit file for the reverser service."""

import grp
import os
import pwd
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Default locations
DEFAULT_DB_PATH = "/var/lib/reverser/tools.db"
DEFAULT_LOG_PATH = "/var/log/reverser/service.log"
UNIT_NAME = "reverser.service"
SYSTEMD_USER_DIR = Path.home() / ".config" / "systemd" / "user"
SYSTEMD_SYSTEM_DIR = Path("/etc/systemd/system")


def _get_python_executable() -> str:
    """Return the path to the current Python executable."""
    return sys.executable


def _get_current_user() -> str:
    """Return the current username."""
    return pwd.getpwuid(os.getuid()).pw_name


def generate_unit_file(
    db_path: str = DEFAULT_DB_PATH,
    log_path: str = DEFAULT_LOG_PATH,
    backend: str = "claude",
    user: Optional[str] = None,
    skip_classify: bool = False,
    extra_env: Optional[str] = None,
) -> str:
    """Generate the content of the systemd unit file.

    Args:
        db_path: Path to the SQLite database.
        log_path: Path for the service log file.
        backend: LLM backend ('claude', 'openai', 'ollama').
        user: User to run the service as (defaults to current user).
        skip_classify: If True, add --skip-classify flag to skip AI calls.
        extra_env: Optional extra Environment= lines for the unit file.

    Returns:
        String content of the .service unit file.
    """
    python = _get_python_executable()
    run_user = user or _get_current_user()

    cmd_parts = [
        python, "-m", "reverser", "service",
        "--db", db_path,
        "--backend", backend,
        "--log-file", log_path,
    ]
    if skip_classify:
        cmd_parts.append("--skip-classify")

    exec_start = " ".join(cmd_parts)

    env_lines = []
    if extra_env:
        for line in extra_env.strip().splitlines():
            env_lines.append(f"Environment={line.strip()}")
    env_block = "\n".join(env_lines)

    unit = f"""\
[Unit]
Description=Code Reverser - AI Function Mapping Service
Documentation=https://github.com/sudo-KNO3/python-playground
After=network.target
Wants=network-online.target

[Service]
Type=simple
User={run_user}
WorkingDirectory={Path.home()}
ExecStart={exec_start}
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=reverser
{env_block}

# Hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths={Path(db_path).parent} {Path(log_path).parent}

[Install]
WantedBy=default.target
"""
    return unit


def install_service(
    db_path: str = DEFAULT_DB_PATH,
    log_path: str = DEFAULT_LOG_PATH,
    backend: str = "claude",
    user: Optional[str] = None,
    skip_classify: bool = False,
    system_wide: bool = False,
    extra_env: Optional[str] = None,
) -> str:
    """Write the unit file and enable the systemd service.

    For user-level install (default), writes to ~/.config/systemd/user/.
    For system-wide install, writes to /etc/systemd/system/ (requires root).

    Args:
        db_path: Path to the SQLite database.
        log_path: Path for the service log file.
        backend: LLM backend name.
        user: Service user (system-wide only).
        skip_classify: Skip AI classification on startup.
        system_wide: Install as system service (requires root).
        extra_env: Extra environment variable lines.

    Returns:
        Path to the installed unit file.
    """
    content = generate_unit_file(
        db_path=db_path,
        log_path=log_path,
        backend=backend,
        user=user,
        skip_classify=skip_classify,
        extra_env=extra_env,
    )

    if system_wide:
        unit_dir = SYSTEMD_SYSTEM_DIR
    else:
        unit_dir = SYSTEMD_USER_DIR

    unit_dir.mkdir(parents=True, exist_ok=True)

    # Create DB and log directories
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)

    unit_path = unit_dir / UNIT_NAME
    unit_path.write_text(content)

    # Reload systemd and enable
    scope = [] if system_wide else ["--user"]
    try:
        subprocess.run(
            ["systemctl"] + scope + ["daemon-reload"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["systemctl"] + scope + ["enable", UNIT_NAME],
            check=True,
            capture_output=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(
            f"systemctl failed: {exc}. "
            "Is systemd running? Try 'systemctl --user daemon-reload' manually."
        ) from exc

    return str(unit_path)


def uninstall_service(system_wide: bool = False) -> None:
    """Stop, disable, and remove the reverser systemd service.

    Args:
        system_wide: If True, remove from /etc/systemd/system/.
    """
    scope = [] if system_wide else ["--user"]

    for cmd in [
        ["systemctl"] + scope + ["stop", UNIT_NAME],
        ["systemctl"] + scope + ["disable", UNIT_NAME],
    ]:
        try:
            subprocess.run(cmd, capture_output=True)
        except FileNotFoundError:
            pass

    unit_path = (
        SYSTEMD_SYSTEM_DIR / UNIT_NAME
        if system_wide
        else SYSTEMD_USER_DIR / UNIT_NAME
    )
    if unit_path.exists():
        unit_path.unlink()

    try:
        subprocess.run(
            ["systemctl"] + scope + ["daemon-reload"],
            check=True,
            capture_output=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass


def get_service_status() -> str:
    """Return the current systemd service status as a string."""
    for scope in [["--user"], []]:
        try:
            result = subprocess.run(
                ["systemctl"] + scope + ["status", UNIT_NAME, "--no-pager"],
                capture_output=True,
                text=True,
            )
            if result.returncode in (0, 3):  # 3 = inactive but unit exists
                return result.stdout.strip()
        except FileNotFoundError:
            pass
    return "(systemd not available or service not installed)"
