"""Data models for the reverser tool."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FunctionInfo:
    """Represents a function or method found in source code."""

    name: str
    qualified_name: str
    signature: str
    docstring: Optional[str]
    source: Optional[str]
    start_line: int
    end_line: int
    is_public: bool
    class_name: Optional[str]
    calls_made: List[str] = field(default_factory=list)
    imports_used: List[str] = field(default_factory=list)


@dataclass
class FileInfo:
    """Represents a parsed source file."""

    path: str
    language: str
    functions: List[FunctionInfo] = field(default_factory=list)
    imports: List["ImportEdge"] = field(default_factory=list)


@dataclass
class CallEdge:
    """Represents a call relationship between two functions."""

    caller_qualified_name: str
    callee_name: str


@dataclass
class ImportEdge:
    """Represents an import statement in a file."""

    file_path: str
    module: str
    alias: Optional[str]
    imported_names: List[str] = field(default_factory=list)


@dataclass
class ToolSchema:
    """MCP-compatible tool schema for a function."""

    name: str
    description: str
    input_schema: Dict[str, Any]
    function_id: int
