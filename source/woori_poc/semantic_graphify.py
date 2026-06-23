from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .config import DATA_DIR, GRAPH_DIR, GRAPHIFY_BATCH, LLM_PROVIDER, active_model_name
from .corpus import TEXT_EXTENSIONS, clean_text
from .llm import chat_json
from .openai_batch import BatchTask, submit_or_collect


SEMANTIC_NODE_TYPES = {
    "AuditFinding",
    "Risk",
    "FailureMode",
    "Control",
    "RegulationTopic",
    "Remediation",
    "Evidence",
}

SEMANTIC_EDGE_TYPES = {
    "MENTIONS_RISK",
    "EVIDENCES_FAILURE",
    "INCREASES_RISK",
    "MITIGATES",
    "DETECTS",
    "REQUIRES_CONTROL",
    "SUPPORTS_REMEDIATION",
    "RELATED_TO_TOPIC",
    "HAS_EVIDENCE",
}


@dataclass(frozen=True)
class SourceDoc:
    path: Path
    rel_path: str
    collection: str
    title: str
    text: str


def stable_hash(value: str, size: int = 20) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:size]


def node_id(node_type: str, label: str) -> str:
    return f"semantic:{node_type}:{stable_hash(node_type + ':' + label.lower(), 24)}"


def doc_id(rel_path: str) -> str:
    return f"semantic:Document:{stable_hash(rel_path, 24)}"


def iter_source_docs(collections: set[str] | None, max_chars: int) -> list[SourceDoc]:
    docs: list[SourceDoc] = []
    if not DATA_DIR.exists():
        return docs
    for path in sorted(DATA_DIR.rglob("*"), key=lambda p: str(p)):
        if not path.is_file() or path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        rel_path = str(path.relative_to(DATA_DIR)).replace("\\", "/")
        collection = rel_path.split("/", 1)[0]
        if collections and collection not in collections:
            continue
        if path.name in {"index.jsonl", "annex_index.jsonl"}:
            continue
        text = clean_text(path.read_text(encoding="utf-8", errors="replace"))
        if not text:
            continue
        title = infer_title(path, text)
        docs.append(SourceDoc(path=path, rel_path=rel_path, collection=collection, title=title, text=text[:max_chars]))
    return docs


def infer_title(path: Path, text: str) -> str:
    for line in text.splitlines()[:20]:
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            return stripped[:120]
    return path.stem[:120]


def semantic_prompt(doc: SourceDoc) -> tuple[str, str]:
    system = (
        "You extract an audit/internal-control knowledge graph from Korean regulatory and audit documents. "
        "Return strict JSON only. Use these node types only: "
        "AuditFinding, Risk, FailureMode, Control, RegulationTopic, Remediation, Evidence. "
        "Use these edge types only: MENTIONS_RISK, EVIDENCES_FAILURE, INCREASES_RISK, MITIGATES, DETECTS, "
        "REQUIRES_CONTROL, SUPPORTS_REMEDIATION, RELATED_TO_TOPIC, HAS_EVIDENCE. "
        "Prefer concise Korean labels. Keep evidence quotes short. Do not invent facts."
    )
    user = {
        "document": {
            "collection": doc.collection,
            "path": doc.rel_path,
            "title": doc.title,
            "text": doc.text,
        },
        "output_schema": {
            "nodes": [
                {
                    "type": "Risk|FailureMode|Control|RegulationTopic|Remediation|AuditFinding|Evidence",
                    "label": "short Korean label",
                    "description": "why this node is present in this document",
                    "confidence": 0.0,
                }
            ],
            "edges": [
                {
                    "source_type": "node type",
                    "source_label": "existing node label",
                    "target_type": "node type",
                    "target_label": "existing node label",
                    "type": "edge type",
                    "evidence": "short quote or paraphrase",
                    "confidence": 0.0,
                }
            ],
        },
    }
    return system, json.dumps(user, ensure_ascii=False)


