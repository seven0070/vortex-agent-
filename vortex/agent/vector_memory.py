"""Vector memory with Chroma optional + local TF-IDF fallback."""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import List, Optional

from vortex.constants import MEMORY_DIR, ensure_home


def _tokenize(t: str):
    return re.findall(r"[a-z0-9]+", (t or "").lower())


class LocalVectorStore:
    def __init__(self, path: Path):
        self.path = path
        self.docs = json.loads(path.read_text()) if path.exists() else []

    def add(self, text, meta):
        self.docs.append({"text": text, "meta": meta or {}})
        self.docs = self.docs[-3000:]
        self.path.write_text(json.dumps(self.docs))

    def query(self, text, n=5):
        q = Counter(_tokenize(text))
        scored = []
        for d in self.docs:
            c = Counter(_tokenize(d["text"]))
            dot = sum(q[t] * c[t] for t in q if t in c)
            if dot:
                scored.append((dot, d))
        scored.sort(key=lambda x: -x[0])
        return [d["text"] for _, d in scored[:n]]


class VectorMemory:
    def __init__(self):
        ensure_home()
        self.backend = "local"
        try:
            import chromadb

            client = chromadb.PersistentClient(path=str(MEMORY_DIR / "chroma"))
            self.collection = client.get_or_create_collection("vortex")
            self.backend = "chroma"
        except Exception:
            self.local = LocalVectorStore(MEMORY_DIR / "vectors.json")

    def remember(self, text: str, meta: Optional[dict] = None):
        if self.backend == "chroma":
            import time

            self.collection.add(
                documents=[text],
                metadatas=[meta or {}],
                ids=[f"v_{time.time_ns()}"],
            )
        else:
            self.local.add(text, meta or {})

    def recall(self, query: str, n: int = 5) -> List[str]:
        if self.backend == "chroma":
            try:
                r = self.collection.query(query_texts=[query], n_results=n)
                return r["documents"][0] if r["documents"] else []
            except Exception:
                return []
        return self.local.query(query, n)
