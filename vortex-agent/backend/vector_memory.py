"""Vector memory: ChromaDB with graceful local fallback."""
import json
import re
from collections import Counter
from paths import vortex_home


def _tokenize(t):
    return re.findall(r"[a-z0-9]+", t.lower())


class LocalVectorStore:
    """Tiny TF-IDF cosine store, persisted to JSON. Zero dependencies."""
    def __init__(self, path):
        self.path = path
        self.docs = json.loads(path.read_text()) if path.exists() else []

    def add(self, text, meta):
        self.docs.append({"text": text, "meta": meta})
        self.docs = self.docs[-2000:]
        self.path.write_text(json.dumps(self.docs))

    def query(self, text, n=3):
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
        self.backend = "local"
        self.chroma = None
        self.collection = None
        try:
            import chromadb
            self.chroma = chromadb.PersistentClient(path=str(vortex_home() / "vectors"))
            self.collection = self.chroma.get_or_create_collection("vortex")
            self.backend = "chroma"
        except Exception:
            self.local = LocalVectorStore(vortex_home() / "vectors.json")

    def remember(self, text, meta=None):
        if self.backend == "chroma":
            import time
            self.collection.add(documents=[text], metadatas=[meta or {}],
                                ids=[f"v_{time.time_ns()}"])
        else:
            self.local.add(text, meta or {})

    def recall(self, query, n=3):
        if self.backend == "chroma":
            try:
                r = self.collection.query(query_texts=[query], n_results=n)
                return r["documents"][0] if r["documents"] else []
            except Exception:
                return []
        return self.local.query(query, n)