KEYWORD_RULES: list[dict[str, Any]] = [
    {
        "patterns": ["불법 계좌", "무단 계좌", "계좌 개설", "실명확인", "본인확인"],
        "finding": "계좌개설 통제 미흡",
        "risk": "비대면·영업점 계좌개설 사고 위험",
        "failure": "본인확인 및 실명확인 절차 미흡",
        "control": "계좌개설 본인확인·증빙 검증 통제",
        "topic": "금융실명거래 및 계좌개설 내부통제",
        "remediation": "계좌개설 승인·사후점검·이상거래 모니터링 강화",
    },
    {
        "patterns": ["횡령", "유용", "PF대출", "대출금"],
        "finding": "자금 취급 및 대출 사후관리 통제 미흡",
        "risk": "임직원 횡령 및 대출금 유용 위험",
        "failure": "직무분리·승인·사후점검 미흡",
        "control": "자금 집행 승인, 직무분리, 잔액 대사 통제",
        "topic": "은행 내부통제 및 대출업무 관리",
        "remediation": "고위험 거래 이중승인과 정기 대사·이상징후 탐지 도입",
    },
    {
        "patterns": ["내부통제기준", "내부통제", "준법감시", "책무구조"],
        "finding": "내부통제 체계 운영 미흡",
        "risk": "법규 위반 및 경영진 책임 확대 위험",
        "failure": "통제기준 마련·운영·점검 체계 미흡",
        "control": "내부통제기준, 준법감시, 책무구조도 운영",
        "topic": "금융회사 지배구조 및 내부통제",
        "remediation": "통제기준 현행화, 책임자 지정, 점검 결과 이사회 보고",
    },
    {
        "patterns": ["검사결과", "제재", "기관경고", "과태료", "문책"],
        "finding": "감독당국 검사·제재 지적사항",
        "risk": "제재, 평판 훼손, 영업 제한 위험",
        "failure": "법규준수 및 사전통제 미흡",
        "control": "검사 지적사항 이행관리 및 제재 리스크 관리",
        "topic": "금융감독 검사 및 제재",
        "remediation": "제재 원인 분석, 개선계획 수립, 이행증빙 관리",
    },
    {
        "patterns": ["별표", "별지", "서식", "보고서", "신청서"],
        "finding": "규정 별표·별지 준수 필요사항",
        "risk": "보고·신청·공시 누락 또는 형식 하자 위험",
        "failure": "서식 요건 및 제출 항목 관리 미흡",
        "control": "별표·별지 기반 체크리스트와 제출 전 검증",
        "topic": "감독규정 시행세칙 별표·별지",
        "remediation": "필수항목 매핑표와 제출 전 리뷰 절차 운영",
    },
]


def snippets_for_patterns(text: str, patterns: list[str], width: int = 180) -> list[str]:
    snippets = []
    lowered = text.lower()
    for pattern in patterns:
        pos = lowered.find(pattern.lower())
        if pos >= 0:
            snippets.append(clean_text(text[max(0, pos - width) : pos + width]))
    return snippets[:3]


def add_node(nodes: dict[str, dict], node_type: str, label: str, description: str, **props: Any) -> str:
    if node_type not in SEMANTIC_NODE_TYPES:
        node_type = "Evidence"
    nid = node_id(node_type, label)
    existing = nodes.get(nid)
    if existing:
        existing["properties"]["mentions"] = existing["properties"].get("mentions", 1) + 1
        if description and description not in existing["properties"].get("descriptions", []):
            existing["properties"].setdefault("descriptions", []).append(description)
        return nid
    nodes[nid] = {
        "id": nid,
        "label": label,
        "type": node_type,
        "properties": {
            "description": description,
            "descriptions": [description] if description else [],
            "mentions": 1,
            **props,
        },
    }
    return nid


def add_edge(edges: list[dict], source: str, target: str, edge_type: str, **props: Any) -> None:
    if edge_type not in SEMANTIC_EDGE_TYPES:
        edge_type = "RELATED_TO_TOPIC"
    edges.append({"source": source, "target": target, "type": edge_type, "properties": props})


