from __future__ import annotations

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from psycopg import sql
from pydantic import BaseModel, Field, ValidationError

from .config import Settings
from .db import connect, prepare_age
from .llm import make_chat_model, resolve_llm_config


ENTITY_TYPE_RE = re.compile(r"[^A-Za-z0-9_가-힣]")
ENTITY_KEY_RE = re.compile(r"[^0-9a-z가-힣]+")
ALLOWED_EDGE_TYPES = {"RELATED_TO", "COMBINES_TO", "CHANGED_TO"}


class ExtractedEntity(BaseModel):
    name: str = Field(min_length=1)
    canonical_name: str | None = None
    aliases: list[str] = Field(default_factory=list)
    type: str = Field(default="Concept")
    description: str = ""


class ExtractedEdge(BaseModel):
    source: str | list[str]
    target: str
    type: str = "RELATED_TO"
    description: str = ""


class ExtractionPayload(BaseModel):
    entities: list[ExtractedEntity] = Field(default_factory=list)
    edges: list[ExtractedEdge] = Field(default_factory=list)


EXTRACTION_PROMPT = """\
다음 한국 금융 법령 chunk에서 지식그래프에 넣을 entity와 edge를 추출하라.

규칙:
- entity는 금융회사, 기관, 임원, 위원회, 내부통제기준, 준법감시인, 책무, 의무, 제재, 보고, 승인, 감독기관, 법령 조항 등으로 제한한다.
- entity는 canonical_name과 aliases를 포함한다. canonical_name은 같은 대상의 대표명이고 aliases는 약칭/띄어쓰기/법령명 변형이다.
- edge type은 다음 3가지만 허용한다.
  - RELATED_TO: a->b 관련 있음, 요구/감독/보고/근거/적용/위반/책임 관계 포함
  - COMBINES_TO: a+b->c 병합하면 의미 있는 상위 개념/요건/통제/책무가 됨. source는 문자열 배열로 작성
  - CHANGED_TO: a->a' 명칭, 제도, 조항, 역할 등이 변경됨
- 반드시 JSON만 출력한다.
- 형식: {{"entities":[{{"name":"...","canonical_name":"...","aliases":["..."],"type":"...","description":"..."}}],"edges":[{{"source":"... 또는 문자열 배열","target":"...","type":"RELATED_TO|COMBINES_TO|CHANGED_TO","description":"..."}}]}}

[법령]
law_name: {law_name}
doc_type: {doc_type}
heading: {heading}
chunk_id: {chunk_id}

{text}
"""


REPAIR_PROMPT = """\
다음 출력은 JSON 파싱에 실패했다. 의미를 유지하되 아래 schema에 맞는 유효한 JSON만 다시 출력하라.

허용 edge type은 RELATED_TO, COMBINES_TO, CHANGED_TO 세 가지뿐이다.
schema:
{{"entities":[{{"name":"...","canonical_name":"...","aliases":["..."],"type":"...","description":"..."}}],"edges":[{{"source":"... 또는 문자열 배열","target":"...","type":"RELATED_TO|COMBINES_TO|CHANGED_TO","description":"..."}}]}}

[원본 출력]
{raw}
"""


@dataclass(frozen=True)
class ChunkExtractionResult:
    chunk_id: int
    payload: ExtractionPayload


def _json_from_text(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end >= start:
        cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)


def _safe_label(value: str, fallback: str = "Entity") -> str:
    label = ENTITY_TYPE_RE.sub("_", value).strip("_")
    return label or fallback


def _normalize_key(value: str) -> str:
    normalized = ENTITY_KEY_RE.sub("", value.lower())
    for suffix in ("주식회사", "회사", "법률", "시행령", "시행규칙"):
        if len(normalized) > len(suffix) + 2 and normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
    return normalized or value.strip().lower()


def _canonical_name(entity: ExtractedEntity) -> str:
    return (entity.canonical_name or entity.name).strip()


def _canonical_key(value: str, entity_type: str) -> str:
    base = f"{_safe_label(entity_type)}:{_normalize_key(value)}"
    digest = hashlib.blake2b(base.encode("utf-8"), digest_size=12).hexdigest()
    return f"{_safe_label(entity_type)}:{digest}"


def _edge_sources(edge: ExtractedEdge) -> list[str]:
    if isinstance(edge.source, list):
        return [source for source in edge.source if source.strip()]
    return [edge.source]


def _relation_group_key(
    source_entity_ids: list[int],
    target_entity_id: int,
    relation_type: str,
    chunk_id: int,
) -> str:
    raw = f"{relation_type}:{chunk_id}:{','.join(map(str, sorted(source_entity_ids)))}->{target_entity_id}"
    return hashlib.blake2b(raw.encode("utf-8"), digest_size=12).hexdigest()


