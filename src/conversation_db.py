"""
Conversation database – stores chat history in a local SQLite database.
Supports multiple named sessions and full message retrieval.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import config


class ConversationDB:
    """
    Lightweight SQLite wrapper for persistent conversation history.

    Schema
    ------
    sessions(id, name, created_at, updated_at)
    messages(id, session_id, role, content, timestamp)
    """

    def __init__(self, db_path: Path = config.DB_PATH) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _create_tables(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT    NOT NULL,
                created_at TEXT    NOT NULL,
                updated_at TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                role       TEXT    NOT NULL CHECK(role IN ('user','assistant','system')),
                content    TEXT    NOT NULL,
                timestamp  TEXT    NOT NULL
            );
            """
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def create_session(self, name: Optional[str] = None) -> int:
        """Create a new conversation session and return its ID."""
        now = datetime.now().isoformat()
        name = name or f"Chat {now[:16]}"
        cur = self._conn.execute(
            "INSERT INTO sessions (name, created_at, updated_at) VALUES (?, ?, ?)",
            (name, now, now),
        )
        self._conn.commit()
        return cur.lastrowid

    def rename_session(self, session_id: int, new_name: str) -> None:
        """Rename an existing session."""
        self._conn.execute(
            "UPDATE sessions SET name = ?, updated_at = ? WHERE id = ?",
            (new_name, datetime.now().isoformat(), session_id),
        )
        self._conn.commit()

    def delete_session(self, session_id: int) -> None:
        """Delete a session and all its messages."""
        self._conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        self._conn.commit()

    def list_sessions(self) -> List[dict]:
        """Return all sessions ordered by most-recently updated."""
        cur = self._conn.execute(
            "SELECT id, name, created_at, updated_at FROM sessions ORDER BY updated_at DESC"
        )
        return [dict(row) for row in cur.fetchall()]

    def get_session(self, session_id: int) -> Optional[dict]:
        """Return a single session record or None."""
        cur = self._conn.execute(
            "SELECT id, name, created_at, updated_at FROM sessions WHERE id = ?",
            (session_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # Message management
    # ------------------------------------------------------------------

    def add_message(self, session_id: int, role: str, content: str) -> int:
        """Append a message to a session and return its ID."""
        now = datetime.now().isoformat()
        cur = self._conn.execute(
            "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, role, content, now),
        )
        self._conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (now, session_id),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_messages(
        self,
        session_id: int,
        limit: Optional[int] = None,
    ) -> List[dict]:
        """
        Return messages for a session in chronological order.
        If *limit* is given, return only the most recent *limit* messages.
        """
        if limit:
            cur = self._conn.execute(
                """
                SELECT id, session_id, role, content, timestamp
                FROM messages
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, limit),
            )
            return list(reversed([dict(r) for r in cur.fetchall()]))
        else:
            cur = self._conn.execute(
                """
                SELECT id, session_id, role, content, timestamp
                FROM messages
                WHERE session_id = ?
                ORDER BY id ASC
                """,
                (session_id,),
            )
            return [dict(r) for r in cur.fetchall()]

    def delete_message(self, message_id: int) -> None:
        """Delete a single message by ID."""
        self._conn.execute("DELETE FROM messages WHERE id = ?", (message_id,))
        self._conn.commit()

    def clear_session_messages(self, session_id: int) -> None:
        """Remove all messages from a session (keeps the session record)."""
        self._conn.execute(
            "DELETE FROM messages WHERE session_id = ?", (session_id,)
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
