"""Vortex Agent — SQLite memory layer. Persists across restarts."""
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

BASE = Path.home() / ".vortex"
BASE.mkdir(parents=True, exist_ok=True)


class Memory:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or (BASE / "memory.db")
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init()

    def _init(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                meta TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                detail TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS kv (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """)
        self.conn.commit()

    # ── chat history ──
    def save_message(self, role: str, content: str, meta: dict = None):
        self.conn.execute(
            "INSERT INTO messages (role, content, meta, created_at) VALUES (?,?,?,?)",
            (role, content, json.dumps(meta or {}), datetime.now().isoformat()),
        )
        self.conn.commit()

    def get_history(self, limit: int = 50) -> List[dict]:
        rows = self.conn.execute(
            "SELECT role, content, meta, created_at FROM messages ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {"role": r[0], "content": r[1], "meta": json.loads(r[2]), "created_at": r[3]}
            for r in reversed(rows)
        ]

    def clear_history(self):
        self.conn.execute("DELETE FROM messages")
        self.conn.commit()

    # ── event log (tool calls, system) ──
    def log_event(self, kind: str, detail: str):
        self.conn.execute(
            "INSERT INTO events (kind, detail, created_at) VALUES (?,?,?)",
            (kind, detail, datetime.now().isoformat()),
        )
        self.conn.commit()

    def get_events(self, limit: int = 50) -> List[dict]:
        rows = self.conn.execute(
            "SELECT kind, detail, created_at FROM events ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [{"kind": r[0], "detail": r[1], "created_at": r[2]} for r in reversed(rows)]

    # ── key/value (e.g. last stego text) ──
    def set_kv(self, key: str, value: str):
        self.conn.execute(
            "INSERT OR REPLACE INTO kv (key, value) VALUES (?,?)", (key, value))
        self.conn.commit()

    def get_kv(self, key: str) -> Optional[str]:
        row = self.conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    # ── stats ──
    def stats(self) -> dict:
        msgs = self.conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        tools = self.conn.execute(
            "SELECT COUNT(*) FROM events WHERE kind='tool_call'").fetchone()[0]
        first = self.conn.execute(
            "SELECT MIN(created_at) FROM messages").fetchone()[0]
        return {"messages": msgs, "tool_calls": tools, "first_message": first}
