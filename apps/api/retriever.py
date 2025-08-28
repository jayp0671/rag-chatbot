from __future__ import annotations
import os, json
from pathlib import Path
from typing import List, Dict, Any
import numpy as np
import faiss
import httpx

# Local ST (kept for fallback)
from sentence_transformers import SentenceTransformer

def _l2_normalize(a: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(a, axis=1, keepdims=True) + 1e-12
    return a / norms

class Embedder:
    """Local CPU embedder (original)."""
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.model = SentenceTransformer(model_name, device="cpu")

    def encode(self, texts: List[str]) -> List[np.ndarray]:
        embs = self.model.encode(
            texts,
            batch_size=8,                     # keep small even locally
            convert_to_numpy=True,
            show_progress_bar=False,
            normalize_embeddings=False,
        ).astype("float32")
        embs = _l2_normalize(embs)
        return [e for e in embs]

class HFAPIEmbedder:
    """Remote embeddings via Hugging Face Inference API (feature-extraction)."""
    def __init__(self, model_name: str, token: str):
        if not token:
            raise ValueError("HF_TOKEN is required for HFAPIEmbedder")
        self.model_name = model_name
        self.url = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{model_name}"
        self.headers = {"Authorization": f"Bearer {token}"}

    def encode(self, texts: List[str]) -> List[np.ndarray]:
        outs: List[np.ndarray] = []
        # call one by one to stay within free limits and keep memory tiny
        with httpx.Client(timeout=60) as client:
            for t in texts:
                r = client.post(self.url, headers=self.headers, json={"inputs": t, "options": {"wait_for_model": True}})
                if r.status_code != 200:
                    raise RuntimeError(f"HF API error {r.status_code}: {r.text}")
                arr = np.asarray(r.json(), dtype="float32")
                # If shape is [seq_len, dim], mean-pool to [dim]
                if arr.ndim == 2:
                    arr = arr.mean(axis=0)
                outs.append(arr)
        embs = np.vstack(outs).astype("float32")
        embs = _l2_normalize(embs)
        return [e for e in embs]

class VectorStore:
    def __init__(self, index_dir: Path):
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.index_dir / "flat.index"
        self.meta_path = self.index_dir / "chunks.json"
        self._index = None
        self._meta: List[Dict[str, Any]] = []
        self._load()

    def ready(self) -> bool:
        return self._index is not None and len(self._meta) > 0

    def _load(self):
        if self.index_path.exists():
            self._index = faiss.read_index(str(self.index_path))
            if self.meta_path.exists():
                self._meta = json.loads(self.meta_path.read_text("utf-8"))
        else:
            self._index = None
            self._meta = []

    def _save(self):
        if self._index is not None:
            faiss.write_index(self._index, str(self.index_path))
        self.meta_path.write_text(json.dumps(self._meta, ensure_ascii=False, indent=2), "utf-8")

    def add(self, items: List[Dict[str, Any]], vectors: List[np.ndarray]):
        vecs = np.vstack(vectors).astype("float32")
        if self._index is None:
            d = vecs.shape[1]
            self._index = faiss.IndexFlatIP(d)  # cosine via normalized vectors
        self._index.add(vecs)
        self._meta.extend(items)
        self._save()

    def search(self, query_vec: np.ndarray, top_k: int = 5) -> List[Dict[str, Any]]:
        if self._index is None or len(self._meta) == 0:
            return []
        q = query_vec.reshape(1, -1).astype("float32")
        D, I = self._index.search(q, k=min(top_k, len(self._meta)))
        out = []
        for score, idx in zip(D[0], I[0]):
            if idx == -1: continue
            meta = self._meta[idx]
            out.append({"score": float(score), **meta})
        return out
