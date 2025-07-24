import os
import faiss
import numpy as np
from typing import List, Dict, Optional
from sentence_transformers import SentenceTransformer
import pickle

INDEX_PATH = "data/faiss_index.bin"
META_PATH = "data/faiss_meta.pkl"
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

class RAGIndex:
    def __init__(self, dim: int = 384):
        self.dim = dim
        self.model = SentenceTransformer(EMBEDDING_MODEL)
        self.index = faiss.IndexFlatL2(dim)
        self.meta: List[Dict] = []
        self._load()

    def _load(self):
        if os.path.exists(INDEX_PATH) and os.path.exists(META_PATH):
            self.index = faiss.read_index(INDEX_PATH)
            with open(META_PATH, "rb") as f:
                self.meta = pickle.load(f)
        else:
            self.index = faiss.IndexFlatL2(self.dim)
            self.meta = []

    def _save(self):
        os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
        faiss.write_index(self.index, INDEX_PATH)
        with open(META_PATH, "wb") as f:
            pickle.dump(self.meta, f)

    def embed(self, text: str) -> np.ndarray:
        emb = self.model.encode([text], show_progress_bar=False, normalize_embeddings=True)
        return emb.astype(np.float32)

    def add_document(self, doc_id: str, text: str, meta: Optional[Dict] = None):
        emb = self.embed(text)
        self.index.add(emb)
        entry = {"doc_id": doc_id, "text": text}
        if meta:
            entry.update(meta)
        self.meta.append(entry)
        self._save()

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        if len(self.meta) == 0:
            return []
        emb = self.embed(query)
        D, I = self.index.search(emb, top_k)
        results = []
        for idx, dist in zip(I[0], D[0]):
            if idx < len(self.meta):
                entry = self.meta[idx].copy()
                entry["distance"] = float(dist)
                results.append(entry)
        return results

# Ленивая инициализация singleton
_rag_index = None

def get_rag_index():
    global _rag_index
    if _rag_index is None:
        _rag_index = RAGIndex()
    return _rag_index 