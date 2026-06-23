from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path

from .config import GRAPH_DIR, GRAPHIFY_BATCH, LLM_PROVIDER, active_model_name
from .corpus import DATA_DIR, clean_text, iter_index_rows, list_collections
from .llm import chat_json
from .openai_batch import BatchTask, submit_or_collect


def node(node_id: str, label: str, node_type: str, **props) -> dict:
    return {"id": node_id, "label": label, "type": node_type, "properties": props}


def edge(source: str, target: str, rel: str, **props) -> dict:
    return {"source": source, "target": target, "type": rel, "properties": props}


def normalize(value: str | None) -> str:
    return clean_text(str(value or "")).replace("\n", " ")


def build_graph() -> tuple[list[dict], list[dict], list[dict]]:
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    documents: list[dict] = []

    root_id = "dataset:woori_poc"
    nodes[root_id] = node(root_id, "우리금융지주 PoC 수집데이터", "Dataset")

    for collection in list_collections():
        collection_id = f"collection:{collection['name']}"
        nodes[collection_id] = node(collection_id, collection["name"], "Collection", path=collection["path"])
        edges.append(edge(root_id, collection_id, "HAS_COLLECTION"))

    for row in iter_index_rows():
        collection = row.get("collection", "unknown")
        title = normalize(row.get("title") or row.get("제목") or row.get("label") or row.get("regulation"))
        path = normalize(row.get("path"))
        source_url = normalize(row.get("source_url") or row.get("출처"))
        doc_key = "|".join(part for part in [collection, title, source_url, path] if part)
        doc_hash = hashlib.sha256(doc_key.encode("utf-8")).hexdigest()[:20]
        doc_id = f"document:{collection}:{doc_hash}"
        doc_type = normalize(row.get("type") or row.get("자료유형") or row.get("class") or "Document")
        nodes[doc_id] = node(
            doc_id,
            title or doc_id,
            "Document",
            collection=collection,
            document_type=doc_type,
            path=path,
            source_url=source_url,
            date=normalize(row.get("date") or row.get("등록일")),
        )
        edges.append(edge(f"collection:{collection}", doc_id, "HAS_DOCUMENT"))
        documents.append({"id": doc_id, **nodes[doc_id]["properties"], "title": title})

        if row.get("regulation"):
            reg_id = f"regulation:{row['regulation']}"
            nodes.setdefault(reg_id, node(reg_id, row["regulation"], "Regulation"))
            edges.append(edge(reg_id, doc_id, "HAS_ANNEX"))
        if row.get("board"):
            board_id = f"board:{row['board']}"
            nodes.setdefault(board_id, node(board_id, row["board"], "Board"))
            edges.append(edge(board_id, doc_id, "PUBLISHED"))
        if row.get("files"):
            for file_path in row["files"]:
                file_id = f"file:{collection}:{file_path}"
                nodes[file_id] = node(file_id, Path(file_path).name, "File", path=file_path)
                edges.append(edge(doc_id, file_id, "HAS_FILE"))

    return list(nodes.values()), edges, documents


def collection_prompts(documents: list[dict], sample_size: int) -> dict[str, tuple[str, str, int]]:
    by_collection: dict[str, list[dict]] = {}
    for doc in documents:
        by_collection.setdefault(doc.get("collection", "unknown"), []).append(doc)

    prompts = {}
    for collection, docs in sorted(by_collection.items()):
        sample = docs[:sample_size]
        titles = "\n".join(f"- {doc.get('title')} ({doc.get('document_type')})" for doc in sample)
        system = (
            "You build compact Korean knowledge graph metadata. "
            "Return strict JSON with keys: collection_summary, topics, entity_types, useful_queries. "
            "No markdown."
        )
        user = f"컬렉션명: {collection}\n문서 수: {len(docs)}\n샘플 문서:\n{titles}"
        prompts[collection] = (system, user, len(docs))
    return prompts


