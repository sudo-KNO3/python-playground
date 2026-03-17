"""Tool definitions for the orchestrator and sub-agents."""

from typing import Any, Dict, List


# ── Orchestrator tools ──────────────────────────────────────────────────────

ORCHESTRATOR_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "search_tools",
        "description": (
            "Search the function database for tools relevant to the user's request. "
            "Returns a list of matching tool names and descriptions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (default 10)",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_tool_schema",
        "description": (
            "Get the full MCP tool schema and details for a specific function "
            "by its exact name. Use this before calling a tool to understand "
            "what parameters it requires."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tool_name": {
                    "type": "string",
                    "description": "The exact function name or qualified name",
                }
            },
            "required": ["tool_name"],
        },
    },
    {
        "name": "call_tool",
        "description": (
            "Execute a discovered function with the given arguments. "
            "Use get_tool_schema first to know what arguments are needed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tool_name": {
                    "type": "string",
                    "description": "The exact function name to call",
                },
                "arguments": {
                    "type": "object",
                    "description": "Keyword arguments to pass to the function",
                },
            },
            "required": ["tool_name", "arguments"],
        },
    },
    {
        "name": "spawn_subagent",
        "description": (
            "Spawn a specialized sub-agent to handle a specific sub-task. "
            "Use this for complex multi-step tasks that require independent planning. "
            "Available sub-agents: 'search' (finds tools), 'executor' (calls tools), "
            "'planner' (decomposes complex tasks into steps)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_type": {
                    "type": "string",
                    "enum": ["search", "executor", "planner"],
                    "description": "Type of sub-agent to spawn",
                },
                "task": {
                    "type": "string",
                    "description": "The specific task for the sub-agent to complete",
                },
                "context": {
                    "type": "string",
                    "description": "Additional context (e.g. tool schemas, previous results)",
                },
            },
            "required": ["agent_type", "task"],
        },
    },
]


# ── Planner sub-agent tools ─────────────────────────────────────────────────

PLANNER_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "create_plan",
        "description": "Output a structured execution plan as a list of steps.",
        "input_schema": {
            "type": "object",
            "properties": {
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "step": {"type": "integer"},
                            "action": {"type": "string"},
                            "tool": {"type": "string"},
                            "params_template": {"type": "object"},
                        },
                    },
                    "description": "Ordered list of execution steps",
                }
            },
            "required": ["steps"],
        },
    }
]


# ── Search sub-agent tools ───────────────────────────────────────────────────

SEARCH_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "return_tools",
        "description": "Return the list of matching tools found.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tools": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "List of tool dicts",
                }
            },
            "required": ["tools"],
        },
    }
]
