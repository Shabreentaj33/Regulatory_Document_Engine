"""
Persistent Memory — SQLite backend
────────────────────────────────────
Stores two things that survive restarts:

1. Document registry  — every PDF ever uploaded with its metadata
                        (summary, sections, risks, chunk count)

2. Conversation history — every question + answer + citations

Tables
------
documents  : one row per uploaded PDF
chat_history : one row per message (user or assistant)
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class PersistentMemory:
    """
    SQLite-backed persistent store for documents and chat history.
    The database file lives at  data/memory.db  (auto-created).
    """

    def __init__(self, db_path: str | Path = "data/memory.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        logger.info("PersistentMemory ready at %s", self.db_path.resolve())

    # ── Init ──────────────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS documents (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename    TEXT    NOT NULL UNIQUE,
                    uploaded_at TEXT    NOT NULL,
                    summary     TEXT,
                    sections    TEXT,   -- JSON
                    risks       TEXT,   -- JSON
                    chunks_stored INTEGER DEFAULT 0,
                    char_count  INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS chat_history (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id  TEXT    NOT NULL DEFAULT 'default',
                    role        TEXT    NOT NULL,   -- 'user' | 'assistant'
                    content     TEXT    NOT NULL,
                    citations   TEXT,               -- JSON list
                    sources     TEXT,               -- JSON list
                    created_at  TEXT    NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_chat_session
                    ON chat_history(session_id, created_at);
            """)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    # ── Documents ─────────────────────────────────────────────────────────────

    def save_document(
        self,
        filename: str,
        summary: str,
        sections: dict,
        risks: list,
        chunks_stored: int,
        char_count: int,
    ) -> None:
        """Insert or replace a document record."""
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO documents
                    (filename, uploaded_at, summary, sections, risks, chunks_stored, char_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(filename) DO UPDATE SET
                    uploaded_at   = excluded.uploaded_at,
                    summary       = excluded.summary,
                    sections      = excluded.sections,
                    risks         = excluded.risks,
                    chunks_stored = excluded.chunks_stored,
                    char_count    = excluded.char_count
            """, (
                filename,
                datetime.now().isoformat(timespec="seconds"),
                summary,
                json.dumps(sections),
                json.dumps(risks),
                chunks_stored,
                char_count,
            ))
        logger.info("Saved document record: %s", filename)

    def load_all_documents(self) -> list[dict[str, Any]]:
        """Return all document records as a list of dicts."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM documents ORDER BY uploaded_at DESC"
            ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["sections"] = json.loads(d["sections"] or "{}")
            d["risks"]    = json.loads(d["risks"]    or "[]")
            result.append(d)
        logger.info("Loaded %d document records from memory", len(result))
        return result

    def document_exists(self, filename: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM documents WHERE filename = ?", (filename,)
            ).fetchone()
        return row is not None

    def delete_document(self, filename: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM documents WHERE filename = ?", (filename,))
        logger.info("Deleted document record: %s", filename)

    def get_document_names(self) -> list[str]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT filename FROM documents ORDER BY uploaded_at DESC"
            ).fetchall()
        return [r["filename"] for r in rows]

    # ── Chat history ──────────────────────────────────────────────────────────

    def save_message(
        self,
        role: str,
        content: str,
        citations: list[str] | None = None,
        sources: list[str] | None = None,
        session_id: str = "default",
    ) -> None:
        """Append a single message to chat history."""
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO chat_history
                    (session_id, role, content, citations, sources, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                role,
                content,
                json.dumps(citations or []),
                json.dumps(sources or []),
                datetime.now().isoformat(timespec="seconds"),
            ))

    def load_chat_history(
        self,
        session_id: str = "default",
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """Return the last *limit* messages for a session."""
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM chat_history
                WHERE session_id = ?
                ORDER BY created_at ASC
                LIMIT ?
            """, (session_id, limit)).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["citations"] = json.loads(d["citations"] or "[]")
            d["sources"]   = json.loads(d["sources"]   or "[]")
            result.append(d)
        return result

    def clear_chat_history(self, session_id: str = "default") -> None:
        with self._conn() as conn:
            conn.execute(
                "DELETE FROM chat_history WHERE session_id = ?", (session_id,)
            )
        logger.info("Cleared chat history for session: %s", session_id)

    def clear_all_chat_history(self) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM chat_history")
        logger.info("Cleared chat history for all sessions")

    def get_all_sessions(self) -> list[str]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT session_id FROM chat_history ORDER BY session_id"
            ).fetchall()
        return [r["session_id"] for r in rows]

    # ── Stats ─────────────────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        with self._conn() as conn:
            doc_count  = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            msg_count  = conn.execute("SELECT COUNT(*) FROM chat_history").fetchone()[0]
            last_upload = conn.execute(
                "SELECT MAX(uploaded_at) FROM documents"
            ).fetchone()[0]
        return {
            "documents_stored": doc_count,
            "messages_stored":  msg_count,
            "last_upload":      last_upload or "never",
            "db_path":          str(self.db_path.resolve()),
        }
