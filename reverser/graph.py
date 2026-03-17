"""Builds call and dependency graphs from parsed file information."""

from typing import Dict, List, Optional

from reverser.models import CallEdge, FileInfo, FunctionInfo


class NetworkBuilder:
    """Builds a call + dependency graph from a list of parsed files."""

    def __init__(self) -> None:
        """Initialize an empty network builder."""
        self._functions: Dict[str, FunctionInfo] = {}
        self._files: List[FileInfo] = []

    def add_file(self, file_info: FileInfo) -> None:
        """Register a parsed file and index its functions.

        Args:
            file_info: Parsed file information.
        """
        self._files.append(file_info)
        for func in file_info.functions:
            self._functions[func.qualified_name] = func
            # Also index by simple name for resolution
            if func.name not in self._functions:
                self._functions[func.name] = func

    def resolve_calls(self) -> List[CallEdge]:
        """Resolve call edges between all registered functions.

        Matches callee names to known qualified names where possible.

        Returns:
            List of CallEdge objects representing the call graph.
        """
        edges: List[CallEdge] = []
        for file_info in self._files:
            for func in file_info.functions:
                for callee_name in func.calls_made:
                    edges.append(
                        CallEdge(
                            caller_qualified_name=func.qualified_name,
                            callee_name=callee_name,
                        )
                    )
        return edges

    def get_qualified_name(self, simple_name: str) -> Optional[str]:
        """Look up the qualified name for a simple function name.

        Args:
            simple_name: The unqualified function name.

        Returns:
            Qualified name if found, else None.
        """
        func = self._functions.get(simple_name)
        return func.qualified_name if func else None

    @property
    def all_functions(self) -> List[FunctionInfo]:
        """Return all unique functions registered in the network."""
        seen = set()
        result: List[FunctionInfo] = []
        for func in self._functions.values():
            if func.qualified_name not in seen:
                seen.add(func.qualified_name)
                result.append(func)
        return result
