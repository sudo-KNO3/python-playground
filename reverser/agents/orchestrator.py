"""Multi-agent orchestrator: natural language → function call execution."""

import json
import os
from typing import Any, Callable, Dict, Iterator, List, Optional

from reverser.agents.tools import (
    ORCHESTRATOR_TOOLS,
    PLANNER_TOOLS,
    SEARCH_TOOLS,
)
from reverser.db import Database

ORCHESTRATOR_SYSTEM = """\
You are an intelligent software orchestrator that translates natural language \
requests into direct function calls on engineering and design software.

You have access to a database of discovered functions from installed programs \
(AutoCAD, HYSYS, AERMOD, MODFLOW, etc.). Your job is to:

1. Understand what the user wants to accomplish
2. Search for relevant tools in the database
3. Understand each tool's parameters
4. Call the tools in the correct order with correct parameters
5. Report the results

When parameters can be inferred from the user's request, extract them directly.
For example: "design a 20x20x20m box" → call a box/solid creation function with
length=20, width=20, height=20 (converting units as needed).

Always search for tools before trying to call them. For complex multi-step tasks,
use spawn_subagent with type='planner' first to decompose the task.

Be precise with units and parameter names. When in doubt, call get_tool_schema.
"""

PLANNER_SYSTEM = """\
You are a task planner. Given a complex user request and available tools,
decompose it into ordered, atomic steps. Each step should call exactly one tool.
Be specific about parameter values that can be derived from the user's request.
"""

SEARCH_SYSTEM = """\
You are a tool search specialist. Given a natural language query and a list of
available functions, identify the most relevant tools and return them.
Rank by relevance. Consider synonyms and domain-specific terminology.
"""

EXECUTOR_SYSTEM = """\
You are a precise function executor. Given a tool name, its schema, and required
parameters (extracted from context), call the tool with exactly the right arguments.
If a parameter value is ambiguous, make a reasonable assumption and note it.
"""

MAX_ITERATIONS = 20


