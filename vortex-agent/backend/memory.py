"""
Vortex Memory — upgraded to real Vortex memory (Cognee + Mem0 inspired)

Architecture:
  Vortex Memory
  ├── Working Memory   (immediate context)
  ├── Episodic Memory  (events, timelines)
  ├── Semantic Memory  (facts + vector+graph)
  ├── Procedural Memory (skills, bug patterns)
  ├── User Memory      (preferences, recurring intents)
  ├── Agent Memory     (per-agent + cross-agent knowledge)
  └── Knowledge Graph  (entity linking, temporal, self-improve)

Keeps backward compatibility with existing Memory API:
- save_message, get_history, clear_history
- log_event, get_events
- set_kv, get_kv
- stats, save_trace, get_traces, save_lesson, etc.

New API (Cognee-style):
- remember(text, kind, meta) → extract + store vector+graph+classify
- recall(query, n, kind) → hybrid vector+graph retrieval
- forget(label/id) + improve()
- Full subsystem access via .working, .episodic, .semantic, etc.
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from paths import vortex_home
from memory_types import (
    WorkingMemory,
    EpisodicMemory,
    SemanticMemory,
    ProceduralMemory,
    UserMemory,
    AgentMemory,
)

# lazy import to avoid circular during tests if vector missing
def _load_vector():
    try:
        from vector_memory import VectorMemory
        return VectorMemory()
    except Exception:
        return None

def _load_kg(conn, vector):
    try:
        from knowledge_graph import KnowledgeGraph
        return KnowledgeGraph(conn, vector_store=vector)
    except Exception as e:
        print(f"[memory] kg not available: {e}")
        return None

class Memory:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or (vortex_home() / "memory.db")
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init()

        # new subsystems
        vector = _load_vector()
        self.vector = vector
        kg = _load_kg(self.conn, vector)
        self.graph = kg
        self.kg = kg  # alias

        # memory layers
        self.working = WorkingMemory(max_items=50)
        self.episodic = EpisodicMemory(self.conn)
        self.semantic = SemanticMemory(self.conn, vector, kg)
        self.procedural = ProceduralMemory(self.conn)
        self.user = UserMemory(self.conn)
        self.agent_memory = AgentMemory(self.conn)

        # init extra tables via layers
        self.semantic.set_deps(self.conn, vector, kg)
        self.procedural.set_deps(self.conn, None, None)
        self.user.set_conn(self.conn)
        self.agent_memory.set_conn(self.conn)
        self.episodic.set_conn(self.conn)

        # Hermes-inspired: cross-session recall (Tier 2) + guaranteed context (Tier 1)
        self.sessions = None
        self.profile = None
        try:
            from sessions import SessionStore
            self.sessions = SessionStore(self.conn)
        except Exception as e:
            print(f"[memory] sessions not loaded: {e}")
        try:
            from profile_memory import ProfileMemory
            self.profile = ProfileMemory()
        except Exception as e:
            print(f"[memory] profile memory not loaded: {e}")

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

    # ── new Cognee-style API ──
    def remember(self, text: str, kind: str = "fact", meta: dict = None, source: str = "user") -> Dict[str, Any]:
        """
        Full flow:
         interaction → extract facts/events/lessons → classify memory → store vector+graph → link entities
        """
        meta = meta or {}
        text = text.strip()
        if not text:
            return {}

        # working memory
        self.working.add(text, kind=kind, meta=meta)

        # classify
        kind_l = kind.lower()
        result: Dict[str, Any] = {"text": text, "kind": kind}

        # route to appropriate stores
        if kind_l in ("fact", "knowledge", "semantic", "general"):
            self.semantic.remember_fact(text, kind=kind, source=source, confidence=meta.get("confidence", 0.75))
            result["stored_in"] = "semantic"
        elif kind_l in ("event", "episodic", "task", "trace"):
            self.episodic.remember_event(text, kind=kind, meta=meta)
            result["stored_in"] = "episodic"
        elif kind_l in ("procedure", "skill", "howto", "procedural"):
            # save as procedural
            self.procedural.save_procedure(name=meta.get("name", f"proc_{int(datetime.now().timestamp())}"),
                                           description=text,
                                           steps=meta.get("steps", []),
                                           meta=meta)
            result["stored_in"] = "procedural"
        elif kind_l in ("user", "preference"):
            self.user.remember_user(meta.get("key", "preference"), text)
            result["stored_in"] = "user"
        elif kind_l.startswith("agent"):
            agent = meta.get("agent", "chief")
            self.agent_memory.remember(agent, text, kind=kind)
            result["stored_in"] = "agent"
        else:
            # default: semantic + episodic + kg
            self.semantic.remember_fact(text, kind=kind, source=source)
            self.episodic.remember_event(text, kind=kind, meta=meta)

        # knowledge graph (always)
        if self.kg:
            try:
                kg_res = self.kg.remember(text, kind=kind, meta=meta, source=source)
                result["kg"] = kg_res
            except Exception as e:
                result["kg_error"] = str(e)[:200]

        # vector already handled via semantic

        # user learning
        try:
            self.user.learn_from_interaction(text, success=True)
        except:
            pass

        return result

    def recall(self, query: str, n: int = 5, kind: str = None, hybrid: bool = True) -> List[Dict[str, Any]]:
        """
        Hybrid retrieval: vector + graph + semantic + episodic + agent cross-share
        Returns unified list injected into orchestrator.
        """
        results: List[Dict[str, Any]] = []

        # semantic
        try:
            sem = self.semantic.recall_facts(query, n=n)
            for s in sem:
                results.append({"type": "semantic", **s})
        except Exception as e:
            pass

        # knowledge graph
        if self.kg and hybrid:
            try:
                gh = self.kg.recall(query, n=n, kind=kind)
                for h in gh:
                    results.append({"type": "graph", "data": h})
            except Exception:
                pass

        # episodic
        try:
            eps = self.episodic.recall_events(query=query, limit=n)
            for ep in eps:
                results.append({"type": "episodic", "text": ep.get("text"), "kind": ep.get("kind")})
        except Exception:
            pass

        # agent cross-share
        try:
            cross = self.agent_memory.cross_agent_share(query, limit=3)
            for c in cross:
                results.append({"type": "agent_memory", **c})
        except Exception:
            pass

        # working context
        try:
            wctx = self.working.get_context(last_n=5)
            # inject if overlap
            for item in wctx:
                if query.lower() in item.text.lower():
                    results.append({"type": "working", "text": item.text, "kind": item.kind})
        except Exception:
            pass

        # rank / deduplicate
        # simple: semantic/graph high, episodic medium, working low
        def rank_key(r):
            order = {"semantic": 3, "graph": 3, "agent_memory": 2.5, "episodic": 2, "working": 1}
            return order.get(r.get("type"), 0) + r.get("confidence", 0)

        results.sort(key=rank_key, reverse=True)

        # if no results, fallback to vector raw
        if not results and self.vector:
            try:
                vh = self.vector.recall(query, n=n)
                results = [{"type": "vector", "text": v} for v in vh]
            except:
                pass

        return results[:n*2]

    def forget(self, label: str = None, decay: bool = True) -> Dict[str, Any]:
        out = {}
        if self.kg:
            try:
                out["kg"] = self.kg.forget(label=label, decay=decay)
            except:
                pass
        # also decay vector? no delete, just forget semantic fact confidence lowering?
        return out

    def improve(self) -> Dict[str, Any]:
        """Run graph improve + prune."""
        out = {}
        if self.kg:
            try:
                out["kg"] = self.kg.improve()
            except Exception as e:
                out["kg_error"] = str(e)
        # could consolidate lessons here too
        return out

    def full_context_for_orchestrator(self, goal: str, n_memories: int = 8) -> Dict[str, Any]:
        """Retrieve relevant memories injected into orchestration state."""
        rec = self.recall(goal, n=n_memories, hybrid=True)
        work = self.working.get_window_text(last_n=10)
        user_prefs = self.user.recall_user()
        agent_shared = self.agent_memory.cross_agent_share(goal, limit=3)

        return {
            "goal": goal,
            "working_context": work,
            "relevant_memories": rec,
            "user_preferences": user_prefs,
            "agent_shared_knowledge": agent_shared,
            "graph_stats": self.kg.stats() if self.kg else {},
            "timestamp": datetime.now().isoformat(),
        }

    # ── chat history ──
    def save_message(self, role: str, content: str, meta: dict = None):
        self.conn.execute(
            "INSERT INTO messages (role, content, meta, created_at) VALUES (?,?,?,?)",
            (role, content, json.dumps(meta or {}), datetime.now().isoformat()),
        )
        self.conn.commit()
        # also push to working memory
        self.working.add(f"{role}: {content}", kind="chat", meta=meta)

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
        self.working.clear()

    # ── event log ──
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

    # ── kv ──
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
        base = {
            "messages": msgs,
            "tool_calls": tools,
            "first_message": first,
            "traces": traces,
            "lessons": lessons,
            "generation": gen,
        }
        # extended stats
        try:
            base["working"] = self.working.stats()
            base["graph"] = self.kg.stats() if self.kg else {}
            base["semantic_count"] = self.conn.execute("SELECT COUNT(*) FROM semantic_facts").fetchone()[0]
        except Exception:
            pass
        return base

    # ── traces ──
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
        # episodic + graph tracking
        try:
            self.episodic.remember_event(f"trace:{row.get('task','')[:80]} [{row.get('status')}]", kind="trace", meta=row)
        except:
            pass
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

    # ── lessons ──
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
        # semantic fact too
        try:
            self.semantic.remember_fact(f"lesson: {lesson['trigger']} → {lesson['action']}", kind="lesson")
        except:
            pass
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

    # ── generations / evals ──
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
