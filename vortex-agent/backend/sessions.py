"""
Vortex sessions — cross-session recall (Hermes Tier-2 equivalent).

The gap this closes: Vortex had seven memory layers but no notion of a *session*.
Every turn landed in one undifferentiated pile, so "what did we discuss last Tuesday
about the retry bug?" was unanswerable. Hermes solves this with SQLite FTS5 keyword
search over full conversation history; this is that, on stdlib sqlite3.

FTS5 is standard in CPython's bundled SQLite, but we degrade to LIKE scanning if a
build lacks it — the feature stays available, just slower.
"""
from __future__ import annotations

import sqlite3
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional


def _fts5_available(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS _fts_probe USING fts5(x)")
        conn.execute("DROP TABLE IF EXISTS _fts_probe")
        return True
    except Exception:
        return False


class SessionStore:
    """Durable conversation sessions with full-text recall across all of them."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.fts = _fts5_available(conn)
        self._init()
        self.current_id: Optional[str] = None
        self._turn_count = 0

    def _init(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT DEFAULT '',
                started_at TEXT,
                ended_at TEXT,
                turns INTEGER DEFAULT 0,
                summary TEXT DEFAULT '',
                meta TEXT DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS session_turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT,
                created_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_turns_session ON session_turns(session_id);
        """)
        if self.fts:
            try:
                self.conn.executescript("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS session_fts
                    USING fts5(content, session_id UNINDEXED, role UNINDEXED,
                               turn_id UNINDEXED, tokenize='porter');
                """)
            except Exception:
                self.fts = False
        self.conn.commit()

    # ── lifecycle ──
    def start(self, title: str = "", meta: Optional[dict] = None) -> str:
        sid = f"s_{uuid.uuid4().hex[:12]}"
        import json
        self.conn.execute(
            "INSERT INTO sessions (id,title,started_at,turns,meta) VALUES (?,?,?,0,?)",
            (sid, title or "session", datetime.now().isoformat(), json.dumps(meta or {})),
        )
        self.conn.commit()
        self.current_id = sid
        self._turn_count = 0
        return sid

    def ensure_session(self) -> str:
        if not self.current_id:
            self.start()
        return self.current_id  # type: ignore[return-value]

    def record(self, role: str, content: str, session_id: Optional[str] = None) -> Optional[int]:
        """Append a turn. Content is indexed for cross-session search."""
        if not content or not content.strip():
            return None
        sid = session_id or self.ensure_session()
        cur = self.conn.execute(
            "INSERT INTO session_turns (session_id,role,content,created_at) VALUES (?,?,?,?)",
            (sid, role, content[:8000], datetime.now().isoformat()),
        )
        turn_id = cur.lastrowid
        if self.fts:
            try:
                self.conn.execute(
                    "INSERT INTO session_fts (content,session_id,role,turn_id) VALUES (?,?,?,?)",
                    (content[:8000], sid, role, str(turn_id)),
                )
            except Exception:
                pass
        self.conn.execute("UPDATE sessions SET turns = turns + 1 WHERE id=?", (sid,))
        self.conn.commit()
        self._turn_count += 1
        return turn_id

    def end(self, summary: str = "", session_id: Optional[str] = None) -> None:
        sid = session_id or self.current_id
        if not sid:
            return
        self.conn.execute("UPDATE sessions SET ended_at=?, summary=? WHERE id=?",
                          (datetime.now().isoformat(), summary[:2000], sid))
        self.conn.commit()
        if sid == self.current_id:
            self.current_id = None

    # ── recall ──
    def search(self, query: str, limit: int = 8,
               exclude_current: bool = False) -> List[Dict[str, Any]]:
        """
        Keyword search across every past conversation.

        This is the "what did we say about X" capability Vortex was missing.
        """
        if not query or not query.strip():
            return []
        rows: List[Dict[str, Any]] = []

        if self.fts:
            try:
                sql = ("SELECT content, session_id, role, turn_id, rank FROM session_fts "
                       "WHERE session_fts MATCH ? ")
                params: List[Any] = [self._fts_query(query)]
                if exclude_current and self.current_id:
                    sql += "AND session_id != ? "
                    params.append(self.current_id)
                sql += "ORDER BY rank LIMIT ?"
                params.append(limit)
                for r in self.conn.execute(sql, params).fetchall():
                    rows.append({"content": r[0], "session_id": r[1], "role": r[2],
                                 "turn_id": r[3], "match": "fts"})
                if rows:
                    return rows
            except Exception:
                pass  # fall through to LIKE

        # portable fallback
        terms = [t for t in query.lower().split() if len(t) > 2][:5]
        if not terms:
            return []
        sql = "SELECT content, session_id, role, id FROM session_turns WHERE ("
        sql += " OR ".join("LOWER(content) LIKE ?" for _ in terms) + ")"
        params = [f"%{t}%" for t in terms]
        if exclude_current and self.current_id:
            sql += " AND session_id != ?"
            params.append(self.current_id)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        for r in self.conn.execute(sql, params).fetchall():
            rows.append({"content": r[0], "session_id": r[1], "role": r[2],
                         "turn_id": r[3], "match": "like"})
        return rows

    @staticmethod
    def _fts_query(query: str) -> str:
        """Sanitise user text into a safe FTS5 OR-query (avoids syntax errors on punctuation)."""
        terms = [t for t in (w.strip(".,!?;:'\"()[]{}") for w in query.split())
                 if len(t) > 2 and t.isalnum()]
        if not terms:
            terms = [w for w in query.split() if w.isalnum()][:3]
        return " OR ".join(f'"{t}"' for t in terms[:8]) or '"x"'

    def list_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT id,title,started_at,ended_at,turns,summary FROM sessions "
            "ORDER BY started_at DESC LIMIT ?", (limit,)).fetchall()
        return [{"id": r[0], "title": r[1], "started_at": r[2], "ended_at": r[3],
                 "turns": r[4], "summary": r[5]} for r in rows]

    def get_session(self, session_id: str, limit: int = 200) -> Dict[str, Any]:
        head = self.conn.execute(
            "SELECT id,title,started_at,ended_at,turns,summary FROM sessions WHERE id=?",
            (session_id,)).fetchone()
        if not head:
            return {}
        turns = self.conn.execute(
            "SELECT role,content,created_at FROM session_turns WHERE session_id=? "
            "ORDER BY id LIMIT ?", (session_id, limit)).fetchall()
        return {
            "id": head[0], "title": head[1], "started_at": head[2], "ended_at": head[3],
            "turns": head[4], "summary": head[5],
            "messages": [{"role": t[0], "content": t[1], "created_at": t[2]} for t in turns],
        }

    def stats(self) -> Dict[str, Any]:
        s = self.conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        t = self.conn.execute("SELECT COUNT(*) FROM session_turns").fetchone()[0]
        return {"sessions": s, "turns": t, "search_backend": "fts5" if self.fts else "like",
                "current_session": self.current_id, "turns_this_session": self._turn_count}