def heuristic_extract(docs: list[SourceDoc]) -> tuple[dict[str, dict], list[dict]]:
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    for doc in docs:
        did = doc_id(doc.rel_path)
        nodes[did] = {
            "id": did,
            "label": doc.title,
            "type": "Document",
            "properties": {"collection": doc.collection, "path": doc.rel_path, "title": doc.title},
        }
        for rule in KEYWORD_RULES:
            snippets = snippets_for_patterns(doc.text, rule["patterns"])
            if not snippets:
                continue
            finding = add_node(nodes, "AuditFinding", rule["finding"], f"{doc.title}에서 관련 키워드가 확인됨")
            risk = add_node(nodes, "Risk", rule["risk"], f"{rule['finding']}에서 파생되는 잠재 리스크")
            failure = add_node(nodes, "FailureMode", rule["failure"], f"{rule['finding']}의 주요 미비 유형")
            control = add_node(nodes, "Control", rule["control"], f"{rule['risk']} 완화를 위한 통제")
            topic = add_node(nodes, "RegulationTopic", rule["topic"], "관련 규정·감독 주제")
            remediation = add_node(nodes, "Remediation", rule["remediation"], "우선 검토할 개선 방향")
            evidence = add_node(nodes, "Evidence", snippets[0][:160], f"문서 근거: {doc.rel_path}", path=doc.rel_path)

            add_edge(edges, did, finding, "HAS_EVIDENCE", path=doc.rel_path, evidence=snippets[0])
            add_edge(edges, finding, risk, "MENTIONS_RISK", path=doc.rel_path, evidence=snippets[0])
            add_edge(edges, finding, failure, "EVIDENCES_FAILURE", path=doc.rel_path, evidence=snippets[0])
            add_edge(edges, failure, risk, "INCREASES_RISK", path=doc.rel_path, evidence=snippets[0])
            add_edge(edges, control, risk, "MITIGATES", path=doc.rel_path, evidence=snippets[0])
            add_edge(edges, topic, control, "REQUIRES_CONTROL", path=doc.rel_path, evidence=snippets[0])
            add_edge(edges, remediation, finding, "SUPPORTS_REMEDIATION", path=doc.rel_path, evidence=snippets[0])
            add_edge(edges, finding, evidence, "HAS_EVIDENCE", path=doc.rel_path, evidence=snippets[0])
    return nodes, edges


def parse_json_object(raw: str) -> dict[str, Any]:
    if not raw:
        return {}
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end < start:
        return {}
    try:
        value = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def merge_llm_output(nodes: dict[str, dict], edges: list[dict], doc: SourceDoc, result: dict[str, Any]) -> None:
    did = doc_id(doc.rel_path)
    for item in result.get("nodes", []) or []:
        if not isinstance(item, dict):
            continue
        ntype = str(item.get("type") or "Evidence")
        label = clean_text(str(item.get("label") or ""))[:140]
        if not label:
            continue
        desc = clean_text(str(item.get("description") or ""))[:600]
        nid = add_node(
            nodes,
            ntype,
            label,
            desc,
            source="llm",
            confidence=float(item.get("confidence") or 0),
        )
        add_edge(edges, did, nid, "HAS_EVIDENCE", path=doc.rel_path, source="llm")

    for item in result.get("edges", []) or []:
        if not isinstance(item, dict):
            continue
        source_type = str(item.get("source_type") or "Evidence")
        source_label = clean_text(str(item.get("source_label") or ""))[:140]
        target_type = str(item.get("target_type") or "Evidence")
        target_label = clean_text(str(item.get("target_label") or ""))[:140]
        if not source_label or not target_label:
            continue
        sid = add_node(nodes, source_type, source_label, "", source="llm")
        tid = add_node(nodes, target_type, target_label, "", source="llm")
        add_edge(
            edges,
            sid,
            tid,
            str(item.get("type") or "RELATED_TO_TOPIC"),
            path=doc.rel_path,
            evidence=clean_text(str(item.get("evidence") or ""))[:500],
            source="llm",
            confidence=float(item.get("confidence") or 0),
        )


def llm_extract(docs: list[SourceDoc], mode: str, wait_batch: bool) -> tuple[dict[str, dict], list[dict], dict[str, Any]]:
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    use_batch = mode == "batch" or (mode == "auto" and LLM_PROVIDER == "openai" and GRAPHIFY_BATCH)
    model_slug = "".join(ch if ch.isalnum() else "_" for ch in active_model_name()).strip("_") or "model"
    status: dict[str, Any] = {"mode": mode, "provider": LLM_PROVIDER, "model": active_model_name(), "docs": len(docs)}

    if use_batch:
        tasks = []
        for doc in docs:
            system, user = semantic_prompt(doc)
            tasks.append(
                BatchTask(
                    custom_id=f"semantic::{stable_hash(doc.rel_path, 32)}",
                    system=system,
                    user=user,
                    response_format={"type": "json_object"},
                )
            )
        outputs, batch_status = submit_or_collect(
            tasks,
            GRAPH_DIR / "batch",
            f"semantic_graphify_{model_slug}",
            wait=wait_batch,
        )
        status.update(batch_status)
        by_id = {f"semantic::{stable_hash(doc.rel_path, 32)}": doc for doc in docs}
        for custom_id, raw in outputs.items():
            doc = by_id.get(custom_id)
            if doc:
                merge_llm_output(nodes, edges, doc, parse_json_object(raw))
        status["completed_outputs"] = len(outputs)
        return nodes, edges, status

    if mode == "none":
        status["status"] = "skipped"
        return nodes, edges, status

    for doc in docs:
        system, user = semantic_prompt(doc)
        try:
            result = chat_json(system, user)
            merge_llm_output(nodes, edges, doc, result)
        except Exception as exc:
            status.setdefault("errors", []).append({"path": doc.rel_path, "error": type(exc).__name__, "message": str(exc)})
    status["status"] = "completed"
    return nodes, edges, status


