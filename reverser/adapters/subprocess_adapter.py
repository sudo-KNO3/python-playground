"""Subprocess-based adapter for executing compiled CLI programs."""

import json
import subprocess
import shlex
from pathlib import Path
from typing import Any, Dict, List

from reverser.adapters import BaseAdapter


class SubprocessAdapter(BaseAdapter):
    """Executes a compiled CLI program by building a command from arguments.

    The `wrapper_path` column on the function record is interpreted as the
    path to the executable (or a JSON config describing how to invoke it).
    """

    def execute(
        self, func_record: Dict[str, Any], arguments: Dict[str, Any]
    ) -> str:
        """Run the executable with arguments constructed from the tool call.

        Args:
            func_record: Function dict from the database. `wrapper_path` must
                         be set to the executable path (or a JSON config).
            arguments: Keyword arguments from the MCP tool call.

        Returns:
            Combined stdout + stderr from the subprocess, or an error message.
        """
        wrapper_path = func_record.get("wrapper_path") or ""
        if not wrapper_path:
            return (
                "Error: no executable path configured for this tool. "
                "Run 'reverser generate-wrappers' to set it up."
            )

        # wrapper_path may be a plain path or a JSON config
        cmd, input_data = self._build_command(wrapper_path, func_record, arguments)
        if cmd is None:
            return f"Error: could not build command for '{func_record.get('name')}'."

        try:
            result = subprocess.run(
                cmd,
                input=input_data,
                capture_output=True,
                text=True,
                timeout=120,
            )
            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"
            if result.returncode != 0:
                output = (
                    f"Process exited with code {result.returncode}\n" + output
                )
            return output.strip() or "(no output)"
        except FileNotFoundError:
            return f"Error: executable not found at '{cmd[0]}'."
        except subprocess.TimeoutExpired:
            return "Error: process timed out after 120 seconds."
        except OSError as exc:
            return f"Error running process: {exc}"

    def _build_command(
        self,
        wrapper_path: str,
        func_record: Dict[str, Any],
        arguments: Dict[str, Any],
    ) -> "tuple[List[str], str]":
        """Build the command list and optional stdin input.

        If wrapper_path is valid JSON, it is treated as a config dict:
        {
          "executable": "/path/to/exe",
          "arg_style": "flags" | "positional" | "stdin_json",
          "fixed_args": ["--mode", "run"]
        }

        Otherwise wrapper_path is treated as the bare executable path and
        arguments are passed as --key=value flags.

        Returns:
            Tuple of (command list, stdin string).
        """
        config: Dict[str, Any] = {}
        try:
            config = json.loads(wrapper_path)
        except (json.JSONDecodeError, TypeError):
            config = {"executable": wrapper_path, "arg_style": "flags"}

        executable = config.get("executable", wrapper_path)
        arg_style = config.get("arg_style", "flags")
        fixed_args: List[str] = config.get("fixed_args", [])

        cmd = [str(executable)] + fixed_args
        stdin_data = ""

        if arg_style == "stdin_json":
            stdin_data = json.dumps(arguments)
        elif arg_style == "positional":
            for value in arguments.values():
                cmd.append(str(value))
        else:  # flags (default)
            for key, value in arguments.items():
                cmd.append(f"--{key}={value}")

        return cmd, stdin_data
