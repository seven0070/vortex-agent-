"""SQLite session store with FTS5 — Hermes hermes_state pattern."""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from vortex.constants import STATE_DB, ensure_home


class SessionDB:
    def __init__(self, path: Optional[Path] = None):
        ensure_home()
        self.path = path or STATE_DB
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init()

    def _init(self):
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT,
                status TEXT,
                role TEXT,
                parent_id TEXT,
                goal TEXT,
                result TEXT,
                error TEXT,
                meta TEXT,
                created_at TEXT,
                updated_at TEXT,
                finished_at TEXT
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT,
                meta TEXT,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                idx INTEGER,
                thought TEXT,
                action TEXT,
                args TEXT,
                observation TEXT,
                status TEXT,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT,
                detail TEXT,
                session_id TEXT,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS kv (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                content, session_id UNINDEXED, role UNINDEXED,
                content='messages', content_rowid='id'
            );
            """
        )
        self.conn.commit()

    def new_session(
        self,
        goal: str = "",
        role: str = "agent",
        parent_id: Optional[str] = None,
        title: Optional[str] = None,
    ) -> str:
        sid = uuid.uuid4().hex[:12]
        now = datetime.now().isoformat(timespec="seconds")
        with self._lock:
            self.conn.execute(
                "INSERT INTO sessions (id,title,status,role,parent_id,goal,meta,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    sid,
                    title or (goal[:60] if goal else sid),
                    "queued",
                    role,
                    parent_id,
                    goal,
                    "{}",
                    now,
                    now,
                ),
            )
            self.conn.commit()
        return sid

    def update_session(self, sid: str, **fields):
        if not fields:
            return
        fields["updated_at"] = datetime.now().isoformat(timespec="seconds")
        cols = ", ".join(f"{k}=?" for k in fields)
        with self._lock:
            self.conn.execute(
                f"UPDATE sessions SET {cols} WHERE id=?",
                (*fields.values(), sid),
            )
            self.conn.commit()

    def get_session(self, sid: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT id,title,status,role,parent_id,goal,result,error,meta,created_at,updated_at,finished_at "
            "FROM sessions WHERE id=?",
            (sid,),
        ).fetchone()
        if not row:
            return None
        steps = self.get_steps(sid)
        return {
            "id": row[0],
            "title": row[1],
            "status": row[2],
            "role": row[3],
            "parent_id": row[4],
            "goal": row[5],
            "result": row[6] or "",
            "error": row[7] or "",
            "meta": json.loads(row[8] or "{}"),
            "created_at": row[9],
            "updated_at": row[10],
            "finished_at": row[11],
            "steps": steps,
            "step_count": len(steps),
        }

    def list_sessions(self, limit: int = 50) -> List[dict]:
        rows = self.conn.execute(
            "SELECT id,title,status,role,goal,created_at,finished_at FROM sessions "
            "ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        out = []
        for r in rows:
            sc = self.conn.execute(
                "SELECT COUNT(*) FROM steps WHERE session_id=?", (r[0],)
            ).fetchone()[0]
            out.append(
                {
                    "id": r[0],
                    "title": r[1],
                    "status": r[2],
                    "role": r[3],
                    "goal": r[4],
                    "created_at": r[5],
                    "finished_at": r[6],
                    "step_count": sc,
                }
            )
        return out

    def add_message(self, sid: str, role: str, content: str, meta: dict = None):
        now = datetime.now().isoformat(timespec="seconds")
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO messages (session_id,role,content,meta,created_at) VALUES (?,?,?,?,?)",
                (sid, role, content, json.dumps(meta or {}), now),
            )
            rowid = cur.lastrowid
            try:
                self.conn.execute(
                    "INSERT INTO messages_fts (rowid, content, session_id, role) VALUES (?,?,?,?)",
                    (rowid, content, sid, role),
                )
            except sqlite3.OperationalError:
                pass
            self.conn.commit()

    def add_step(
        self,
        sid: str,
        idx: int,
        thought: str,
        action: str,
        args: dict,
        observation: str,
        status: str,
    ):
        now = datetime.now().isoformat(timespec="seconds")
        with self._lock:
            self.conn.execute(
                "INSERT INTO steps (session_id,idx,thought,action,args,observation,status,created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    sid,
                    idx,
                    thought,
                    action,
                    json.dumps(args or {}),
                    observation,
                    status,
                    now,
                ),
            )
            self.conn.commit()

    def get_steps(self, sid: str) -> List[dict]:
        rows = self.conn.execute(
            "SELECT idx,thought,action,args,observation,status,created_at FROM steps "
            "WHERE session_id=? ORDER BY idx",
            (sid,),
        ).fetchall()
        return [
            {
                "index": r[0],
                "thought": r[1],
                "action": r[2],
                "args": json.loads(r[3] or "{}"),
                "observation": r[4],
                "status": r[5],
                "ts": r[6],
            }
            for r in rows
        ]

    def log_event(self, kind: str, detail: str, session_id: str = ""):
        with self._lock:
            self.conn.execute(
                "INSERT INTO events (kind,detail,session_id,created_at) VALUES (?,?,?,?)",
                (kind, detail, session_id, datetime.now().isoformat(timespec="seconds")),
            )
            self.conn.commit()

    def get_events(self, limit: int = 50) -> List[dict]:
        rows = self.conn.execute(
            "SELECT kind,detail,session_id,created_at FROM events ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {"kind": r[0], "detail": r[1], "session_id": r[2], "created_at": r[3]}
            for r in reversed(rows)
        ]

    def set_kv(self, key: str, value: str):
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO kv (key,value) VALUES (?,?)", (key, value)
            )
            self.conn.commit()

    def get_kv(self, key: str) -> Optional[str]:
        row = self.conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def search(self, query: str, limit: int = 10) -> List[dict]:
        try:
            rows = self.conn.execute(
                "SELECT session_id, role, snippet(messages_fts,0,'»','«','…',20) "
                "FROM messages_fts WHERE messages_fts MATCH ? LIMIT ?",
                (query, limit),
            ).fetchall()
            return [{"session_id": r[0], "role": r[1], "snippet": r[2]} for r in rows]
        except Exception:
            return []

    def stats(self) -> dict:
        msgs = self.conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        sessions = self.conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        steps = self.conn.execute("SELECT COUNT(*) FROM steps").fetchone()[0]
        return {"messages": msgs, "sessions": sessions, "steps": steps, "tool_calls": steps}
