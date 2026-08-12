"""
Vortex Memory Architecture — inspired by Cognee + Mem0

   Vortex Memory
   ├── Working Memory  (immediate context, 20-50 turn window)
   ├── Episodic Memory (events, traces, execution history)
   ├── Semantic Memory (facts, knowledge, vector+graph)
   ├── Procedural Memory (skills, bug patterns, tool chains)
   ├── User Memory (preferences, recurring intents)
   ├── Agent Memory (per-agent learnings)
   └── Knowledge Graph (entity linking, temporal)

Flow:
  interaction → extract facts/events/lessons → classify memory → store vector+graph → link entities → retrieve → inject into Orchestrator
"""
from __future__ import annotations
import json
import time
from collections import deque, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

def _now():
    return datetime.now().isoformat()

@dataclass
class MemoryItem:
    text: str
    kind: str
    meta: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.7
    created_at: str = field(default_factory=_now)
    id: str = ""

# ── Working Memory — immediate context, token-bounded ──
class WorkingMemory:
    """Short-term scratchpad, like LLM working memory."""
    def __init__(self, max_items=40):
        self.max_items = max_items
        self.items: deque = deque(maxlen=max_items)
        self.focus: Optional[str] = None

    def add(self, text: str, kind: str = "turn", meta: dict = None):
        self.items.append(MemoryItem(text=text[:1000], kind=kind, meta=meta or {}))

    def set_focus(self, goal: str):
        self.focus = goal

    def get_context(self, last_n=12) -> List[MemoryItem]:
        return list(self.items)[-last_n:]

    def get_window_text(self, last_n=12) -> str:
        ctx = self.get_context(last_n)
        return "\n".join(f"[{c.kind}] {c.text[:200]}" for c in ctx)

    def clear(self):
        self.items.clear()

    def stats(self):
        return {"count": len(self.items), "focus": self.focus}

# ── Episodic Memory — events, what happened ──
class EpisodicMemory:
    """Long-term episodic: stores tool calls, council decisions, eval outcomes."""
    def __init__(self, conn=None):
        self.conn = conn
        self._buffer: List[MemoryItem] = []

    def set_conn(self, conn):
        self.conn = conn

    def remember_event(self, text: str, kind: str = "event", meta: dict = None) -> int:
        meta = meta or {}
        item = MemoryItem(text=text, kind=kind, meta=meta)
        self._buffer.append(item)
        if self.conn:
            cur = self.conn.execute(
                "INSERT INTO events (kind, detail, created_at) VALUES (?,?,?)",
                (kind, json.dumps({"text": text, "meta": meta}), _now())
            )
            self.conn.commit()
            return cur.lastrowid
        return len(self._buffer)

    def recall_events(self, query: str = "", kind: str = None, limit: int = 20) -> List[Dict[str, Any]]:
        if not self.conn:
            # in-memory fallback
            q = query.lower()
            filtered = [b for b in self._buffer if q in b.text.lower()][:limit]
            return [{"text": f.text, "kind": f.kind, "meta": f.meta, "created_at": f.created_at} for f in filtered]
        sql = "SELECT kind, detail, created_at FROM events ORDER BY id DESC LIMIT ?"
        params = [limit*2]
        if kind:
            sql = "SELECT kind, detail, created_at FROM events WHERE kind=? ORDER BY id DESC LIMIT ?"
            params = [kind, limit*2]
        rows = self.conn.execute(sql, params).fetchall()
        out = []
        query_low = query.lower()
        for k, detail, created in rows:
            try:
                data = json.loads(detail or "{}")
                txt = data.get("text", detail)
            except:
                txt = detail
            if not query or query_low in str(txt).lower() or query_low in k.lower():
                out.append({"kind": k, "text": txt, "detail": detail, "created_at": created})
        return out[:limit]

    def timeline(self, limit=30) -> List[Dict[str, Any]]:
        return self.recall_events(limit=limit)

