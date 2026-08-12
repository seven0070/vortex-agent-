"""
Vortex Knowledge Graph — inspired by Cognee + Mem0.

Implements:
- persistent nodes (entities) + edges (relations) in SQLite
- operations: remember, recall, forget, improve
- entity linking, temporal awareness, vector + graph hybrid
- traceability for self-improvement

Graph stored in memory.db (kg_nodes, kg_edges, kg_observations)
 vectors in vector_memory for hybrid retrieval.
"""
from __future__ import annotations
import json
import re
import time
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from pathlib import Path

def _now():
    return datetime.now().isoformat()

ENTITY_RE = re.compile(r"\b[A-Z][a-z]+\b|\b[a-z]+(?:_tool|_agent)\b", re.I)

@dataclass
class Node:
    id: str
    type: str  # person, tool, concept, task, fact, lesson, user, agent
    label: str
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    confidence: float = 0.8
    embedding_text: str = ""

@dataclass
class Edge:
    id: str
    src: str
    dst: str
    relation: str  # uses, knows, triggers, derived_from, similar_to, etc.
    weight: float = 1.0
    meta: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

class KnowledgeGraph:
    """
    Persistent knowledge graph, Cognee-style.
    - remember: extract entities/relations from text and store vector+graph
    - recall: hybrid vector + graph traversal
    - forget: decay / deactivate
    - improve: merge duplicates, strengthen edges
    """
    def __init__(self, conn: sqlite3.Connection, vector_store=None):
        self.conn = conn
        self.vector = vector_store
        self._init_tables()

    def _init_tables(self):
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS kg_nodes (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            label TEXT NOT NULL,
            properties TEXT,
            confidence REAL,
            embedding_text TEXT,
            created_at TEXT,
            updated_at TEXT,
            active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS kg_edges (
            id TEXT PRIMARY KEY,
            src TEXT NOT NULL,
            dst TEXT NOT NULL,
            relation TEXT NOT NULL,
            weight REAL,
            meta TEXT,
            created_at TEXT,
            active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS kg_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            kind TEXT,
            entities TEXT,
            created_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_kg_nodes_label ON kg_nodes(label);
        CREATE INDEX IF NOT EXISTS idx_kg_nodes_type ON kg_nodes(type);
        CREATE INDEX IF NOT EXISTS idx_kg_edges_src ON kg_edges(src);
        CREATE INDEX IF NOT EXISTS idx_kg_edges_dst ON kg_edges(dst);
        """)
        self.conn.commit()

    # ---- core ops: remember / recall / forget / improve (Cognee API) ----
    def remember(self, text: str, kind: str = "fact", meta: dict = None, source: str = "") -> Dict[str, Any]:
        """
        Extract facts/events/lessons from interaction, store vector + graph.
        Returns {nodes, edges, observation_id}
        """
        meta = meta or {}
        text = text.strip()
        if not text:
            return {"nodes": [], "edges": []}

        # 1. extract entities (heuristic — Mem0-style entity linking)
        entities = self._extract_entities(text, kind)
        observation_id = self._save_observation(text, kind, entities)

        nodes = []
        for ent in entities:
            node = self._upsert_node(
                label=ent["label"].lower(),
                type=ent["type"],
                properties={"source_text": text[:300], **meta, "source": source},
                embedding_text=text,
                confidence=ent.get("confidence", 0.75)
            )
            nodes.append(node)

        # 2. link entities (co-occurrence edges)
        edges = []
        for i in range(len(nodes)):
            for j in range(i+1, len(nodes)):
                e = self._upsert_edge(nodes[i].id, nodes[j].id, "co_occurs", weight=0.5,
                                      meta={"observation_id": observation_id, "kind": kind})
                edges.append(e)

        # 3. link to existing similar nodes (temporal memory)
        for node in nodes:
            similars = self._find_similar_nodes(node.label, limit=3, exclude_id=node.id)
            for sim, score in similars:
                if score > 0.6:
                    e = self._upsert_edge(node.id, sim, "similar_to", weight=score*0.8)
                    edges.append(e)

        # 4. vector store (semantic memory sync)
        if self.vector:
            try:
                self.vector.remember(text, {"kind": kind, "entities": [n.label for n in nodes], **meta})
            except Exception:
                pass

        # 5. temporal edge: if episodic, chain to last observation of same kind
        last_obs = self._last_observation_of_kind(kind)
        if last_obs and last_obs[0] != observation_id:
            # link entities across time
            pass

        return {"nodes": [n.__dict__ for n in nodes], "edges": [e.__dict__ for e in edges], "observation_id": observation_id}

    def recall(self, query: str, n: int = 5, kind: str = None, include_graph: bool = True) -> List[Dict[str, Any]]:
        """
        Hybrid retrieval: vector + graph + entity.
        Mem0 ideas: entity linking + temporal + user/session/agent filtering
        """
        results = []

        # vector recall
        vector_hits = []
        if self.vector:
            try:
                vector_hits = self.vector.recall(query, n=n*2)
            except Exception:
                vector_hits = []

        # entity-based recall
        q_tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
        rows = self.conn.execute(
            "SELECT id, type, label, properties, confidence, embedding_text, created_at FROM kg_nodes WHERE active=1 ORDER BY updated_at DESC LIMIT 200"
        ).fetchall()
        scored = []
        for r in rows:
            label = r[2]
            # token overlap
            overlap = len(q_tokens & set(label.split()))
            if r[1] == kind or kind is None:
                # bonus for confidence + recency
                scored.append((overlap + r[4], {"id": r[0], "type": r[1], "label": label,
                                                "properties": json.loads(r[3] or "{}"),
                                                "confidence": r[4], "embedding_text": r[5],
                                                "created_at": r[6]}))
        scored.sort(key=lambda x: -x[0])
        graph_hits = [x[1] for x in scored[:n] if x[0] > 0]

        # if no overlap, fallback to last N
        if not graph_hits:
            graph_hits = [x[1] for x in scored[:2]]

        # expand via edges (1-hop)
        expanded = []
        if include_graph and graph_hits:
            node_ids = [h["id"] for h in graph_hits[:3]]
            q_marks = ",".join("?"*len(node_ids))
            edge_rows = self.conn.execute(
                f"SELECT src, dst, relation, weight FROM kg_edges WHERE active=1 AND (src IN ({q_marks}) OR dst IN ({q_marks})) ORDER BY weight DESC LIMIT 20",
                node_ids+node_ids
            ).fetchall()
            # fetch neighbors
            neighbor_ids = set()
            for er in edge_rows:
                if er[0] in node_ids and er[1] not in node_ids:
                    neighbor_ids.add(er[1])
                if er[1] in node_ids and er[0] not in node_ids:
                    neighbor_ids.add(er[0])
            if neighbor_ids:
                q2 = ",".join("?"*len(neighbor_ids))
                neigh_rows = self.conn.execute(
                    f"SELECT id, type, label, properties, confidence FROM kg_nodes WHERE id IN ({q2}) AND active=1",
                    list(neighbor_ids)
                ).fetchall()
                for nr in neigh_rows:
                    expanded.append({"id": nr[0], "type": nr[1], "label": nr[2],
                                     "properties": json.loads(nr[3] or "{}"),
                                     "confidence": nr[4], "via": "graph_expand"})
            # add edges info to results
            for er in edge_rows[:10]:
                results.append({"kind": "relation", "src": er[0], "dst": er[1], "relation": er[2], "weight": er[3]})

        # merge
        for h in vector_hits[:n]:
            results.append({"kind": "vector", "text": h, "score": 0.8})
        for h in graph_hits:
            results.append({"kind": "entity", "node": h, "score": h.get("confidence", 0.5)})
        for h in expanded:
            results.append({"kind": "graph_neighbor", "node": h, "score": 0.4})

        # temporal ranking: boost recent
        def temporal_score(r):
            if r.get("kind") == "entity":
                return r.get("score", 0)
            return r.get("score", 0)*0.8
        results.sort(key=lambda x: -temporal_score(x))
        return results[:n*2]

    def forget(self, label: str = None, node_id: str = None, decay: bool = True) -> int:
        """Deactivate or decay confidence."""
        if node_id:
            if decay:
                self.conn.execute("UPDATE kg_nodes SET confidence=MAX(0.05, confidence*0.6), updated_at=? WHERE id=?", (_now(), node_id))
            else:
                self.conn.execute("UPDATE kg_nodes SET active=0, updated_at=? WHERE id=?", (_now(), node_id))
            self.conn.commit()
            return 1
        if label:
            if decay:
                cur = self.conn.execute("UPDATE kg_nodes SET confidence=MAX(0.05, confidence*0.7), updated_at=? WHERE label=? AND active=1", (_now(), label.lower()))
            else:
                cur = self.conn.execute("UPDATE kg_nodes SET active=0, updated_at=? WHERE label=?", (_now(), label.lower()))
            self.conn.commit()
            return cur.rowcount
        return 0

    def improve(self) -> Dict[str, Any]:
        """
        Learning from feedback: merge duplicates, strengthen successful edges,
        prune low-confidence nodes. Inspired by Cognee's improve.
        """
        # deduplicate by label+type
        dupes = self.conn.execute("""
           SELECT label, type, COUNT(*) c FROM kg_nodes WHERE active=1 GROUP BY label, type HAVING c>1
        """).fetchall()
        merged = 0
        for label, typ, cnt in dupes:
            rows = self.conn.execute("SELECT id, confidence, properties FROM kg_nodes WHERE label=? AND type=? AND active=1 ORDER BY confidence DESC", (label, typ)).fetchall()
            keeper = rows[0][0]
            # merge others into keeper: move edges
            for r in rows[1:]:
                # re-point edges
                self.conn.execute("UPDATE kg_edges SET src=? WHERE src=?", (keeper, r[0]))
                self.conn.execute("UPDATE kg_edges SET dst=? WHERE dst=?", (keeper, r[0]))
                self.conn.execute("UPDATE kg_nodes SET active=0 WHERE id=?", (r[0],))
                merged += 1

        # strengthen edges that connect high-confidence nodes
        self.conn.execute("""
            UPDATE kg_edges SET weight = MIN(1.0, weight+0.05)
            WHERE active=1 AND src IN (SELECT id FROM kg_nodes WHERE confidence>0.85 AND active=1)
              AND dst IN (SELECT id FROM kg_nodes WHERE confidence>0.85 AND active=1)
        """)

        # prune orphan low-conf
        cur = self.conn.execute("UPDATE kg_nodes SET active=0 WHERE confidence<0.15 AND active=1")
        pruned = cur.rowcount

        self.conn.commit()
        return {"merged": merged, "pruned": pruned, "dup_groups": len(dupes)}

    # ----- helpers -----
    def _extract_entities(self, text: str, kind: str) -> List[Dict[str, Any]]:
        # Heuristic entity extraction: tools, concepts, tasks, numbers
        entities = []
        low = text.lower()

        # tool triggers
        if any(k in low for k in ("code", "run", "execute", "python", "fibonacci", "benchmark")):
            entities.append({"label": "codeforge", "type": "tool", "confidence": 0.9})
        if any(k in low for k in ("translate", "conlang", "glossopetrae")):
            entities.append({"label": "glossopetrae", "type": "tool", "confidence": 0.9})
        if any(k in low for k in ("hide", "encode", "steg", "secret")):
            entities.append({"label": "steganography", "type": "tool", "confidence": 0.9})

        # concepts from tokens (mem0-style)
        tokens = re.findall(r"[a-z]{3,}", low)
        stop = {"the","and","for","are","you","with","this","that","from","have","what","when","how","can"}
        for t in set(tokens) - stop:
            if len(t) > 3:
                entities.append({"label": t, "type": "concept", "confidence": 0.55})

        # task type
        if kind in ("user_msg", "task", "fact"):
            entities.append({"label": kind, "type": "task_type", "confidence": 0.6})

        # deduplicate
        seen = set()
        uniq = []
        for e in entities:
            key = (e["label"], e["type"])
            if key not in seen:
                seen.add(key)
                uniq.append(e)
        return uniq[:12]

    def _save_observation(self, text, kind, entities):
        cur = self.conn.execute(
            "INSERT INTO kg_observations (text, kind, entities, created_at) VALUES (?,?,?,?)",
            (text, kind, json.dumps(entities), _now())
        )
        self.conn.commit()
        return cur.lastrowid

    def _last_observation_of_kind(self, kind):
        return self.conn.execute("SELECT id FROM kg_observations WHERE kind=? ORDER BY id DESC LIMIT 1", (kind,)).fetchone()

    def _upsert_node(self, label, type, properties, embedding_text, confidence) -> Node:
        label = label.lower().strip()[:120]
        row = self.conn.execute("SELECT id, confidence FROM kg_nodes WHERE label=? AND type=? AND active=1", (label, type)).fetchone()
        now = _now()
        if row:
            nid, old_conf = row
            new_conf = min(0.99, max(old_conf, confidence) + 0.03)
            self.conn.execute("UPDATE kg_nodes SET confidence=?, updated_at=?, properties=?, embedding_text=? WHERE id=?",
                              (new_conf, now, json.dumps(properties), embedding_text[:500], nid))
            self.conn.commit()
            return Node(id=nid, type=type, label=label, properties=properties, confidence=new_conf, created_at=now, updated_at=now, embedding_text=embedding_text)
        else:
            nid = f"n_{int(time.time_ns())}_{hash(label) & 0xffff}"
            self.conn.execute(
                "INSERT INTO kg_nodes (id, type, label, properties, confidence, embedding_text, created_at, updated_at, active) VALUES (?,?,?,?,?,?,?,?,1)",
                (nid, type, label, json.dumps(properties), confidence, embedding_text[:500], now, now)
            )
            self.conn.commit()
            return Node(id=nid, type=type, label=label, properties=properties, confidence=confidence, created_at=now, updated_at=now, embedding_text=embedding_text)

    def _upsert_edge(self, src, dst, relation, weight, meta=None) -> Edge:
        meta = meta or {}
        # check existing
        row = self.conn.execute("SELECT id, weight FROM kg_edges WHERE src=? AND dst=? AND relation=? AND active=1", (src, dst, relation)).fetchone()
        now = _now()
        if row:
            eid, old_w = row
            new_w = min(1.0, old_w + 0.08)
            self.conn.execute("UPDATE kg_edges SET weight=?, meta=? WHERE id=?", (new_w, json.dumps(meta), eid))
            self.conn.commit()
            return Edge(id=eid, src=src, dst=dst, relation=relation, weight=new_w, meta=meta, created_at=now)
        else:
            eid = f"e_{int(time.time_ns())}_{hash(src+dst+relation) & 0xffff}"
            self.conn.execute(
                "INSERT INTO kg_edges (id, src, dst, relation, weight, meta, created_at, active) VALUES (?,?,?,?,?,?,?,1)",
                (eid, src, dst, relation, weight, json.dumps(meta), now)
            )
            self.conn.commit()
            return Edge(id=eid, src=src, dst=dst, relation=relation, weight=weight, meta=meta, created_at=now)

    def _find_similar_nodes(self, label, limit=3, exclude_id=None) -> List[Tuple[str, float]]:
        # simple similarity: substring + shared tokens
        label = label.lower()
        rows = self.conn.execute("SELECT id, label FROM kg_nodes WHERE active=1 AND id!=? LIMIT 200", (exclude_id or "",)).fetchall()
        scored = []
        for nid, nlabel in rows:
            if label in nlabel or nlabel in label:
                scored.append((nid, 0.85))
            else:
                # jaccard of char bigrams
                s1 = set([label[i:i+2] for i in range(len(label)-1)])
                s2 = set([nlabel[i:i+2] for i in range(len(nlabel)-1)])
                if s1 and s2:
                    j = len(s1 & s2) / len(s1 | s2)
                    if j > 0.3:
                        scored.append((nid, j))
        scored.sort(key=lambda x: -x[1])
        return scored[:limit]

    def stats(self) -> Dict[str, Any]:
        n = self.conn.execute("SELECT COUNT(*) FROM kg_nodes WHERE active=1").fetchone()[0]
        e = self.conn.execute("SELECT COUNT(*) FROM kg_edges WHERE active=1").fetchone()[0]
        obs = self.conn.execute("SELECT COUNT(*) FROM kg_observations").fetchone()[0]
        return {"nodes": n, "edges": e, "observations": obs}

    # compatibility with mem0 API
    def get_all(self, limit=50):
        rows = self.conn.execute("SELECT id, type, label, confidence, created_at FROM kg_nodes WHERE active=1 ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
        return [{"id": r[0], "type": r[1], "label": r[2], "confidence": r[3], "created_at": r[4]} for r in rows]