def _safe_edge_type(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_]", "_", value.upper()).strip("_")
    return normalized if normalized in ALLOWED_EDGE_TYPES else "RELATED_TO"


def _cypher_quote(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _run_cypher(conn, graph_name: str, cypher: str) -> None:
    if "$cypher$" in cypher:
        cypher = cypher.replace("$cypher$", "")
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("SELECT * FROM cypher({}, $cypher${}$cypher$) AS (v agtype)").format(
                sql.Literal(graph_name),
                sql.SQL(cypher),
            )
        )


def _upsert_graph_payload(conn, graph_name: str, chunk_id: int, payload: ExtractionPayload) -> None:
    entity_ids_by_name: dict[str, int] = {}
    entity_labels_by_name: dict[str, str] = {}
    entity_canonical_by_name: dict[str, str] = {}
    entity_key_by_name: dict[str, str] = {}
    with conn.cursor() as cur:
        for entity in payload.entities:
            entity_type = _safe_label(entity.type)
            canonical_name = _canonical_name(entity)
            canonical_key = _canonical_key(canonical_name, entity_type)
            aliases = sorted({entity.name, canonical_name, *entity.aliases})
            cur.execute(
                """
                INSERT INTO graph_entities (
                    name, canonical_name, canonical_key, entity_type, description, source_chunk_id
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (canonical_key, entity_type) DO UPDATE
                SET description = COALESCE(NULLIF(EXCLUDED.description, ''), graph_entities.description)
                RETURNING id
                """,
                (canonical_name, canonical_name, canonical_key, entity_type, entity.description, chunk_id),
            )
            entity_id = cur.fetchone()["id"]
            for alias in aliases:
                alias_key = _normalize_key(alias)
                cur.execute(
                    """
                    INSERT INTO graph_entity_aliases (entity_id, alias, alias_key, entity_type)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (alias_key, entity_type) DO UPDATE
                    SET entity_id = EXCLUDED.entity_id,
                        alias = EXCLUDED.alias
                    """,
                    (entity_id, alias, alias_key, entity_type),
                )
                entity_ids_by_name[alias] = entity_id
                entity_labels_by_name.setdefault(alias, entity_type)
                entity_canonical_by_name.setdefault(alias, canonical_name)
                entity_key_by_name.setdefault(alias, canonical_key)
            entity_ids_by_name[entity.name] = entity_id
            entity_ids_by_name[canonical_name] = entity_id
            entity_labels_by_name.setdefault(entity.name, entity_type)
            entity_labels_by_name.setdefault(canonical_name, entity_type)
            entity_canonical_by_name.setdefault(entity.name, canonical_name)
            entity_canonical_by_name.setdefault(canonical_name, canonical_name)
            entity_key_by_name.setdefault(entity.name, canonical_key)
            entity_key_by_name.setdefault(canonical_name, canonical_key)
            cypher = (
                f"MERGE (n:{entity_type} {{canonical_key: {_cypher_quote(canonical_key)}}}) "
                f"SET n.name = {_cypher_quote(canonical_name)}, "
                f"n.canonical_name = {_cypher_quote(canonical_name)}, "
                f"n.description = {_cypher_quote(entity.description)}, "
                f"n.source_chunk_id = {chunk_id}"
            )
            _run_cypher(conn, graph_name, cypher)

        for edge in payload.edges:
            source_names = _edge_sources(edge)
            source_ids = [entity_ids_by_name[name] for name in source_names if name in entity_ids_by_name]
            target_id = entity_ids_by_name.get(edge.target)
            if not source_ids or target_id is None:
                continue
            source_label_by_source = {
                name: entity_labels_by_name.get(name) for name in source_names if name in entity_ids_by_name
            }
            target_label = entity_labels_by_name.get(edge.target)
            target_key = entity_key_by_name.get(edge.target)
            if not target_label:
                continue
            relation_type = _safe_edge_type(edge.type)
            group_key = _relation_group_key(source_ids, target_id, relation_type, chunk_id)
            for source_name in source_names:
                source_id = entity_ids_by_name.get(source_name)
                source_label = source_label_by_source.get(source_name)
                source_key = entity_key_by_name.get(source_name)
                if source_id is None or not source_label or not source_key or not target_key:
                    continue
                cur.execute(
                    """
                    INSERT INTO graph_edges (
                        source_entity_id, target_entity_id, relation_type,
                        relation_group_key, description, source_chunk_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (source_id, target_id, relation_type, group_key, edge.description, chunk_id),
                )
                cypher = (
                    f"MATCH (s:{source_label} {{canonical_key: {_cypher_quote(source_key)}}}), "
                    f"(t:{target_label} {{canonical_key: {_cypher_quote(target_key)}}}) "
                    f"MERGE (s)-[r:{relation_type} {{source_chunk_id: {chunk_id}, relation_group_key: {_cypher_quote(group_key)}}}]->(t) "
                    f"SET r.description = {_cypher_quote(edge.description)}, "
                    f"r.source_names = {_cypher_quote(json.dumps(source_names, ensure_ascii=False))}"
                )
                _run_cypher(conn, graph_name, cypher)


def _load_pending_chunks(cfg: Settings, model_name: str, limit: int | None) -> list[dict[str, Any]]:
    with connect(cfg) as conn:
        prepare_age(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.id, c.id AS chunk_id, c.law_name, c.doc_type, c.heading, c.text
                FROM legal_chunks c
                LEFT JOIN graph_extractions gx
                  ON gx.chunk_id = c.id AND gx.model_name = %s
                WHERE gx.id IS NULL
                ORDER BY c.id
                LIMIT %s
                """,
                (model_name, limit),
            )
            return list(cur.fetchall())