# ── Semantic Memory — facts, knowledge ──
class SemanticMemory:
    """Fact store + vector sync."""
    def __init__(self, conn=None, vector_store=None, kg=None):
        self.conn = conn
        self.vector = vector_store
        self.kg = kg

    def set_deps(self, conn, vector_store, kg):
        self.conn = conn
        self.vector = vector_store
        self.kg = kg
        if self.conn:
            self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS semantic_facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fact TEXT NOT NULL,
                kind TEXT,
                confidence REAL,
                source TEXT,
                entities TEXT,
                created_at TEXT
            );
            """)
            self.conn.commit()

    def remember_fact(self, fact: str, kind: str = "general", confidence: float = 0.75, source: str = "", entities: List[str] = None):
        entities = entities or []
        if self.conn:
            self.conn.execute(
                "INSERT INTO semantic_facts (fact, kind, confidence, source, entities, created_at) VALUES (?,?,?,?,?,?)",
                (fact, kind, confidence, source, json.dumps(entities), _now())
            )
            self.conn.commit()
        if self.vector:
            try:
                self.vector.remember(fact, {"kind": kind, "type": "semantic", "confidence": confidence})
            except:
                pass
        if self.kg:
            try:
                self.kg.remember(fact, kind=kind, meta={"type": "semantic", "source": source})
            except:
                pass

    def recall_facts(self, query: str, n: int = 5) -> List[Dict[str, Any]]:
        out = []
        # vector first
        if self.vector:
            try:
                vh = self.vector.recall(query, n=n)
                for h in vh:
                    out.append({"fact": h, "source": "vector", "confidence": 0.7})
            except:
                pass
        # sql fallback with LIKE
        if self.conn:
            rows = self.conn.execute("SELECT fact, kind, confidence, source FROM semantic_facts ORDER BY id DESC LIMIT 200").fetchall()
            q = query.lower()
            scored = []
            for fact, kind, conf, src in rows:
                score = 0
                if q in fact.lower():
                    score = 2 + conf
                elif any(t in fact.lower() for t in q.split()):
                    score = 1 + conf*0.5
                if score>0:
                    scored.append((score, {"fact": fact, "kind": kind, "confidence": conf, "source": src}))
            scored.sort(key=lambda x: -x[0])
            out.extend([x[1] for x in scored[:n]])
        # graph recall
        if self.kg:
            try:
                gh = self.kg.recall(query, n=n)
                for h in gh:
                    if h.get("kind") == "entity":
                        node = h.get("node", {})
                        out.append({"fact": f"{node.get('label')} ({node.get('type')})", "source": "graph", "confidence": node.get("confidence", 0.5)})
            except:
                pass
        # dedup by fact text
        seen = set()
        deduped = []
        for o in out:
            ft = o["fact"][:200]
            if ft not in seen:
                seen.add(ft)
                deduped.append(o)
        return deduped[:n]

# ── Procedural Memory — skills, how to do ──
class ProceduralMemory:
    """How-to, tool chains, bug fixes that worked."""
    def __init__(self, conn=None, skills_lib=None, bugs_lib=None):
        self.conn = conn
        self.skills = skills_lib
        self.bugs = bugs_lib
        self._procedures: Dict[str, Dict[str, Any]] = {}

    def set_deps(self, conn, skills_lib, bugs_lib):
        self.conn = conn
        self.skills = skills_lib
        self.bugs = bugs_lib
        if self.conn:
            self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS procedural_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                steps TEXT,
                success_count INTEGER DEFAULT 0,
                fail_count INTEGER DEFAULT 0,
                created_at TEXT
            );
            """)
            self.conn.commit()

    def save_procedure(self, name: str, description: str, steps: List[Any], meta: dict = None):
        meta = meta or {}
        self._procedures[name] = {"description": description, "steps": steps, "meta": meta, "created_at": _now()}
        if self.skills:
            try:
                self.skills.save(name, description, steps)
            except:
                pass
        if self.conn:
            self.conn.execute(
                "INSERT INTO procedural_memory (name, description, steps, created_at) VALUES (?,?,?,?)",
                (name, description, json.dumps(steps), _now())
            )
            self.conn.commit()

    def get_procedure(self, name: str) -> Optional[Dict[str, Any]]:
        if name in self._procedures:
            return self._procedures[name]
        if self.skills:
            return self.skills.get(name)
        if self.conn:
            row = self.conn.execute("SELECT name, description, steps FROM procedural_memory WHERE name=? ORDER BY id DESC LIMIT 1", (name,)).fetchone()
            if row:
                return {"name": row[0], "description": row[1], "steps": json.loads(row[2] or "[]")}
        return None

    def list_procedures(self) -> List[Dict[str, Any]]:
        if self.skills:
            return self.skills.list()
        return [{"name": k, **v} for k, v in self._procedures.items()]

    def record_success(self, name: str, success: bool):
        if self.conn:
            col = "success_count" if success else "fail_count"
            self.conn.execute(f"UPDATE procedural_memory SET {col}={col}+1 WHERE name=?", (name,))
            self.conn.commit()