class Orchestrator:
    """Multi-agent orchestrator using the Anthropic Claude SDK.

    Translates natural language requests into function calls against
    the function database. Uses a ReAct-style agent loop with optional
    sub-agent delegation for complex tasks.
    """

    def __init__(self, db: Database, model: str = "claude-opus-4-5") -> None:
        """Initialize the orchestrator.

        Args:
            db: Open database instance with discovered functions.
            model: Claude model ID to use.
        """
        import anthropic

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. "
                "Set it in your environment or .env file."
            )
        self.db = db
        self.model = model
        self.client = anthropic.Anthropic(api_key=api_key)

    # ── Tool handlers ────────────────────────────────────────────────────────

    def _handle_search_tools(self, query: str, limit: int = 10) -> str:
        """Handle the search_tools orchestrator tool."""
        results = self.db.search_tools(query)[:limit]
        if not results:
            # Broader fallback search
            all_funcs = self.db.get_all_functions()
            query_words = query.lower().split()
            results = [
                f for f in all_funcs
                if any(
                    w in (f.get("name") or "").lower()
                    or w in (f.get("ai_description") or "").lower()
                    or w in (f.get("qualified_name") or "").lower()
                    for w in query_words
                )
            ][:limit]

        if not results:
            return json.dumps({"found": 0, "tools": []})

        tools = [
            {
                "name": f.get("name"),
                "qualified_name": f.get("qualified_name"),
                "description": f.get("ai_description") or f.get("docstring") or "",
                "signature": f.get("signature") or "",
                "execution_method": f.get("execution_method") or "unknown",
                "has_wrapper": bool(f.get("wrapper_path")),
            }
            for f in results
        ]
        return json.dumps({"found": len(tools), "tools": tools})

    def _handle_get_tool_schema(self, tool_name: str) -> str:
        """Handle the get_tool_schema orchestrator tool."""
        # Search by name or qualified name
        funcs = self.db.get_all_functions()
        target = None
        for f in funcs:
            if f.get("name") == tool_name or f.get("qualified_name") == tool_name:
                target = f
                break
        if target is None:
            return json.dumps({"error": f"Tool '{tool_name}' not found."})

        schema_str = target.get("tool_schema") or ""
        schema = {}
        if schema_str:
            try:
                schema = json.loads(schema_str)
            except json.JSONDecodeError:
                pass

        return json.dumps({
            "name": target.get("name"),
            "qualified_name": target.get("qualified_name"),
            "signature": target.get("signature"),
            "docstring": target.get("docstring"),
            "description": target.get("ai_description"),
            "execution_method": target.get("execution_method"),
            "wrapper_path": target.get("wrapper_path"),
            "mcp_schema": schema,
        })

    def _handle_call_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> str:
        """Handle the call_tool orchestrator tool."""
        funcs = self.db.get_all_functions()
        target = None
        for f in funcs:
            if f.get("name") == tool_name or f.get("qualified_name") == tool_name:
                target = f
                break
            # Also check MCP schema name
            schema_str = f.get("tool_schema") or ""
            if schema_str:
                try:
                    schema = json.loads(schema_str)
                    if schema.get("name") == tool_name:
                        target = f
                        break
                except json.JSONDecodeError:
                    pass

        if target is None:
            return json.dumps({"error": f"Tool '{tool_name}' not found in database."})

        # Get source file info
        row = self.db.conn.execute(
            "SELECT path, language FROM files WHERE id = ?",
            (target["file_id"],),
        ).fetchone()

        file_path = row["path"] if row else ""
        language = row["language"] if row else "Unknown"

        from reverser.mcp_server import _dispatch_execution

        result = _dispatch_execution(target, file_path, language, arguments)
        return json.dumps({"result": result})

    def _handle_spawn_subagent(
        self, agent_type: str, task: str, context: str = ""
    ) -> str:
        """Spawn a specialized sub-agent and return its result."""
        if agent_type == "planner":
            return self._run_planner_agent(task, context)
        elif agent_type == "search":
            return self._run_search_agent(task, context)
        elif agent_type == "executor":
            return self._run_executor_agent(task, context)
        return json.dumps({"error": f"Unknown sub-agent type: '{agent_type}'"})

    # ── Sub-agents ───────────────────────────────────────────────────────────

    def _run_planner_agent(self, task: str, context: str) -> str:
        """Run the planner sub-agent to decompose a complex task."""
        messages = [
            {
                "role": "user",
                "content": (
                    f"Task: {task}\n\nAvailable context:\n{context}\n\n"
                    "Create a step-by-step execution plan."
                ),
            }
        ]
        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=PLANNER_SYSTEM,
            tools=PLANNER_TOOLS,
            messages=messages,
        )
        for block in response.content:
            if hasattr(block, "type") and block.type == "tool_use":
                if block.name == "create_plan":
                    return json.dumps(block.input)
        return json.dumps({"plan": response.content[0].text if response.content else ""})

    def _run_search_agent(self, task: str, context: str) -> str:
        """Run the search sub-agent to find relevant tools."""
        results = self.db.search_tools(task)[:15]
        tool_list = json.dumps([
            {"name": f.get("name"), "description": f.get("ai_description") or f.get("docstring") or ""}
            for f in results
        ])
        messages = [
            {
                "role": "user",
                "content": (
                    f"Task: {task}\n\nAvailable tools:\n{tool_list}\n\n"
                    "Return the most relevant tools for this task."
                ),
            }
        ]
        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=SEARCH_SYSTEM,
            tools=SEARCH_TOOLS,
            messages=messages,
        )
        for block in response.content:
            if hasattr(block, "type") and block.type == "tool_use":
                if block.name == "return_tools":
                    return json.dumps(block.input)
        return tool_list

    def _run_executor_agent(self, task: str, context: str) -> str:
        """Run the executor sub-agent to call a specific function."""
        # Executor calls back into the orchestrator's call_tool handler
        # by parsing the task description for tool name + parameters
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=EXECUTOR_SYSTEM,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Execute this task: {task}\n\nContext:\n{context}\n\n"
                            "Identify the tool name and parameters, then describe the call."
                        ),
                    }
                ],
            )
        except Exception as exc:
            return json.dumps({"error": f"Executor LLM call failed: {exc}"})

        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text = block.text
                break
        return json.dumps({"executor_response": text})

    # ── Main agent loop ──────────────────────────────────────────────────────

    def _handle_tool_call(
        self, tool_name: str, tool_input: Dict[str, Any]
    ) -> str:
        """Dispatch a tool call to the appropriate handler."""
        if tool_name == "search_tools":
            return self._handle_search_tools(
                tool_input.get("query", ""),
                tool_input.get("limit", 10),
            )
        elif tool_name == "get_tool_schema":
            return self._handle_get_tool_schema(tool_input.get("tool_name", ""))
        elif tool_name == "call_tool":
            return self._handle_call_tool(
                tool_input.get("tool_name", ""),
                tool_input.get("arguments", {}),
            )
        elif tool_name == "spawn_subagent":
            return self._handle_spawn_subagent(
                tool_input.get("agent_type", ""),
                tool_input.get("task", ""),
                tool_input.get("context", ""),
            )
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    def run(
        self,
        request: str,
        on_step: Optional[Callable[[str, str], None]] = None,
    ) -> str:
        """Execute a natural language request against the function database.

        Runs a ReAct agent loop: the orchestrator thinks, searches for tools,
        calls them, and iterates until the task is complete or the iteration
        limit is reached.

        Args:
            request: Natural language user request.
            on_step: Optional callback called with (step_type, content) at
                     each agent step. Useful for streaming output to the REPL.

        Returns:
            Final text response from the orchestrator.
        """
        import anthropic

        messages: List[Dict[str, Any]] = [
            {"role": "user", "content": request}
        ]

        stats = self.db.get_stats()
        system = (
            ORCHESTRATOR_SYSTEM
            + f"\n\nDatabase stats: {stats['functions']} functions from "
            f"{stats['files']} files. {stats['actions']} marked as actions."
        )

        for iteration in range(MAX_ITERATIONS):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system,
                tools=ORCHESTRATOR_TOOLS,
                messages=messages,
            )

            # Collect text output
            text_parts = []
            tool_calls = []
            for block in response.content:
                if hasattr(block, "text") and block.text:
                    text_parts.append(block.text)
                    if on_step:
                        on_step("thought", block.text)
                elif hasattr(block, "type") and block.type == "tool_use":
                    tool_calls.append(block)

            # If no tool calls, we're done
            if response.stop_reason == "end_turn" or not tool_calls:
                return " ".join(text_parts) or "(Task complete — no text output)"

            # Execute tool calls and collect results
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for tc in tool_calls:
                if on_step:
                    on_step(
                        "tool_call",
                        f"{tc.name}({json.dumps(tc.input, indent=2)})",
                    )
                result = self._handle_tool_call(tc.name, tc.input)
                if on_step:
                    on_step("tool_result", result[:500])
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tc.id,
                        "content": result,
                    }
                )

            messages.append({"role": "user", "content": tool_results})

        return "(Max iterations reached. Partial results may have been executed.)"

    def run_stream(self, request: str) -> Iterator[str]:
        """Yield agent step output as it happens.

        Yields formatted strings suitable for display in the REPL.

        Args:
            request: Natural language user request.

        Yields:
            Formatted step strings.
        """
        steps = []

        def collect(step_type: str, content: str) -> None:
            if step_type == "thought":
                steps.append(f"💭 {content}")
            elif step_type == "tool_call":
                steps.append(f"🔧 Calling: {content[:200]}")
            elif step_type == "tool_result":
                steps.append(f"✓ Result: {content[:200]}")
            # Yield the step immediately
            yield_queue.append(steps[-1])

        yield_queue: List[str] = []

        # We can't truly stream with current architecture, so we batch
        import threading

        result_holder: List[str] = []

        def run_in_thread() -> None:
            result = self.run(request, on_step=collect)
            result_holder.append(result)

        thread = threading.Thread(target=run_in_thread)
        thread.start()

        while thread.is_alive() or yield_queue:
            while yield_queue:
                yield yield_queue.pop(0)
            import time
            time.sleep(0.05)

        thread.join()
        if result_holder:
            yield f"\n✅ {result_holder[0]}"
