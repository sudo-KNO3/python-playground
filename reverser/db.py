"""SQLite database operations for storing the code network."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


DDL = """
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    language TEXT NOT NULL,
    last_scanned TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS functions (
    id INTEGER PRIMARY KEY,
    file_id INTEGER REFERENCES files(id),
    name TEXT NOT NULL,
    qualified_name TEXT NOT NULL UNIQUE,
    signature TEXT,
    docstring TEXT,
    source TEXT,
    start_line INTEGER,
    end_line INTEGER,
    is_public INTEGER NOT NULL DEFAULT 1,
    is_action INTEGER NOT NULL DEFAULT 0,
    action_confidence REAL,
    ai_description TEXT,
    tool_schema TEXT
);

CREATE TABLE IF NOT EXISTS calls (
    id INTEGER PRIMARY KEY,
    caller_id INTEGER REFERENCES functions(id),
    callee_name TEXT NOT NULL,
    callee_id INTEGER REFERENCES functions(id)
);

CREATE TABLE IF NOT EXISTS imports (
    id INTEGER PRIMARY KEY,
    file_id INTEGER REFERENCES files(id),
    module TEXT NOT NULL,
    alias TEXT,
    imported_names TEXT
);
"""


class Database:
    """Manages the SQLite database for the code network."""

    def __init__(self, db_path: str) -> None:
        """Initialize the database connection."""
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.initialize()

    def initialize(self) -> None:
        """Create tables if they do not exist."""
        self.conn.executescript(DDL)
        self.conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        self.conn.close()

    def upsert_file(self, path: str, language: str) -> int:
        """Insert or update a file record and return its id."""
        now = datetime.utcnow().isoformat()
        self.conn.execute(
            """
            INSERT INTO files (path, language, last_scanned)
            VALUES (?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET language=excluded.language,
                                            last_scanned=excluded.last_scanned
            """,
            (path, language, now),
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT id FROM files WHERE path = ?", (path,)
        ).fetchone()
        return int(row["id"])

    def upsert_function(
        self,
        file_id: int,
        name: str,
        qualified_name: str,
        signature: Optional[str],
        docstring: Optional[str],
        source: Optional[str],
        start_line: int,
        end_line: int,
        is_public: bool,
    ) -> int:
        """Insert or update a function record and return its id."""
        self.conn.execute(
            """
            INSERT INTO functions
                (file_id, name, qualified_name, signature, docstring, source,
                 start_line, end_line, is_public)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(qualified_name) DO UPDATE SET
                file_id=excluded.file_id,
                name=excluded.name,
                signature=excluded.signature,
                docstring=excluded.docstring,
                source=excluded.source,
                start_line=excluded.start_line,
                end_line=excluded.end_line,
                is_public=excluded.is_public
            """,
            (
                file_id,
                name,
                qualified_name,
                signature,
                docstring,
                source,
                start_line,
                end_line,
                1 if is_public else 0,
            ),
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT id FROM functions WHERE qualified_name = ?",
            (qualified_name,),
        ).fetchone()
        return int(row["id"])

    def insert_call(
        self, caller_id: int, callee_name: str, callee_id: Optional[int]
    ) -> None:
        """Insert a call edge."""
        self.conn.execute(
            "INSERT INTO calls (caller_id, callee_name, callee_id) VALUES (?, ?, ?)",
            (caller_id, callee_name, callee_id),
        )
        self.conn.commit()

    def insert_import(
        self,
        file_id: int,
        module: str,
        alias: Optional[str],
        imported_names: List[str],
    ) -> None:
        """Insert an import record."""
        self.conn.execute(
            "INSERT INTO imports (file_id, module, alias, imported_names) VALUES (?, ?, ?, ?)",
            (file_id, module, alias, json.dumps(imported_names)),
        )
        self.conn.commit()

    def get_function_id(self, qualified_name: str) -> Optional[int]:
        """Return the id of a function by qualified name, or None."""
        row = self.conn.execute(
            "SELECT id FROM functions WHERE qualified_name = ?",
            (qualified_name,),
        ).fetchone()
        return int(row["id"]) if row else None

    def get_all_functions(self) -> List[Dict[str, Any]]:
        """Return all function records as dicts."""
        rows = self.conn.execute("SELECT * FROM functions").fetchall()
        return [dict(r) for r in rows]

    def get_action_functions(self) -> List[Dict[str, Any]]:
        """Return all functions marked as actions."""
        rows = self.conn.execute(
            "SELECT * FROM functions WHERE is_action = 1"
        ).fetchall()
        return [dict(r) for r in rows]

    def search_tools(self, query: str) -> List[Dict[str, Any]]:
        """Search for action functions by name or description (LIKE)."""
        like = f"%{query}%"
        rows = self.conn.execute(
            """
            SELECT * FROM functions
            WHERE is_action = 1
              AND (name LIKE ? OR ai_description LIKE ? OR qualified_name LIKE ?)
            """,
            (like, like, like),
        ).fetchall()
        return [dict(r) for r in rows]

    def update_tool_schema(
        self,
        function_id: int,
        schema_json: str,
        description: str,
        confidence: float,
        is_action: bool = True,
    ) -> None:
        """Update tool schema, description and action classification for a function."""
        self.conn.execute(
            """
            UPDATE functions
            SET tool_schema = ?, ai_description = ?, action_confidence = ?, is_action = ?
            WHERE id = ?
            """,
            (
                schema_json,
                description,
                confidence,
                1 if is_action else 0,
                function_id,
            ),
        )
        self.conn.commit()

    def get_function_calls(self, function_id: int) -> List[str]:
        """Return names of functions called by the given function."""
        rows = self.conn.execute(
            "SELECT callee_name FROM calls WHERE caller_id = ?",
            (function_id,),
        ).fetchall()
        return [r["callee_name"] for r in rows]

    def get_function_callers(self, function_id: int) -> List[str]:
        """Return qualified names of functions that call the given function."""
        rows = self.conn.execute(
            """
            SELECT f.qualified_name FROM calls c
            JOIN functions f ON f.id = c.caller_id
            WHERE c.callee_id = ?
            """,
            (function_id,),
        ).fetchall()
        return [r["qualified_name"] for r in rows]

    def get_stats(self) -> Dict[str, int]:
        """Return summary statistics about the database contents."""
        files = self.conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        functions = self.conn.execute(
            "SELECT COUNT(*) FROM functions"
        ).fetchone()[0]
        actions = self.conn.execute(
            "SELECT COUNT(*) FROM functions WHERE is_action = 1"
        ).fetchone()[0]
        calls = self.conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
        imports = self.conn.execute("SELECT COUNT(*) FROM imports").fetchone()[0]
        return {
            "files": files,
            "functions": functions,
            "actions": actions,
            "calls": calls,
            "imports": imports,
        }