# ── User Memory — preferences, recurring patterns ──
class UserMemory:
    """User-specific long-term memory, Mem0 user/session split idea."""
    def __init__(self, conn=None):
        self.conn = conn
        self._prefs: Dict[str, Any] = {}

    def set_conn(self, conn):
        self.conn = conn
        if self.conn:
            self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS user_memory (
                key TEXT PRIMARY KEY,
                value TEXT,
                confidence REAL,
                updated_at TEXT
            );
            """)
            self.conn.commit()

    def remember_user(self, key: str, value: Any, confidence: float = 0.8):
        self._prefs[key] = value
        if self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO user_memory (key, value, confidence, updated_at) VALUES (?,?,?,?)",
                (key, json.dumps(value), confidence, _now())
            )
            self.conn.commit()

    def recall_user(self, key: str = None) -> Any:
        if key:
            if key in self._prefs:
                return self._prefs[key]
            if self.conn:
                row = self.conn.execute("SELECT value FROM user_memory WHERE key=?", (key,)).fetchone()
                if row:
                    return json.loads(row[0])
            return None
        # all
        if self.conn:
            rows = self.conn.execute("SELECT key, value FROM user_memory").fetchall()
            return {r[0]: json.loads(r[1]) for r in rows}
        return dict(self._prefs)

    def learn_from_interaction(self, task: str, success: bool):
        # simple heuristic: record preferred tools / intents
        low = task.lower()
        if "translate" in low:
            self.remember_user("prefers_translation", True, 0.6)
        if "code" in low or "run" in low:
            self.remember_user("prefers_code", True, 0.6)

# ── Agent Memory — per-agent learnings ──
class AgentMemory:
    """Each bot's private memory + shared cross-agent knowledge (Cognee idea)."""
    def __init__(self, conn=None):
        self.conn = conn
        self.agent_memories: Dict[str, List[MemoryItem]] = defaultdict(list)

    def set_conn(self, conn):
        self.conn = conn
        if self.conn:
            self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS agent_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent TEXT NOT NULL,
                content TEXT NOT NULL,
                kind TEXT,
                confidence REAL,
                created_at TEXT
            );
            """)
            self.conn.commit()

    def remember(self, agent: str, content: str, kind: str = "learning", confidence: float = 0.7):
        item = MemoryItem(text=content, kind=kind, confidence=confidence)
        self.agent_memories[agent].append(item)
        self.agent_memories[agent] = self.agent_memories[agent][-100:]
        if self.conn:
            self.conn.execute(
                "INSERT INTO agent_memory (agent, content, kind, confidence, created_at) VALUES (?,?,?,?,?)",
                (agent, content, kind, confidence, _now())
            )
            self.conn.commit()

    def recall(self, agent: str, query: str = "", limit: int = 5) -> List[Dict[str, Any]]:
        mem = self.agent_memories.get(agent, [])
        if query:
            q = query.lower()
            filtered = [m for m in mem if q in m.text.lower()]
            mem = filtered
        out = [{"agent": agent, "text": m.text, "kind": m.kind, "confidence": m.confidence, "created_at": m.created_at} for m in mem[-limit:]]

        if self.conn:
            rows = self.conn.execute("SELECT content, kind, confidence, created_at FROM agent_memory WHERE agent=? ORDER BY id DESC LIMIT ?", (agent, limit)).fetchall()
            for content, kind, conf, created in rows:
                if content not in [o["text"] for o in out]:
                    out.append({"agent": agent, "text": content, "kind": kind, "confidence": conf, "created_at": created})
        return out[:limit]

    def cross_agent_share(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Cross-agent knowledge sharing — Cognee concept."""
        all_items = []
        for agent, mems in self.agent_memories.items():
            for m in mems:
                if query.lower() in m.text.lower():
                    all_items.append({"agent": agent, "text": m.text, "kind": m.kind, "confidence": m.confidence})
        if self.conn:
            rows = self.conn.execute("SELECT agent, content, kind, confidence FROM agent_memory ORDER BY id DESC LIMIT 100").fetchall()
            for agent, content, kind, conf in rows:
                if query.lower() in content.lower():
                    all_items.append({"agent": agent, "text": content, "kind": kind, "confidence": conf})
        # rank by confidence
        all_items.sort(key=lambda x: -x.get("confidence", 0))
        return all_items[:limit]