def dedupe_edges(edges: list[dict]) -> list[dict]:
    seen: set[str] = set()
    rows: list[dict] = []
    for edge in edges:
        props = edge.get("properties") or {}
        key = "|".join(
            [
                edge.get("source", ""),
                edge.get("target", ""),
                edge.get("type", ""),
                str(props.get("path", "")),
                str(props.get("evidence", ""))[:120],
            ]
        )
        if key in seen:
            continue
        seen.add(key)
        rows.append(edge)
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        for row in rows:
            fp.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_outputs(nodes: dict[str, dict], edges: list[dict], docs: list[SourceDoc], status: dict[str, Any]) -> None:
    rows = sorted(nodes.values(), key=lambda row: (row["type"], row["label"]))
    edges = dedupe_edges(edges)
    write_jsonl(GRAPH_DIR / "semantic_nodes.jsonl", rows)
    write_jsonl(GRAPH_DIR / "semantic_edges.jsonl", edges)
    write_jsonl(
        GRAPH_DIR / "semantic_documents.jsonl",
        [
            {
                "id": doc_id(doc.rel_path),
                "title": doc.title,
                "collection": doc.collection,
                "path": doc.rel_path,
                "chars": len(doc.text),
            }
            for doc in docs
        ],
    )
    type_counts = Counter(row["type"] for row in rows)
    edge_counts = Counter(row["type"] for row in edges)
    lines = [
        "# Semantic Graphify",
        "",
        f"- 생성일: {date.today().isoformat()}",
        f"- 처리 문서: {len(docs)}",
        f"- 의미 노드: {len(rows)}",
        f"- 의미 관계: {len(edges)}",
        f"- LLM provider/model: {status.get('provider')}/{status.get('model')}",
        f"- LLM status: {status.get('status', status.get('mode'))}",
        f"- LLM completed outputs: {status.get('completed_outputs', 0)}",
        "",
        "## Node Types",
        "",
    ]
    lines.extend(f"- {key}: {value}" for key, value in sorted(type_counts.items()))
    lines.extend(["", "## Edge Types", ""])
    lines.extend(f"- {key}: {value}" for key, value in sorted(edge_counts.items()))
    lines.extend(["", "## Ontology", ""])
    lines.extend(f"- {value}" for value in sorted(SEMANTIC_NODE_TYPES))
    (GRAPH_DIR / "semantic_README.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    (GRAPH_DIR / "semantic_status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")


def update_graph_readme() -> None:
    readme = GRAPH_DIR / "README.md"
    extra = "\n\n## Semantic Graphify\n\n- semantic_nodes.jsonl\n- semantic_edges.jsonl\n- semantic_documents.jsonl\n- semantic_README.md\n"
    if not readme.exists():
        readme.write_text("# Graphify 결과" + extra, encoding="utf-8")
        return
    text = readme.read_text(encoding="utf-8", errors="replace")
    if "## Semantic Graphify" not in text:
        readme.write_text(text.rstrip() + extra, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collections", nargs="*", default=None, help="collection names to process; default is all")
    parser.add_argument("--max-chars", type=int, default=6500, help="max characters per document sent to LLM")
    parser.add_argument("--max-files", type=int, default=0, help="limit files for smoke tests; 0 means all")
    parser.add_argument("--llm-mode", choices=["auto", "sync", "batch", "none"], default="auto")
    parser.add_argument("--wait-batch", action="store_true")
    args = parser.parse_args()

    collections = set(args.collections) if args.collections else None
    docs = iter_source_docs(collections, args.max_chars)
    if args.max_files > 0:
        docs = docs[: args.max_files]

    nodes, edges = heuristic_extract(docs)
    llm_nodes, llm_edges, status = llm_extract(docs, args.llm_mode, args.wait_batch)
    for key, value in llm_nodes.items():
        if key in nodes:
            nodes[key]["properties"].update(value.get("properties", {}))
        else:
            nodes[key] = value
    edges.extend(llm_edges)

    GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    write_outputs(nodes, edges, docs, status)
    update_graph_readme()
    print(
        "semantic graphify done: "
        f"docs={len(docs)} nodes={len(nodes)} edges={len(dedupe_edges(edges))} "
        f"status={status.get('status', status.get('mode'))} dir={GRAPH_DIR}"
    )


if __name__ == "__main__":
    main()
