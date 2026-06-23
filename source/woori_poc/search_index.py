from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path

import numpy as np
from openai import OpenAI

from .config import ARTIFACTS_DIR, DATA_DIR, OPENAI_API_KEY, OPENAI_BASE_URL
from .corpus import TEXT_EXTENSIONS, clean_text


SEARCH_DIR = ARTIFACTS_DIR / "search"
EMBEDDING_MODEL = "text-embedding-ada-002"
CHUNK_CHARS = 1200
CHUNK_OVERLAP = 150
EMBED_BATCH_SIZE = 64


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[가-힣A-Za-z0-9_]{2,}", text.lower())
    grams: list[str] = []
    for token in tokens:
        if re.fullmatch(r"[가-힣]{4,}", token):
            grams.extend(token[i : i + 2] for i in range(len(token) - 1))
    return tokens + grams


def is_indexable_artifact(root: Path, path: Path) -> bool:
    if SEARCH_DIR in path.parents:
        return False
    if root == ARTIFACTS_DIR / "graph" and path.parent.name == "batch":
        return False
    return True


def iter_source_files():
    for root in [DATA_DIR, ARTIFACTS_DIR / "graph", ARTIFACTS_DIR / "wiki"]:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS and is_indexable_artifact(root, path):
                yield root, path


def chunk_text(text: str) -> list[str]:
    text = clean_text(text)
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + CHUNK_CHARS)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return chunks


def build_chunks() -> list[dict]:
    rows = []
    chunk_id = 0
    for root, path in iter_source_files():
        area = "data" if root == DATA_DIR else "artifacts"
        rel = str(path.relative_to(root)).replace("\\", "/")
        text = path.read_text(encoding="utf-8", errors="replace")
        for idx, chunk in enumerate(chunk_text(text)):
            rows.append(
                {
                    "id": chunk_id,
                    "area": area,
                    "path": rel,
                    "chunk_index": idx,
                    "text": chunk,
                }
            )
            chunk_id += 1
    return rows


def build_bm25(chunks: list[dict]) -> dict:
    tokenized = [tokenize(row["text"]) for row in chunks]
    doc_freq: Counter[str] = Counter()
    term_freqs = []
    lengths = []
    for tokens in tokenized:
        tf = Counter(tokens)
        term_freqs.append(tf)
        lengths.append(len(tokens))
        doc_freq.update(tf.keys())
    total_docs = len(chunks)
    avgdl = sum(lengths) / total_docs if total_docs else 0
    return {
        "k1": 1.5,
        "b": 0.75,
        "avgdl": avgdl,
        "total_docs": total_docs,
        "doc_freq": dict(doc_freq),
        "doc_lengths": lengths,
        "term_freqs": [dict(tf) for tf in term_freqs],
    }


def write_chunks(chunks: list[dict]) -> None:
    with (SEARCH_DIR / "chunks.jsonl").open("w", encoding="utf-8") as fp:
        for row in chunks:
            fp.write(json.dumps(row, ensure_ascii=False) + "\n")


def build_embeddings(chunks: list[dict]) -> None:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is required for embeddings")
    client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    vectors = []
    for start in range(0, len(chunks), EMBED_BATCH_SIZE):
        batch = chunks[start : start + EMBED_BATCH_SIZE]
        response = client.embeddings.create(model=EMBEDDING_MODEL, input=[row["text"] for row in batch])
        ordered = sorted(response.data, key=lambda item: item.index)
        vectors.extend(item.embedding for item in ordered)
        print(f"embedded {min(start + EMBED_BATCH_SIZE, len(chunks))}/{len(chunks)}")
    arr = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1
    arr = arr / norms
    np.save(SEARCH_DIR / "embeddings.npy", arr)
    (SEARCH_DIR / "embedding_config.json").write_text(
        json.dumps(
            {
                "model": EMBEDDING_MODEL,
                "chunk_chars": CHUNK_CHARS,
                "chunk_overlap": CHUNK_OVERLAP,
                "batch_size": EMBED_BATCH_SIZE,
                "dimension": int(arr.shape[1]) if arr.size else 0,
                "chunks": len(chunks),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-embeddings", action="store_true")
    args = parser.parse_args()
    SEARCH_DIR.mkdir(parents=True, exist_ok=True)
    chunks = build_chunks()
    write_chunks(chunks)
    (SEARCH_DIR / "bm25_index.json").write_text(json.dumps(build_bm25(chunks), ensure_ascii=False), encoding="utf-8")
    if not args.skip_embeddings:
        build_embeddings(chunks)
    print(f"search index done: chunks={len(chunks)} dir={SEARCH_DIR}")


if __name__ == "__main__":
    main()
