"""File scanner and language detector for the reverser tool."""

from pathlib import Path
from typing import Iterator

LANGUAGE_MAP = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".jsx": "JavaScript",
    ".tsx": "TypeScript",
    ".go": "Go",
    ".rb": "Ruby",
    ".java": "Java",
    ".cs": "C#",
    ".cpp": "C++",
    ".cc": "C++",
    ".c": "C",
    ".h": "C",
    ".rs": "Rust",
    ".php": "PHP",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".scala": "Scala",
    ".sh": "Shell",
    ".bash": "Shell",
    ".r": "R",
    ".R": "R",
    ".lua": "Lua",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".hs": "Haskell",
    ".ml": "OCaml",
    ".clj": "Clojure",
}

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "node_modules",
    ".venv",
    "venv",
    "env",
    ".env",
    "dist",
    "build",
    ".eggs",
    "*.egg-info",
    ".tox",
    ".coverage",
    "htmlcov",
}


def detect_language(path: Path) -> str:
    """Detect the programming language of a file by its extension.

    Args:
        path: Path to the source file.

    Returns:
        Human-readable language name, or 'Unknown' if unrecognized.
    """
    return LANGUAGE_MAP.get(path.suffix.lower(), "Unknown")


def scan_directory(root: Path) -> Iterator[Path]:
    """Recursively yield source files from a directory.

    Skips hidden directories, virtual environments, build artifacts,
    and binary/non-source files.

    Args:
        root: Root directory to scan.

    Yields:
        Path objects for each source file found.
    """
    root = root.resolve()
    for item in root.rglob("*"):
        if item.is_file():
            # Skip files inside excluded directories
            if any(part in SKIP_DIRS for part in item.parts):
                continue
            # Skip hidden files
            if item.name.startswith("."):
                continue
            # Only yield files with a known language extension
            if detect_language(item) != "Unknown":
                yield item
