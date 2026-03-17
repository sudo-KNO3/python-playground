"""MCP server that exposes discovered action functions as tools."""

import importlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from reverser.db import Database

try:
    import mcp.server.stdio
    import mcp.types as mcp_types
    from mcp.server import Server

    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False


def _load_python_function(
    file_path: str, qualified_name: str
) -> Optional[Any]:
    """Dynamically load a Python function from its source file.

    Args:
        file_path: Absolute path to the .py file.
        qualified_name: Dotted qualified name, e.g. 'module.ClassName.method'.

    Returns:
        The callable, or None if it could not be loaded.
    """
    path = Path(file_path)
    if not path.exists():
        return None

    # Build a unique module name from the path to avoid collisions
    module_name = f"_reverser_loaded_{path.stem}_{abs(hash(file_path))}"

    if module_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            return None
        # Add the file's parent directory to sys.path for relative imports
        parent = str(path.parent)
        if parent not in sys.path:
            sys.path.insert(0, parent)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)  # type: ignore[union-attr]
        except Exception:
            del sys.modules[module_name]
            return None
    else:
        module = sys.modules[module_name]

    # Navigate dotted path: skip the first component (module/package name)
    parts = qualified_name.split(".")
    # Skip leading path component(s) that match the module name or file stem
    while parts and parts[0] in (path.stem, module_name):
        parts = parts[1:]

    obj: Any = module
    for part in parts:
        obj = getattr(obj, part, None)
        if obj is None:
            return None

    return obj if callable(obj) else None


def _build_mcp_tool(func_record: Dict[str, Any]) -> Optional[Any]:
    """Build an MCP Tool object from a function record.

    Args:
        func_record: Function dict from the database.

    Returns:
        mcp.types.Tool or None if schema is missing / MCP unavailable.
    """
    if not MCP_AVAILABLE:
        return None

    schema_str = func_record.get("tool_schema")
    if not schema_str:
        return None

    try:
        schema = json.loads(schema_str)
    except json.JSONDecodeError:
        return None

    return mcp_types.Tool(
        name=schema.get("name", func_record["name"]),
        description=schema.get(
            "description", func_record.get("ai_description", "")
        ),
        inputSchema=schema.get(
            "inputSchema", {"type": "object", "properties": {}}
        ),
    )


def run_mcp_server(db_path: str) -> None:
    """Start an MCP stdio server backed by the given database.

    Exposes all action functions as MCP tools. Python functions are
    executed by dynamic import; non-Python functions return an
    informational message.

    Args:
        db_path: Path to the SQLite database file.
    """
    if not MCP_AVAILABLE:
        raise ImportError(
            "mcp package is required. Run: pip install mcp"
        )

    db = Database(db_path)
    server: Server = Server("code-reverser")

    @server.list_tools()  # type: ignore[misc]
    async def handle_list_tools() -> List[Any]:
        """Return all action tools from the database."""
        actions = db.get_action_functions()
        tools = []
        for func in actions:
            tool = _build_mcp_tool(func)
            if tool is not None:
                tools.append(tool)
        return tools

    @server.call_tool()  # type: ignore[misc]
    async def handle_call_tool(
        name: str, arguments: Optional[Dict[str, Any]]
    ) -> List[Any]:
        """Execute a tool by name with the provided arguments."""
        args = arguments or {}

        # Find the function in the DB by tool name (schema name or func name)
        actions = db.get_action_functions()
        target = None
        for func in actions:
            schema_str = func.get("tool_schema")
            if schema_str:
                try:
                    schema = json.loads(schema_str)
                    if schema.get("name") == name:
                        target = func
                        break
                except json.JSONDecodeError:
                    pass
            if func.get("name") == name:
                target = func

        if target is None:
            return [
                mcp_types.TextContent(
                    type="text",
                    text=f"Error: tool '{name}' not found in database.",
                )
            ]

        # Only Python files can be executed
        file_path = ""
        # Fetch the file path via the file_id
        row = db.conn.execute(
            "SELECT path, language FROM files WHERE id = ?",
            (target["file_id"],),
        ).fetchone()

        if row is None:
            return [
                mcp_types.TextContent(
                    type="text",
                    text=f"Error: source file for tool '{name}' not found.",
                )
            ]

        file_path = row["path"]
        language = row["language"]

        if language != "Python":
            return [
                mcp_types.TextContent(
                    type="text",
                    text=(
                        f"Tool '{name}' is defined in a {language} file. "
                        "Execution is only supported for Python functions."
                    ),
                )
            ]

        func_callable = _load_python_function(
            file_path, target["qualified_name"]
        )
        if func_callable is None:
            return [
                mcp_types.TextContent(
                    type="text",
                    text=(
                        f"Error: could not load function "
                        f"'{target['qualified_name']}' from '{file_path}'."
                    ),
                )
            ]

        try:
            result = func_callable(**args)
        except Exception as exc:
            return [
                mcp_types.TextContent(
                    type="text",
                    text=f"Error executing '{name}': {type(exc).__name__}: {exc}",
                )
            ]

        # Serialize result to text
        if isinstance(result, (dict, list)):
            text = json.dumps(result, indent=2, default=str)
        else:
            text = str(result)

        return [mcp_types.TextContent(type="text", text=text)]

    import asyncio

    async def main() -> None:
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )

    asyncio.run(main())
