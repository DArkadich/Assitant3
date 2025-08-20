import os
import pickle
from typing import List, Dict, Optional
import numpy as np

INDEX_PATH = "data/faiss_index.bin"
META_PATH = "data/faiss_meta.pkl"
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
RAG_ENABLE = os.getenv("RAG_ENABLE", "1") not in ("0", "false", "False")

class RAGIndex:
    def __init__(self, dim: int = 384):
        # Ленивая загрузка зависимостей, чтобы не тянуть torch в быстром пути
        self.dim = dim
        # Импортируем по месту использования
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            import faiss  # type: ignore
        except Exception:
            # Если нет зависимостей — поднимем понятную ошибку при обращении
            SentenceTransformer = None  # type: ignore
            faiss = None  # type: ignore

        self._faiss = faiss
        self._SentenceTransformer = SentenceTransformer
        if self._SentenceTransformer is None or self._faiss is None:
            # Работает как no-op индекс
            self.model = None
            self.index = None
            self.meta: List[Dict] = []
            return

        self.model = self._SentenceTransformer(EMBEDDING_MODEL)
        self.index = self._faiss.IndexFlatL2(dim)
        self.meta: List[Dict] = []
        self._load()

    def _load(self):
        if self.index is None:
            return
        if os.path.exists(INDEX_PATH) and os.path.exists(META_PATH):
            self.index = self._faiss.read_index(INDEX_PATH)
            with open(META_PATH, "rb") as f:
                self.meta = pickle.load(f)
        else:
            self.index = self._faiss.IndexFlatL2(self.dim)
            self.meta = []

    def _save(self):
        if self.index is None:
            return
        os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
        self._faiss.write_index(self.index, INDEX_PATH)
        with open(META_PATH, "wb") as f:
            pickle.dump(self.meta, f)

    def embed(self, text: str) -> np.ndarray:
        if self.model is None:
            # Возврат нулевого вектора при отключенном/недоступном RAG
            return np.zeros((1, self.dim), dtype=np.float32)
        emb = self.model.encode([text], show_progress_bar=False, normalize_embeddings=True)
        return emb.astype(np.float32)

    def add_document(self, doc_id: str, text: str, meta: Optional[Dict] = None):
        if self.index is None:
            return
        emb = self.embed(text)
        self.index.add(emb)
        entry = {"doc_id": doc_id, "text": text}
        if meta:
            entry.update(meta)
        self.meta.append(entry)
        self._save()

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        if self.index is None or len(self.meta) == 0:
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
        if not RAG_ENABLE:
            class NoopIndex:
                def add_document(self, *args, **kwargs):
                    return
                def search(self, *args, **kwargs):
                    return []
            _rag_index = NoopIndex()
        else:
            _rag_index = RAGIndex()
    return _rag_index 