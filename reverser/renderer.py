"""Rich console rendering for reverser CLI output."""

import json
from typing import Any, Dict, List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from reverser.db import Database


def _make_console(no_color: bool = False) -> Console:
    """Create a Rich Console instance."""
    return Console(no_color=no_color, highlight=False)


def render_stats(stats: Dict[str, int], console: Console) -> None:
    """Render database statistics as a simple table.

    Args:
        stats: Dict with counts for files, functions, actions, calls, imports.
        console: Rich Console to print to.
    """
    table = Table(title="Database Statistics", show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Count", justify="right", style="bold green")
    for key, value in stats.items():
        table.add_row(key.replace("_", " ").title(), str(value))
    console.print(table)


def render_search_results(
    results: List[Dict[str, Any]], console: Console
) -> None:
    """Render tool search results as a table.

    Args:
        results: List of function dicts from the database.
        console: Rich Console to print to.
    """
    if not results:
        console.print("[yellow]No tools found matching the query.[/yellow]")
        return

    table = Table(
        title=f"Found {len(results)} tool(s)",
        show_header=True,
        expand=True,
    )
    table.add_column("Tool Name", style="cyan", min_width=20)
    table.add_column("Qualified Name", style="dim", min_width=30)
    table.add_column("Description", min_width=40)
    table.add_column("Confidence", justify="right", style="green")

    for func in results:
        confidence = func.get("action_confidence")
        conf_str = f"{confidence:.2f}" if confidence is not None else "-"
        table.add_row(
            func.get("name", "-"),
            func.get("qualified_name", "-"),
            func.get("ai_description") or "-",
            conf_str,
        )

    console.print(table)


def render_network(
    function_record: Dict[str, Any],
    callers: List[str],
    callees: List[str],
    console: Console,
) -> None:
    """Render the call network for a single function.

    Args:
        function_record: Function dict from the database.
        callers: Qualified names of functions that call this one.
        callees: Names of functions called by this one.
        console: Rich Console to print to.
    """
    name = function_record.get("qualified_name", "unknown")
    console.print(
        Panel(
            f"[bold cyan]{name}[/bold cyan]\n\n"
            f"[dim]{function_record.get('signature', '')}[/dim]",
            title="Function",
            border_style="blue",
        )
    )

    if callers:
        caller_text = "\n".join(f"  [green]→[/green] {c}" for c in callers)
        console.print(
            Panel(caller_text, title="Called by", border_style="green")
        )
    else:
        console.print("[dim]  (no known callers)[/dim]")

    if callees:
        callee_text = "\n".join(f"  [yellow]→[/yellow] {c}" for c in callees)
        console.print(
            Panel(callee_text, title="Calls", border_style="yellow")
        )
    else:
        console.print("[dim]  (no recorded callees)[/dim]")


def render_tool_schema(
    function_record: Dict[str, Any], console: Console
) -> None:
    """Render the MCP tool schema for an action function.

    Args:
        function_record: Function dict with tool_schema field.
        console: Rich Console to print to.
    """
    schema_str = function_record.get("tool_schema")
    if not schema_str:
        console.print("[yellow]No tool schema generated yet.[/yellow]")
        return

    try:
        schema = json.loads(schema_str)
    except json.JSONDecodeError:
        console.print("[red]Tool schema is malformed JSON.[/red]")
        return

    console.print(
        Panel(
            json.dumps(schema, indent=2),
            title=f"MCP Tool Schema: {schema.get('name', '-')}",
            border_style="magenta",
        )
    )


def render_scan_progress(
    file_path: str,
    function_count: int,
    console: Console,
) -> None:
    """Print a single scan progress line.

    Args:
        file_path: Path of the file just scanned.
        function_count: Number of functions found.
        console: Rich Console to print to.
    """
    console.print(
        f"  [dim]{file_path}[/dim] "
        f"[cyan]{function_count}[/cyan] function(s)"
    )