def llm_collection_insights(documents: list[dict], sample_size: int, llm_mode: str, wait_batch: bool) -> list[dict]:
    prompts = collection_prompts(documents, sample_size)
    insights = []

    use_batch = llm_mode == "batch" or (llm_mode == "auto" and LLM_PROVIDER == "openai" and GRAPHIFY_BATCH)
    if use_batch:
        tasks = [
            BatchTask(
                custom_id=f"graphify::{collection}",
                system=system,
                user=user,
                response_format={"type": "json_object"},
            )
            for collection, (system, user, _count) in prompts.items()
        ]
        model_slug = "".join(ch if ch.isalnum() else "_" for ch in active_model_name()).strip("_") or "model"
        outputs, status = submit_or_collect(tasks, GRAPH_DIR / "batch", f"graphify_{model_slug}", wait=wait_batch)
        for collection, (_system, _user, count) in prompts.items():
            raw = outputs.get(f"graphify::{collection}")
            if raw:
                try:
                    result = json.loads(raw[raw.find("{") : raw.rfind("}") + 1])
                except Exception:
                    result = {"raw": raw}
            else:
                result = {
                    "collection_summary": f"{collection} 컬렉션. OpenAI Batch status={status.get('status')}; 결과가 아직 완료되지 않았습니다.",
                    "topics": [],
                    "entity_types": [],
                    "useful_queries": [],
                    "batch_id": status.get("id"),
                    "batch_status": status.get("status"),
                }
            insights.append({"collection": collection, "document_count": count, "llm": result})
        return insights

    for collection, (system, user, count) in prompts.items():
        try:
            result = chat_json(system, user)
        except Exception as exc:
            result = {
                "collection_summary": f"{collection} 컬렉션. LLM graphify failed: {type(exc).__name__}",
                "topics": [],
                "entity_types": [],
                "useful_queries": [],
            }
        insights.append({"collection": collection, "document_count": count, "llm": result})
    return insights


def write_outputs(nodes: list[dict], edges: list[dict], documents: list[dict], insights: list[dict]) -> None:
    GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    for name, rows in [("nodes.jsonl", nodes), ("edges.jsonl", edges), ("documents.jsonl", documents), ("llm_insights.jsonl", insights)]:
        with (GRAPH_DIR / name).open("w", encoding="utf-8") as fp:
            for row in rows:
                fp.write(json.dumps(row, ensure_ascii=False) + "\n")

    type_counts = Counter(node["type"] for node in nodes)
    collection_counts = Counter(doc.get("collection") for doc in documents)
    lines = [
        "# Graphify 결과",
        "",
        f"- 생성일: {date.today().isoformat()}",
        f"- 노드: {len(nodes)}",
        f"- 엣지: {len(edges)}",
        f"- 문서: {len(documents)}",
        "",
        "## 노드 유형",
        "",
    ]
    lines.extend(f"- {key}: {value}" for key, value in sorted(type_counts.items()))
    lines.extend(["", "## 컬렉션별 문서 수", ""])
    lines.extend(f"- {key}: {value}" for key, value in sorted(collection_counts.items()))
    lines.extend(["", "## LLM 컬렉션 인사이트", ""])
    for insight in insights:
        summary = insight.get("llm", {}).get("collection_summary") or insight.get("llm", {}).get("raw", "")
        lines.extend([f"### {insight['collection']}", "", str(summary), ""])
    (GRAPH_DIR / "README.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-size", type=int, default=80, help="documents per collection passed to vLLM for graph insights")
    parser.add_argument("--llm-mode", choices=["auto", "sync", "batch"], default="auto")
    parser.add_argument("--wait-batch", action="store_true", help="poll OpenAI Batch until done or LLM_BATCH_MAX_WAIT_SECONDS is reached")
    args = parser.parse_args()
    nodes, edges, documents = build_graph()
    insights = llm_collection_insights(documents, args.sample_size, args.llm_mode, args.wait_batch)
    write_outputs(nodes, edges, documents, insights)
    print(f"graphify done: nodes={len(nodes)} edges={len(edges)} documents={len(documents)} dir={GRAPH_DIR}")


if __name__ == "__main__":
    main()
