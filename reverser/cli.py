"""CLI commands for the reverser tool."""

from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from reverser.db import Database
from reverser.renderer import (
    render_network,
    render_scan_progress,
    render_search_results,
    render_stats,
    render_tool_schema,
)


def _make_llm(
    backend: str,
    ollama_host: Optional[str] = None,
    ollama_model: Optional[str] = None,
) -> "reverser.llm.LLM":  # type: ignore[name-defined]
    """Instantiate an LLM, providing a clear error on missing dependencies."""
    from reverser.llm import LLM

    try:
        return LLM(
            backend=backend,
            ollama_host=ollama_host,
            ollama_model=ollama_model,
        )
    except (ValueError, ImportError) as exc:
        raise click.ClickException(str(exc))


@click.group()
def cli() -> None:
    """AI-powered codebase reverse engineer and MCP tool server."""


@cli.command()
@click.argument("project_path", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--db",
    "db_path",
    default="tools.db",
    show_default=True,
    help="Path to the SQLite database file.",
)
@click.option(
    "--backend",
    default="claude",
    show_default=True,
    type=click.Choice(["claude", "openai", "ollama"]),
    help="LLM backend for classification and schema generation.",
)
@click.option(
    "--ollama-host",
    default=None,
    help="Ollama server URL (overrides REVERSER_OLLAMA_HOST).",
)
@click.option(
    "--ollama-model",
    default=None,
    help="Ollama model name (overrides REVERSER_OLLAMA_MODEL).",
)
@click.option(
    "--no-classify",
    is_flag=True,
    default=False,
    help="Skip AI classification step (parse and index only).",
)
@click.option(
    "--no-color",
    is_flag=True,
    default=False,
    help="Disable rich terminal colors.",
)
def scan(
    project_path: str,
    db_path: str,
    backend: str,
    ollama_host: Optional[str],
    ollama_model: Optional[str],
    no_classify: bool,
    no_color: bool,
) -> None:
    """Scan a project directory and populate the tool database.

    Parses all source files, builds the call/dependency graph,
    classifies action functions, and generates MCP tool schemas.
    """
    from reverser.classifier import classify_functions
    from reverser.graph import NetworkBuilder
    from reverser.parser import parse_file
    from reverser.scanner import detect_language, scan_directory
    from reverser.schema_gen import generate_schemas_for_actions

    console = Console(no_color=no_color, highlight=False)
    db = Database(db_path)
    root = Path(project_path)

    console.print(f"\n[bold]Scanning[/bold] {root}")
    console.print(f"[dim]Database: {db_path}[/dim]\n")

    llm = None if no_classify else _make_llm(backend, ollama_host, ollama_model)

    network = NetworkBuilder()
    file_infos = []

    for source_file in scan_directory(root):
        lang = detect_language(source_file)
        file_info = parse_file(source_file, lang, llm)
        file_infos.append(file_info)
        network.add_file(file_info)
        render_scan_progress(str(source_file), len(file_info.functions), console)

    # Persist files and functions to DB
    console.print("\n[bold]Indexing into database...[/bold]")
    for file_info in file_infos:
        file_id = db.upsert_file(file_info.path, file_info.language)
        func_id_map = {}
        for func in file_info.functions:
            fid = db.upsert_function(
                file_id=file_id,
                name=func.name,
                qualified_name=func.qualified_name,
                signature=func.signature,
                docstring=func.docstring,
                source=func.source,
                start_line=func.start_line,
                end_line=func.end_line,
                is_public=func.is_public,
            )
            func_id_map[func.qualified_name] = fid
        for imp in file_info.imports:
            db.insert_import(file_id, imp.module, imp.alias, imp.imported_names)

    # Persist call edges
    call_edges = network.resolve_calls()
    for edge in call_edges:
        caller_id = db.get_function_id(edge.caller_qualified_name)
        callee_id = db.get_function_id(
            network.get_qualified_name(edge.callee_name) or edge.callee_name
        )
        if caller_id is not None:
            db.insert_call(caller_id, edge.callee_name, callee_id)

    stats = db.get_stats()
    console.print(
        f"\n[green]Indexed[/green] {stats['files']} file(s), "
        f"{stats['functions']} function(s)."
    )

    if not no_classify and llm is not None:
        console.print("\n[bold]Classifying action functions...[/bold]")
        action_count = classify_functions(db, llm)
        console.print(
            f"[green]Identified[/green] {action_count} action function(s)."
        )

        console.print("\n[bold]Generating MCP tool schemas...[/bold]")
        schema_count = generate_schemas_for_actions(db, llm)
        console.print(
            f"[green]Generated[/green] {schema_count} tool schema(s)."
        )

    render_stats(db.get_stats(), console)
    db.close()