def _parse_extraction_payload(raw: str) -> ExtractionPayload:
    return ExtractionPayload.model_validate(_json_from_text(raw))


def _fallback_payload(chunk: dict[str, Any], exc: Exception) -> ExtractionPayload:
    return ExtractionPayload(
        entities=[
            ExtractedEntity(
                name=chunk["law_name"],
                canonical_name=chunk["law_name"],
                aliases=[],
                type="Law",
                description=f"Extraction failed: {type(exc).__name__}: {exc}",
            )
        ],
        edges=[],
    )


async def _extract_one_async(llm: Any, chunk: dict[str, Any]) -> ChunkExtractionResult:
    prompt = EXTRACTION_PROMPT.format(**chunk)
    try:
        response = await llm.ainvoke(prompt)
        raw = response.content if isinstance(response.content, str) else json.dumps(response.content)
        try:
            payload = _parse_extraction_payload(raw)
        except (json.JSONDecodeError, ValidationError):
            repair_prompt = REPAIR_PROMPT.format(raw=raw)
            repair_response = await llm.ainvoke(repair_prompt)
            repaired = (
                repair_response.content
                if isinstance(repair_response.content, str)
                else json.dumps(repair_response.content)
            )
            try:
                payload = _parse_extraction_payload(repaired)
            except (json.JSONDecodeError, ValidationError) as repair_exc:
                payload = _fallback_payload(chunk, repair_exc)
    except Exception as exc:
        payload = _fallback_payload(chunk, exc)
    return ChunkExtractionResult(chunk_id=int(chunk["id"]), payload=payload)


async def _extract_chunks_async(
    chunks: list[dict[str, Any]],
    *,
    concurrency: int,
) -> list[ChunkExtractionResult]:
    llm = make_chat_model(temperature=0, max_tokens=8192, enable_thinking=False)
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def run_with_limit(chunk: dict[str, Any]) -> ChunkExtractionResult:
        async with semaphore:
            return await _extract_one_async(llm, chunk)

    return await asyncio.gather(*(run_with_limit(chunk) for chunk in chunks))


def _write_extraction_results(
    cfg: Settings,
    model_name: str,
    results: list[ChunkExtractionResult],
) -> dict[str, int]:
    processed = 0
    extracted_entities = 0
    extracted_edges = 0
    with connect(cfg) as conn:
        prepare_age(conn)
        for result in results:
            payload = result.payload
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO graph_extractions (chunk_id, model_name, raw_json)
                    VALUES (%s, %s, %s::jsonb)
                    ON CONFLICT (chunk_id, model_name) DO UPDATE
                    SET raw_json = EXCLUDED.raw_json
                    """,
                    (result.chunk_id, model_name, payload.model_dump_json()),
                )
            _upsert_graph_payload(conn, cfg.graph_name, result.chunk_id, payload)
            processed += 1
            extracted_entities += len(payload.entities)
            extracted_edges += len(payload.edges)

    return {"chunks": processed, "entities": extracted_entities, "edges": extracted_edges}


async def extract_and_load_async(
    limit: int | None = None,
    *,
    concurrency: int = 20,
    settings: Settings | None = None,
) -> dict[str, int]:
    cfg = settings or Settings()
    model_name = str(resolve_llm_config()["model"])
    chunks = _load_pending_chunks(cfg, model_name, limit)
    if not chunks:
        return {"chunks": 0, "entities": 0, "edges": 0}
    results = await _extract_chunks_async(chunks, concurrency=concurrency)
    return _write_extraction_results(cfg, model_name, results)


def extract_and_load(
    limit: int | None = None,
    *,
    concurrency: int = 20,
    settings: Settings | None = None,
) -> dict[str, int]:
    return asyncio.run(
        extract_and_load_async(limit=limit, concurrency=concurrency, settings=settings)
    )
