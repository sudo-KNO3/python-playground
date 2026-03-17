"""AST-based Python source file parser."""

import ast
import textwrap
from pathlib import Path
from typing import List, Optional, Tuple

from reverser.models import FileInfo, FunctionInfo, ImportEdge


def _get_source_segment(source: str, node: ast.AST) -> Optional[str]:
    """Extract the source code for an AST node."""
    try:
        return ast.get_source_segment(source, node)
    except Exception:
        return None


def _build_signature(node: ast.FunctionDef) -> str:
    """Build a readable signature string from a function AST node."""
    args = node.args
    parts: List[str] = []

    # Positional-only args (Python 3.8+)
    for arg in args.posonlyargs:
        annotation = (
            ast.unparse(arg.annotation) if arg.annotation else None
        )
        parts.append(f"{arg.arg}: {annotation}" if annotation else arg.arg)
    if args.posonlyargs:
        parts.append("/")

    # Regular args
    defaults_offset = len(args.args) - len(args.defaults)
    for i, arg in enumerate(args.args):
        annotation = (
            ast.unparse(arg.annotation) if arg.annotation else None
        )
        part = f"{arg.arg}: {annotation}" if annotation else arg.arg
        default_idx = i - defaults_offset
        if default_idx >= 0:
            part += f" = {ast.unparse(args.defaults[default_idx])}"
        parts.append(part)

    if args.vararg:
        parts.append(f"*{args.vararg.arg}")
    elif args.kwonlyargs:
        parts.append("*")

    for i, arg in enumerate(args.kwonlyargs):
        annotation = (
            ast.unparse(arg.annotation) if arg.annotation else None
        )
        part = f"{arg.arg}: {annotation}" if annotation else arg.arg
        if args.kw_defaults[i] is not None:
            part += f" = {ast.unparse(args.kw_defaults[i])}"  # type: ignore[arg-type]
        parts.append(part)

    if args.kwarg:
        parts.append(f"**{args.kwarg.arg}")

    ret = (
        f" -> {ast.unparse(node.returns)}" if node.returns else ""
    )
    return f"({', '.join(parts)}){ret}"


def _extract_calls(node: ast.FunctionDef) -> List[str]:
    """Extract names of functions/methods called within a function."""
    calls: List[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            if isinstance(child.func, ast.Name):
                calls.append(child.func.id)
            elif isinstance(child.func, ast.Attribute):
                calls.append(child.func.attr)
    return list(set(calls))


def _extract_imports(tree: ast.Module) -> List[ImportEdge]:
    """Extract import statements from a module AST."""
    edges: List[ImportEdge] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                edges.append(
                    ImportEdge(
                        file_path="",
                        module=alias.name,
                        alias=alias.asname,
                        imported_names=[],
                    )
                )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = [alias.name for alias in node.names]
            edges.append(
                ImportEdge(
                    file_path="",
                    module=module,
                    alias=None,
                    imported_names=names,
                )
            )
    return edges


class _FunctionVisitor(ast.NodeVisitor):
    """AST visitor that collects FunctionInfo from a Python module."""

    def __init__(self, source: str, module_name: str) -> None:
        self.source = source
        self.module_name = module_name
        self.functions: List[FunctionInfo] = []
        self._class_stack: List[str] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Track class context for method qualified names."""
        self._class_stack.append(node.name)
        self.generic_visit(node)
        self._class_stack.pop()

    def _visit_func(
        self, node: "ast.FunctionDef"
    ) -> None:
        """Process a function or async function definition."""
        class_name = self._class_stack[-1] if self._class_stack else None
        if class_name:
            qualified_name = f"{self.module_name}.{class_name}.{node.name}"
        else:
            qualified_name = f"{self.module_name}.{node.name}"

        docstring: Optional[str] = ast.get_docstring(node)
        source_seg = _get_source_segment(self.source, node)
        signature = _build_signature(node)
        calls = _extract_calls(node)
        is_public = not node.name.startswith("_")

        func = FunctionInfo(
            name=node.name,
            qualified_name=qualified_name,
            signature=signature,
            docstring=docstring,
            source=source_seg,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            is_public=is_public,
            class_name=class_name,
            calls_made=calls,
        )
        self.functions.append(func)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_func(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(
        self, node: ast.AsyncFunctionDef
    ) -> None:
        self._visit_func(node)  # type: ignore[arg-type]
        self.generic_visit(node)


def _module_name_from_path(path: Path) -> str:
    """Derive a dotted module name from a file path.

    Uses the stem (filename without extension) as the module name.
    For nested packages, returns a dotted path relative to the nearest
    ancestor directory that is not a Python package (no __init__.py).
    """
    parts: List[str] = [path.stem]
    current = path.parent
    while (current / "__init__.py").exists():
        parts.insert(0, current.name)
        current = current.parent
    return ".".join(parts)


def parse_python_file(path: Path) -> FileInfo:
    """Parse a Python source file using the AST.

    Args:
        path: Path to the .py file.

    Returns:
        FileInfo with all extracted functions and imports.
    """
    source = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return FileInfo(path=str(path), language="Python")

    module_name = _module_name_from_path(path)
    visitor = _FunctionVisitor(source, module_name)
    visitor.visit(tree)

    imports = _extract_imports(tree)
    for imp in imports:
        imp.file_path = str(path)

    return FileInfo(
        path=str(path),
        language="Python",
        functions=visitor.functions,
        imports=imports,
    )