@cli.command()
@click.option(
    "--db",
    "db_path",
    default="tools.db",
    show_default=True,
    help="Path to the SQLite database file.",
)
def serve(db_path: str) -> None:
    """Start the MCP stdio server backed by the tool database.

    Connect this server to Claude Desktop or another MCP client.
    """
    if not Path(db_path).exists():
        raise click.ClickException(
            f"Database '{db_path}' not found. Run 'reverser scan' first."
        )
    from reverser.mcp_server import run_mcp_server

    run_mcp_server(db_path)


@cli.command()
@click.argument("query")
@click.option(
    "--db",
    "db_path",
    default="tools.db",
    show_default=True,
    help="Path to the SQLite database file.",
)
@click.option(
    "--no-color",
    is_flag=True,
    default=False,
    help="Disable rich terminal colors.",
)
def search(query: str, db_path: str, no_color: bool) -> None:
    """Search for tools in the database by keyword."""
    if not Path(db_path).exists():
        raise click.ClickException(
            f"Database '{db_path}' not found. Run 'reverser scan' first."
        )
    console = Console(no_color=no_color, highlight=False)
    db = Database(db_path)
    results = db.search_tools(query)
    db.close()
    render_search_results(results, console)


@cli.command()
@click.option(
    "--db",
    "db_path",
    default="tools.db",
    show_default=True,
    help="Path to the SQLite database file.",
)
@click.option(
    "--function",
    "function_name",
    required=True,
    help="Qualified function name to inspect.",
)
@click.option(
    "--no-color",
    is_flag=True,
    default=False,
    help="Disable rich terminal colors.",
)
def network(db_path: str, function_name: str, no_color: bool) -> None:
    """Show the call/dependency network for a specific function."""
    if not Path(db_path).exists():
        raise click.ClickException(
            f"Database '{db_path}' not found. Run 'reverser scan' first."
        )
    console = Console(no_color=no_color, highlight=False)
    db = Database(db_path)

    row = db.conn.execute(
        "SELECT * FROM functions WHERE qualified_name = ?",
        (function_name,),
    ).fetchone()

    if row is None:
        db.close()
        raise click.ClickException(
            f"Function '{function_name}' not found in database."
        )

    func_record = dict(row)
    callers = db.get_function_callers(func_record["id"])
    callees = db.get_function_calls(func_record["id"])
    db.close()

    render_network(func_record, callers, callees, console)
    render_tool_schema(func_record, console)


@cli.command()
@click.option(
    "--db",
    "db_path",
    default="tools.db",
    show_default=True,
    help="Path to the SQLite database file.",
)
@click.option(
    "--backend",
    default="claude",
    show_default=True,
    type=click.Choice(["claude", "openai", "ollama"]),
    help="LLM backend to use.",
)
@click.option(
    "--ollama-host",
    default=None,
    help="Ollama server URL.",
)
@click.option(
    "--ollama-model",
    default=None,
    help="Ollama model name.",
)
@click.option(
    "--no-color",
    is_flag=True,
    default=False,
    help="Disable rich terminal colors.",
)
def classify(
    db_path: str,
    backend: str,
    ollama_host: Optional[str],
    ollama_model: Optional[str],
    no_color: bool,
) -> None:
    """Re-classify action functions without re-scanning the project."""
    if not Path(db_path).exists():
        raise click.ClickException(
            f"Database '{db_path}' not found. Run 'reverser scan' first."
        )
    from reverser.classifier import classify_functions
    from reverser.schema_gen import generate_schemas_for_actions

    console = Console(no_color=no_color, highlight=False)
    db = Database(db_path)
    llm = _make_llm(backend, ollama_host, ollama_model)

    console.print("[bold]Classifying action functions...[/bold]")
    action_count = classify_functions(db, llm)
    console.print(f"[green]Identified[/green] {action_count} action function(s).")

    console.print("\n[bold]Generating MCP tool schemas...[/bold]")
    schema_count = generate_schemas_for_actions(db, llm)
    console.print(f"[green]Generated[/green] {schema_count} tool schema(s).")

    render_stats(db.get_stats(), console)
    db.close()


