"""Parser package: extracts function/call/import information from source files."""

from pathlib import Path
from typing import Optional

from reverser.models import FileInfo
from reverser.scanner import detect_language


def parse_file(
    path: Path,
    language: Optional[str] = None,
    llm: Optional[object] = None,
) -> FileInfo:
    """Parse a source file and return structured FileInfo.

    Uses the AST-based parser for Python files and the AI-based parser
    for all other languages (requires an LLM instance).

    Args:
        path: Path to the source file.
        language: Language override; detected automatically if omitted.
        llm: LLM instance for non-Python files. If None, non-Python files
             return a FileInfo with no functions extracted.

    Returns:
        FileInfo with extracted functions, imports, and metadata.
    """
    lang = language or detect_language(path)

    if lang == "Python":
        from reverser.parser.python_parser import parse_python_file

        return parse_python_file(path)

    if llm is not None:
        from reverser.parser.ai_parser import parse_with_ai

        return parse_with_ai(path, lang, llm)  # type: ignore[arg-type]

    return FileInfo(path=str(path), language=lang)
