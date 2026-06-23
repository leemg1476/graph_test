from __future__ import annotations

import json
import re
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .config import ARTIFACTS_DIR, DATA_DIR, GRAPH_DIR, WIKI_DIR
from .corpus import (
    iter_index_rows,
    list_collections as corpus_list_collections,
    list_dir as corpus_list_dir,
    read_text_file,
    search_text as corpus_search_text,
)
from .search_runtime import bm25_search, embedding_search, hybrid_search


mcp = FastMCP("woori-poc-data")


def ok(data):
    return {"ok": True, "data": data}


def fail(exc: Exception):
    return {"ok": False, "error": type(exc).__name__, "message": str(exc)}


def jsonl_rows(path: Path, limit: int = 100) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
            if len(rows) >= limit:
                break
    return rows


def tokenize_graph_query(text: str) -> list[str]:
    tokens = re.findall(r"[0-9A-Za-z가-힣]{2,}", text.lower())
    bigrams: list[str] = []
    compact = re.sub(r"\s+", "", text.lower())
    for i in range(max(0, len(compact) - 1)):
        part = compact[i : i + 2]
        if re.search(r"[가-힣]", part):
            bigrams.append(part)
    return tokens + bigrams


def score_graph_row(row: dict, tokens: list[str]) -> float:
    if not tokens:
        return 0.0
    blob = json.dumps(row, ensure_ascii=False).lower()
    score = 0.0
    for token in tokens:
        count = blob.count(token)
        if count:
            score += min(count, 4)
    row_type = str(row.get("type") or "")
    if row_type in {"AuditFinding", "Risk", "FailureMode", "Control", "RegulationTopic", "Remediation"}:
        score *= 1.3
    return score


def load_graph_rows(rel: str, limit: int | None = None) -> list[dict]:
    path = GRAPH_DIR / rel
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
        if limit and len(rows) >= limit:
            break
    return rows


def semantic_graph_search(query: str, limit: int) -> list[dict]:
    tokens = tokenize_graph_query(query)
    candidates: list[tuple[float, dict]] = []
    nodes = load_graph_rows("semantic_nodes.jsonl")
    edges = load_graph_rows("semantic_edges.jsonl")
    documents = load_graph_rows("semantic_documents.jsonl")
    node_by_id = {row.get("id"): row for row in nodes}
    paths_by_node: dict[str, set[str]] = {}
    for edge_row in edges:
        props = edge_row.get("properties") or {}
        path = props.get("path")
        if not path:
            continue
        paths_by_node.setdefault(edge_row.get("source", ""), set()).add(path)
        paths_by_node.setdefault(edge_row.get("target", ""), set()).add(path)

    for rel, rows in [
        ("semantic_nodes.jsonl", nodes),
        ("semantic_edges.jsonl", edges),
        ("semantic_documents.jsonl", documents),
    ]:
        for row in rows:
            score = score_graph_row(row, tokens)
            if score <= 0:
                continue
            row = {**row, "_artifact": f"graph/{rel}", "_score": score}
            if rel == "semantic_nodes.jsonl":
                related_paths = sorted(paths_by_node.get(row.get("id", ""), set()))[:10]
                if related_paths:
                    row["related_paths"] = related_paths
            elif rel == "semantic_edges.jsonl":
                source = node_by_id.get(row.get("source", ""), {})
                target = node_by_id.get(row.get("target", ""), {})
                props = row.get("properties") or {}
                row["source_label"] = source.get("label")
                row["source_type"] = source.get("type")
                row["target_label"] = target.get("label")
                row["target_type"] = target.get("type")
                if props.get("path"):
                    row["related_paths"] = [props["path"]]
            candidates.append((score, row))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return [row for _score, row in candidates[:limit]]


@mcp.tool()
def list_collections() -> dict:
    """List available collected data collections."""
    try:
        return ok(corpus_list_collections())
    except Exception as exc:
        return fail(exc)


@mcp.tool()
def list_directory(area: str = "data", path: str = ".") -> dict:
    """List a directory under area='data' or area='artifacts'."""
    try:
        return ok(corpus_list_dir(area, path))
    except Exception as exc:
        return fail(exc)