@cli.command("generate-wrappers")
@click.option(
    "--db",
    "db_path",
    default="tools.db",
    show_default=True,
    help="Path to the SQLite database file.",
)
@click.option(
    "--program",
    required=True,
    help=(
        "Path to the executable (subprocess/python_sdk) "
        "or COM ProgID (com), e.g. 'HYSYS.Application'."
    ),
)
@click.option(
    "--method",
    default="subprocess_cli",
    show_default=True,
    type=click.Choice(["subprocess_cli", "com", "python_sdk", "generic"]),
    help="How the program is invoked.",
)
@click.option(
    "--wrappers-dir",
    default="wrappers",
    show_default=True,
    help="Directory where generated wrapper .py files are saved.",
)
@click.option(
    "--language",
    default=None,
    help="Only generate wrappers for functions in this language (e.g. Fortran).",
)
@click.option(
    "--backend",
    default="claude",
    show_default=True,
    type=click.Choice(["claude", "openai", "ollama"]),
    help="LLM backend to use.",
)
@click.option(
    "--ollama-host",
    default=None,
    help="Ollama server URL.",
)
@click.option(
    "--ollama-model",
    default=None,
    help="Ollama model name.",
)
@click.option(
    "--no-color",
    is_flag=True,
    default=False,
    help="Disable rich terminal colors.",
)
def generate_wrappers(
    db_path: str,
    program: str,
    method: str,
    wrappers_dir: str,
    language: Optional[str],
    backend: str,
    ollama_host: Optional[str],
    ollama_model: Optional[str],
    no_color: bool,
) -> None:
    """Generate Python wrapper functions for non-Python action tools.

    For each action function discovered in the scanned codebase, uses an LLM
    to write a Python function that correctly interacts with the target program
    (subprocess, COM automation, or Python SDK). The wrappers are saved as .py
    files and registered in the database so the MCP server can call them.

    Examples:

    \\b
    # AERMOD (Fortran CLI tool)
    reverser generate-wrappers --db aermod.db \\
        --program /path/to/aermod.exe --method subprocess_cli

    \\b
    # HYSYS (Windows COM)
    reverser generate-wrappers --db hysys.db \\
        --program HYSYS.Application --method com

    \\b
    # MODFLOW via FloPy (Python SDK)
    reverser generate-wrappers --db modflow.db \\
        --program flopy --method python_sdk
    """
    if not Path(db_path).exists():
        raise click.ClickException(
            f"Database '{db_path}' not found. Run 'reverser scan' first."
        )

    from reverser.adapters.wrapper_gen import generate_wrappers_for_actions

    console = Console(no_color=no_color, highlight=False)
    db = Database(db_path)
    llm = _make_llm(backend, ollama_host, ollama_model)
    wrappers_path = Path(wrappers_dir)

    console.print(
        f"\n[bold]Generating Python wrappers[/bold] → [dim]{wrappers_dir}/[/dim]"
    )
    console.print(f"  Program : [cyan]{program}[/cyan]")
    console.print(f"  Method  : [cyan]{method}[/cyan]")
    if language:
        console.print(f"  Language: [cyan]{language}[/cyan]")
    console.print()

    count = generate_wrappers_for_actions(
        db=db,
        llm=llm,
        program_path=program,
        exec_method=method,
        wrappers_dir=wrappers_path,
        language_filter=language,
    )

    console.print(
        f"[green]Generated[/green] {count} wrapper(s) in [dim]{wrappers_dir}/[/dim]"
    )
    db.close()
