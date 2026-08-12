"""Vortex Agent — SQLite memory layer. Persists across restarts."""
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from paths import vortex_home


class Memory:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or (vortex_home() / "memory.db")
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
            CREATE TABLE IF NOT EXISTS traces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                generation INTEGER NOT NULL,
                task TEXT NOT NULL,
                bot TEXT,
                route TEXT,
                tool TEXT,
                status TEXT,
                score REAL,
                latency_ms INTEGER,
                detail TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                trigger TEXT NOT NULL,
                action TEXT NOT NULL,
                confidence REAL,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                active INTEGER DEFAULT 1,
                meta TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS generations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id INTEGER,
                score REAL,
                mutations TEXT,
                notes TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS eval_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                generation INTEGER,
                name TEXT,
                passed INTEGER,
                total INTEGER,
                score REAL,
                detail TEXT,
                created_at TEXT NOT NULL
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
        traces = self.conn.execute("SELECT COUNT(*) FROM traces").fetchone()[0]
        lessons = self.conn.execute(
            "SELECT COUNT(*) FROM lessons WHERE active=1").fetchone()[0]
        gen = self.conn.execute(
            "SELECT MAX(id) FROM generations").fetchone()[0] or 0
        return {
            "messages": msgs,
            "tool_calls": tools,
            "first_message": first,
            "traces": traces,
            "lessons": lessons,
            "generation": gen,
        }

    # ── RSI: traces ──
    def save_trace(self, row: dict) -> int:
        cur = self.conn.execute(
            """INSERT INTO traces
               (generation, task, bot, route, tool, status, score, latency_ms, detail, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                row.get("generation", 0),
                row.get("task", ""),
                row.get("bot"),
                row.get("route"),
                row.get("tool"),
                row.get("status"),
                row.get("score"),
                row.get("latency_ms"),
                json.dumps(row.get("detail") or {}),
                datetime.now().isoformat(),
            ),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_traces(self, limit: int = 50) -> List[dict]:
        rows = self.conn.execute(
            """SELECT id, generation, task, bot, route, tool, status, score,
                      latency_ms, detail, created_at
               FROM traces ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [
            {
                "id": r[0], "generation": r[1], "task": r[2], "bot": r[3],
                "route": r[4], "tool": r[5], "status": r[6], "score": r[7],
                "latency_ms": r[8], "detail": json.loads(r[9] or "{}"),
                "created_at": r[10],
            }
            for r in rows
        ]

    # ── RSI: lessons ──
    def save_lesson(self, lesson: dict) -> int:
        existing = self.conn.execute(
            "SELECT id FROM lessons WHERE kind=? AND trigger=? AND action=?",
            (lesson["kind"], lesson["trigger"], lesson["action"]),
        ).fetchone()
        if existing:
            self.conn.execute(
                "UPDATE lessons SET confidence=MAX(confidence, ?), active=1 WHERE id=?",
                (lesson.get("confidence", 0.5), existing[0]),
            )
            self.conn.commit()
            return existing[0]
        cur = self.conn.execute(
            """INSERT INTO lessons
               (kind, trigger, action, confidence, wins, losses, active, meta, created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                lesson["kind"], lesson["trigger"], lesson["action"],
                lesson.get("confidence", 0.5),
                lesson.get("wins", 0), lesson.get("losses", 0),
                1, json.dumps(lesson.get("meta") or {}),
                datetime.now().isoformat(),
            ),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_lessons(self, active_only: bool = True) -> List[dict]:
        q = "SELECT id, kind, trigger, action, confidence, wins, losses, active, meta, created_at FROM lessons"
        if active_only:
            q += " WHERE active=1"
        q += " ORDER BY confidence DESC, id DESC"
        rows = self.conn.execute(q).fetchall()
        return [
            {
                "id": r[0], "kind": r[1], "trigger": r[2], "action": r[3],
                "confidence": r[4], "wins": r[5], "losses": r[6],
                "active": bool(r[7]), "meta": json.loads(r[8] or "{}"),
                "created_at": r[9],
            }
            for r in rows
        ]

    def bump_lesson(self, lesson_id: int, win: bool):
        col = "wins" if win else "losses"
        self.conn.execute(
            f"UPDATE lessons SET {col}={col}+1 WHERE id=?", (lesson_id,))
        if not win:
            self.conn.execute(
                """UPDATE lessons SET confidence=MAX(0.05, confidence-0.15),
                   active=CASE WHEN losses>=3 AND wins=0 THEN 0 ELSE active END
                   WHERE id=?""",
                (lesson_id,),
            )
        else:
            self.conn.execute(
                "UPDATE lessons SET confidence=MIN(0.99, confidence+0.05) WHERE id=?",
                (lesson_id,),
            )
        self.conn.commit()

    def set_lessons_active(self, ids: List[int], active: bool):
        if not ids:
            return
        q = ",".join("?" * len(ids))
        self.conn.execute(
            f"UPDATE lessons SET active=? WHERE id IN ({q})",
            [1 if active else 0, *ids],
        )
        self.conn.commit()

    # ── RSI: generations / evals ──
    def save_generation(self, parent_id, score, mutations, notes="") -> int:
        cur = self.conn.execute(
            """INSERT INTO generations (parent_id, score, mutations, notes, created_at)
               VALUES (?,?,?,?,?)""",
            (parent_id, score, json.dumps(mutations or []), notes,
             datetime.now().isoformat()),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_generations(self, limit: int = 20) -> List[dict]:
        rows = self.conn.execute(
            """SELECT id, parent_id, score, mutations, notes, created_at
               FROM generations ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [
            {
                "id": r[0], "parent_id": r[1], "score": r[2],
                "mutations": json.loads(r[3] or "[]"), "notes": r[4],
                "created_at": r[5],
            }
            for r in rows
        ]

    def current_generation(self) -> int:
        row = self.conn.execute("SELECT MAX(id) FROM generations").fetchone()
        return row[0] or 0

    def save_eval(self, generation, name, passed, total, score, detail) -> int:
        cur = self.conn.execute(
            """INSERT INTO eval_runs
               (generation, name, passed, total, score, detail, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (generation, name, passed, total, score,
             json.dumps(detail or {}), datetime.now().isoformat()),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_evals(self, limit: int = 20) -> List[dict]:
        rows = self.conn.execute(
            """SELECT id, generation, name, passed, total, score, detail, created_at
               FROM eval_runs ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [
            {
                "id": r[0], "generation": r[1], "name": r[2],
                "passed": r[3], "total": r[4], "score": r[5],
                "detail": json.loads(r[6] or "{}"), "created_at": r[7],
            }
            for r in rows
        ]
