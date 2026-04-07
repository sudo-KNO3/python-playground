"""Interactive REPL: natural language → live function execution."""

import sys
from pathlib import Path
from typing import List, Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.text import Text


BANNER = """\
[bold cyan]Code Reverser[/bold cyan] — Natural Language Interface
Type a request in plain English to call functions in connected programs.
Type [bold]/help[/bold] for commands, [bold]/exit[/bold] to quit.
"""

HELP_TEXT = """\
## Commands

- `/exit` or `/quit` — Exit the REPL
- `/stats` — Show database statistics
- `/search <query>` — Search for tools matching a keyword
- `/tools` — List all discovered action tools
- `/schema <name>` — Show MCP schema for a specific tool
- `/history` — Show recent requests
- `/clear` — Clear the screen

## Examples

```
design a 20x20x20m box
run an air dispersion model with emission rate 100 g/s
simulate groundwater flow in a 500x500m grid
calculate the pressure drop across a heat exchanger
add a circle with radius 5 at point (0, 0, 0)
```
"""


class REPL:
    """Interactive natural language interface to the function database.

    Maintains a session with the orchestrator and streams results to
    the terminal using rich formatting.
    """

    def __init__(
        self,
        db_path: str,
        model: str = "claude-opus-4-5",
        no_color: bool = False,
    ) -> None:
        """Initialize the REPL.

        Args:
            db_path: Path to the SQLite database file.
            model: Claude model ID for the orchestrator.
            no_color: Disable rich terminal colors.
        """
        from reverser.db import Database
        from reverser.agents.orchestrator import Orchestrator

        self.console = Console(no_color=no_color, highlight=False)
        self.db = Database(db_path)
        self.orchestrator = Orchestrator(self.db, model=model)
        self.history: List[str] = []

    def _print_banner(self) -> None:
        stats = self.db.get_stats()
        self.console.print(
            Panel(
                BANNER
                + f"\n[dim]Database: {stats['functions']} functions, "
                f"{stats['actions']} actions ready[/dim]",
                border_style="cyan",
            )
        )

    def _handle_command(self, line: str) -> bool:
        """Handle a slash command. Returns True if handled."""
        parts = line.strip().split(None, 1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd in ("/exit", "/quit"):
            self.console.print("[dim]Goodbye.[/dim]")
            return True  # signal exit

        elif cmd == "/help":
            self.console.print(Markdown(HELP_TEXT))

        elif cmd == "/stats":
            from reverser.renderer import render_stats
            render_stats(self.db.get_stats(), self.console)

        elif cmd == "/search":
            if not arg:
                self.console.print("[yellow]Usage: /search <query>[/yellow]")
            else:
                from reverser.renderer import render_search_results
                results = self.db.search_tools(arg)
                render_search_results(results, self.console)

        elif cmd == "/tools":
            from reverser.renderer import render_search_results
            actions = self.db.get_action_functions()
            render_search_results(actions, self.console)

        elif cmd == "/schema":
            if not arg:
                self.console.print("[yellow]Usage: /schema <tool_name>[/yellow]")
            else:
                row = self.db.conn.execute(
                    "SELECT * FROM functions WHERE name = ? OR qualified_name = ?",
                    (arg, arg),
                ).fetchone()
                if row:
                    from reverser.renderer import render_tool_schema
                    render_tool_schema(dict(row), self.console)
                else:
                    self.console.print(f"[yellow]Tool '{arg}' not found.[/yellow]")

        elif cmd == "/history":
            if not self.history:
                self.console.print("[dim]No history yet.[/dim]")
            else:
                for i, entry in enumerate(self.history[-10:], 1):
                    self.console.print(f"  {i}. [dim]{entry}[/dim]")

        elif cmd == "/clear":
            self.console.clear()
            self._print_banner()

        else:
            self.console.print(f"[yellow]Unknown command: {cmd}. Type /help.[/yellow]")

        return False

    def _execute_request(self, request: str) -> None:
        """Run the orchestrator on a natural language request."""
        self.history.append(request)
        self.console.print(Rule(style="dim"))

        step_buffer: list = []

        def on_step(step_type: str, content: str) -> None:
            if step_type == "thought" and content.strip():
                self.console.print(f"[dim italic]💭 {content.strip()[:200]}[/dim italic]")
            elif step_type == "tool_call":
                # Extract just the tool name for clean display
                tool_name = content.split("(")[0].strip()
                self.console.print(f"[cyan]🔧 {tool_name}[/cyan]")
            elif step_type == "tool_result":
                try:
                    import json
                    data = json.loads(content)
                    result = data.get("result") or data.get("found") or data
                    self.console.print(f"[green]  ↳ {str(result)[:200]}[/green]")
                except Exception:
                    self.console.print(f"[green]  ↳ {content[:200]}[/green]")

        with self.console.status("[bold cyan]Thinking...[/bold cyan]"):
            try:
                result = self.orchestrator.run(request, on_step=on_step)
            except Exception as exc:
                self.console.print(
                    f"[bold red]Error:[/bold red] {type(exc).__name__}: {exc}"
                )
                return

        self.console.print(Rule(style="dim"))
        self.console.print(
            Panel(result, title="[bold green]Result[/bold green]", border_style="green")
        )

    def run(self) -> None:
        """Start the interactive REPL loop."""
        self._print_banner()

        while True:
            try:
                line = Prompt.ask("\n[bold cyan]>[/bold cyan]").strip()
            except (EOFError, KeyboardInterrupt):
                self.console.print("\n[dim]Interrupted.[/dim]")
                break

            if not line:
                continue

            if line.startswith("/"):
                should_exit = self._handle_command(line)
                if should_exit and line.lower() in ("/exit", "/quit"):
                    break
            else:
                self._execute_request(line)

        self.db.close()


def start_repl(
    db_path: str,
    model: str = "claude-opus-4-5",
    no_color: bool = False,
) -> None:
    """Launch the interactive REPL.

    Args:
        db_path: Path to the SQLite database.
        model: Claude model ID.
        no_color: Disable rich colors.
    """
    repl = REPL(db_path, model=model, no_color=no_color)
    repl.run()