@mcp.tool()
def read_file(area: str, path: str, max_chars: int = 20000) -> dict:
    """Read a text file under data/artifacts. Binary files return metadata only."""
    try:
        return ok(read_text_file(area, path, max_chars=max_chars))
    except Exception as exc:
        return fail(exc)


@mcp.tool()
def search_text(query: str, area: str = "data", collection: str | None = None, limit: int = 20) -> dict:
    """Search text files under data or artifacts."""
    try:
        return ok(corpus_search_text(query=query, area=area, collection=collection, limit=limit))
    except Exception as exc:
        return fail(exc)


@mcp.tool()
def search_bm25(query: str, limit: int = 10) -> dict:
    """Search the prebuilt BM25 index."""
    try:
        return ok(bm25_search(query, limit=limit))
    except Exception as exc:
        return fail(exc)


@mcp.tool()
def search_embedding(query: str, limit: int = 10) -> dict:
    """Search the prebuilt OpenAI text-embedding-ada-002 vector index."""
    try:
        return ok(embedding_search(query, limit=limit))
    except Exception as exc:
        return fail(exc)


@mcp.tool()
def search_hybrid(query: str, limit: int = 10) -> dict:
    """Search with reciprocal-rank fusion over BM25 and embeddings."""
    try:
        return ok(hybrid_search(query, limit=limit))
    except Exception as exc:
        return fail(exc)


@mcp.tool()
def get_index(collection: str | None = None, limit: int = 200) -> dict:
    """Read dataset JSONL indexes. Optionally filter by collection."""
    try:
        rows = []
        for row in iter_index_rows(collection):
            rows.append(row)
            if len(rows) >= limit:
                break
        return ok(rows)
    except Exception as exc:
        return fail(exc)


@mcp.tool()
def graph_summary() -> dict:
    """Return graphify summary and artifact paths."""
    try:
        readme = GRAPH_DIR / "README.md"
        semantic = GRAPH_DIR / "semantic_README.md"
        return ok(
            {
                "exists": GRAPH_DIR.exists(),
                "summary": readme.read_text(encoding="utf-8") if readme.exists() else "",
                "semantic_summary": semantic.read_text(encoding="utf-8") if semantic.exists() else "",
                "nodes": "graph/nodes.jsonl",
                "edges": "graph/edges.jsonl",
                "documents": "graph/documents.jsonl",
                "llm_insights": "graph/llm_insights.jsonl",
                "semantic_nodes": "graph/semantic_nodes.jsonl",
                "semantic_edges": "graph/semantic_edges.jsonl",
                "semantic_documents": "graph/semantic_documents.jsonl",
            }
        )
    except Exception as exc:
        return fail(exc)


@mcp.tool()
def search_graph(query: str, limit: int = 30) -> dict:
    """Search semantic graph first, then metadata graph artifacts."""
    try:
        semantic_results = semantic_graph_search(query, limit)
        if semantic_results:
            return ok(semantic_results)
        results = []
        needle = query.lower()
        for rel in ["nodes.jsonl", "documents.jsonl", "llm_insights.jsonl"]:
            path = GRAPH_DIR / rel
            if not path.exists():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                if needle in line.lower():
                    row = json.loads(line)
                    row["_artifact"] = f"graph/{rel}"
                    results.append(row)
                    if len(results) >= limit:
                        return ok(results)
        return ok(results)
    except Exception as exc:
        return fail(exc)


@mcp.tool()
def list_wiki_pages() -> dict:
    """List LLM wiki pages."""
    try:
        if not WIKI_DIR.exists():
            return ok([])
        return ok(
            [
                {"name": path.name, "path": f"wiki/{path.name}", "size": path.stat().st_size}
                for path in sorted(WIKI_DIR.glob("*.md"), key=lambda p: p.name)
            ]
        )
    except Exception as exc:
        return fail(exc)


@mcp.tool()
def read_wiki(page: str = "index.md", max_chars: int = 20000) -> dict:
    """Read an LLM wiki page from artifacts/wiki."""
    try:
        normalized = page.replace("\\", "/")
        if normalized.startswith("wiki/"):
            normalized = normalized[len("wiki/") :]
        return ok(read_text_file("artifacts", f"wiki/{normalized}", max_chars=max_chars))
    except Exception as exc:
        return fail(exc)


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    mcp.run()


if __name__ == "__main__":
    main()
