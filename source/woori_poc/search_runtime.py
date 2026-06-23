from __future__ import annotations

import json
import math
from functools import lru_cache

import numpy as np
from openai import OpenAI

from .config import ARTIFACTS_DIR, OPENAI_API_KEY, OPENAI_BASE_URL
from .search_index import EMBEDDING_MODEL, tokenize


SEARCH_DIR = ARTIFACTS_DIR / "search"


@lru_cache(maxsize=1)
def load_chunks() -> list[dict]:
    path = SEARCH_DIR / "chunks.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@lru_cache(maxsize=1)
def load_bm25() -> dict:
    path = SEARCH_DIR / "bm25_index.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_embeddings() -> np.ndarray | None:
    path = SEARCH_DIR / "embeddings.npy"
    if not path.exists():
        return None
    return np.load(path, mmap_mode="r")


def bm25_search(query: str, limit: int = 10) -> list[dict]:
    chunks = load_chunks()
    index = load_bm25()
    if not chunks or not index:
        return []
    q_tokens = tokenize(query)
    total_docs = index["total_docs"]
    avgdl = index["avgdl"] or 1
    k1 = index["k1"]
    b = index["b"]
    scores: list[tuple[float, int]] = []
    for idx, tf in enumerate(index["term_freqs"]):
        score = 0.0
        dl = index["doc_lengths"][idx] or 1
        for term in q_tokens:
            freq = tf.get(term, 0)
            if not freq:
                continue
            df = index["doc_freq"].get(term, 0)
            idf = math.log(1 + (total_docs - df + 0.5) / (df + 0.5))
            score += idf * (freq * (k1 + 1)) / (freq + k1 * (1 - b + b * dl / avgdl))
        if score > 0:
            scores.append((score, idx))
    scores.sort(reverse=True)
    return [{**chunks[idx], "score": score, "source": "bm25"} for score, idx in scores[:limit]]


def embedding_search(query: str, limit: int = 10) -> list[dict]:
    chunks = load_chunks()
    matrix = load_embeddings()
    if not chunks or matrix is None:
        return []
    if not OPENAI_API_KEY:
        return []
    client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=query)
    vector = np.asarray(response.data[0].embedding, dtype=np.float32)
    norm = np.linalg.norm(vector)
    if norm:
        vector = vector / norm
    scores = np.asarray(matrix @ vector)
    top = np.argsort(-scores)[:limit]
    return [{**chunks[int(idx)], "score": float(scores[int(idx)]), "source": "embedding"} for idx in top]


def hybrid_search(query: str, limit: int = 10) -> list[dict]:
    merged: dict[int, dict] = {}
    for rank, row in enumerate(bm25_search(query, limit=limit * 3), 1):
        item = merged.setdefault(row["id"], {**row, "hybrid_score": 0.0, "sources": []})
        item["hybrid_score"] += 1 / (60 + rank)
        item["sources"].append("bm25")
    for rank, row in enumerate(embedding_search(query, limit=limit * 3), 1):
        item = merged.setdefault(row["id"], {**row, "hybrid_score": 0.0, "sources": []})
        item["hybrid_score"] += 1 / (60 + rank)
        item["sources"].append("embedding")
    rows = sorted(merged.values(), key=lambda item: item["hybrid_score"], reverse=True)
    return rows[:limit]
