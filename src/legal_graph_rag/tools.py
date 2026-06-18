from __future__ import annotations

import re

from .config import Settings
from .db import connect
from .embedding import HashingEmbedder


TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]{2,}")
GENERIC_TERMS = {
    "대한",
    "관련",
    "사항",
    "경우",
    "업무",
    "회사",
    "금융",
    "법률",
    "시행령",
    "규정",
    "기준",
    "관리",
    "보고",
}
RELATION_PRIORITY = {"CHANGED_TO": 3, "COMBINES_TO": 2, "RELATED_TO": 1}
TOKEN_RE = re.compile(r"[0-9A-Za-z\uac00-\ud7a3]{2,}")
GENERIC_TERMS = {
    "\ub300\ud55c",
    "\uad00\ub828",
    "\uc0ac\ud56d",
    "\uacbd\uc6b0",
    "\uc5c5\ubb34",
    "\ud68c\uc0ac",
    "\uae08\uc735",
    "\ubc95\ub960",
    "\uc2dc\ud589\ub839",
    "\uaddc\uc815",
    "\uae30\uc900",
    "\uad00\ub9ac",
    "\ubcf4\uace0",
    "\uc704\uc6d0\ud68c",
}


def vector_search(query: str, k: int = 5, settings: Settings | None = None) -> list[dict]:
    cfg = settings or Settings()
    embedding = HashingEmbedder(cfg.embed_dim).embed(query)
    with connect(cfg) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, law_name, doc_type, source_path, heading, text,
                       cosine_similarity(embedding, %s) AS score
                FROM legal_chunks
                ORDER BY score DESC
                LIMIT %s
                """,
                (embedding, k),
            )
            return list(cur.fetchall())


def _normalize_key(value: str) -> str:
    return re.sub(r"[^0-9a-z\uac00-\ud7a3]+", "", value.lower())


def _query_terms(query: str) -> list[str]:
    seen: set[str] = set()
    terms: list[str] = []
    for token in TOKEN_RE.findall(query):
        normalized = _normalize_key(token)
        if len(normalized) < 2 or normalized in seen or normalized in GENERIC_TERMS:
            continue
        seen.add(normalized)
        terms.append(token)
    return sorted(terms, key=len, reverse=True)[:12]


def _dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def _entity_seed_text(row: dict) -> str:
    aliases = " ".join(row.get("aliases") or [])
    return " ".join(
        str(value or "")
        for value in [
            row.get("name"),
            row.get("canonical_name"),
            aliases,
            row.get("entity_type"),
            row.get("description"),
        ]
    )


def _lexical_seed_score(row: dict, normalized_terms: list[str], terms: list[str]) -> float:
    aliases = row.get("aliases") or []
    alias_keys = row.get("alias_keys") or []
    names = [row.get("name") or "", row.get("canonical_name") or "", *aliases]
    normalized_names = [_normalize_key(name) for name in names]
    score = 0.0
    if any(term in normalized_names or term in alias_keys for term in normalized_terms):
        score += 0.08
    if any(any(term and term in name for name in normalized_names) for term in normalized_terms):
        score += 0.04
    if any(term in (row.get("description") or "") for term in terms):
        score += 0.015
    return score


def _rank_seed_entities(
    entities: list[dict],
    query: str,
    terms: list[str],
    *,
    dim: int,
    limit: int,
) -> list[dict]:
    embedder = HashingEmbedder(dim)
    query_embedding = embedder.embed(query)
    normalized_terms = [_normalize_key(term) for term in terms]
    ranked: list[dict] = []
    for row in entities:
        entity_embedding = embedder.embed(_entity_seed_text(row))
        vector_score = _dot(query_embedding, entity_embedding)
        lexical_score = _lexical_seed_score(row, normalized_terms, terms)
        scored = dict(row)
        scored["vector_score"] = vector_score
        scored["lexical_score"] = lexical_score
        scored["score"] = vector_score + lexical_score
        aliases = scored.get("aliases") or []
        scored["matched_alias"] = aliases[0] if aliases else scored.get("canonical_name") or scored.get("name")
        ranked.append(scored)
    ranked.sort(key=lambda row: (row["score"], row["vector_score"]), reverse=True)
    return [row for row in ranked if row["score"] > 0][:limit]


def graph_search(query: str, k: int = 10, settings: Settings | None = None) -> list[dict]:
    cfg = settings or Settings()
    terms = _query_terms(query)
    if not terms:
        terms = [query[:20]]
    like_params: list[str] = []
    for term in terms:
        pattern = f"%{term}%"
        like_params.extend([pattern, pattern])
    with connect(cfg) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.id, e.name, e.canonical_name, e.canonical_key, e.entity_type,
                       e.description, e.source_chunk_id,
                       COALESCE(array_agg(DISTINCT a.alias) FILTER (WHERE a.alias IS NOT NULL), '{}') AS aliases,
                       COALESCE(array_agg(DISTINCT a.alias_key) FILTER (WHERE a.alias_key IS NOT NULL), '{}') AS alias_keys
                FROM graph_entities e
                LEFT JOIN graph_entity_aliases a ON a.entity_id = e.id
                GROUP BY e.id, e.name, e.canonical_name, e.canonical_key, e.entity_type,
                         e.description, e.source_chunk_id
                """,
            )
            all_entities = list(cur.fetchall())
            linked_entities = _rank_seed_entities(
                all_entities,
                query,
                terms,
                dim=cfg.embed_dim,
                limit=max(k, 10),
            )
            linked_ids = [row["id"] for row in linked_entities]

            fallback_entities: list[dict] = []
            if not linked_ids:
                entity_clauses = " OR ".join(["e.name ILIKE %s OR e.description ILIKE %s"] * len(terms))
                cur.execute(
                    f"""
                    SELECT e.id, e.name, e.canonical_name, e.canonical_key,
                           e.entity_type, e.description, e.source_chunk_id,
                           NULL AS matched_alias, 10 AS score
                    FROM graph_entities e
                    WHERE {entity_clauses}
                    ORDER BY e.id
                    LIMIT %s
                    """,
                    [*like_params, max(k, 10)],
                )
                fallback_entities = list(cur.fetchall())
                linked_entities = fallback_entities
                linked_ids = [row["id"] for row in linked_entities]

            edges: list[dict] = []
            if linked_ids:
                cur.execute(
                    """
                    WITH seed(id) AS (SELECT unnest(%s::int[])),
                    one_hop AS (
                        SELECT ge.id AS edge_id,
                               ge.source_entity_id,
                               ge.target_entity_id,
                               ge.relation_type,
                               ge.relation_group_key,
                               ge.description,
                               ge.source_chunk_id,
                               CASE WHEN ge.relation_type = 'CHANGED_TO' THEN 3
                                    WHEN ge.relation_type = 'COMBINES_TO' THEN 2
                                    ELSE 1 END AS relation_rank,
                               1 AS hop
                        FROM graph_edges ge
                        JOIN seed s ON s.id IN (ge.source_entity_id, ge.target_entity_id)
                    ),
                    two_hop AS (
                        SELECT ge.id AS edge_id,
                               ge.source_entity_id,
                               ge.target_entity_id,
                               ge.relation_type,
                               ge.relation_group_key,
                               ge.description,
                               ge.source_chunk_id,
                               CASE WHEN ge.relation_type = 'CHANGED_TO' THEN 3
                                    WHEN ge.relation_type = 'COMBINES_TO' THEN 2
                                    ELSE 1 END AS relation_rank,
                               2 AS hop
                        FROM graph_edges ge
                        JOIN one_hop oh
                          ON oh.source_entity_id IN (ge.source_entity_id, ge.target_entity_id)
                          OR oh.target_entity_id IN (ge.source_entity_id, ge.target_entity_id)
                        WHERE ge.id <> oh.edge_id
                    ),
                    selected AS (
                        SELECT DISTINCT ON (edge_id) *
                        FROM (
                            SELECT * FROM one_hop
                            UNION ALL
                            SELECT * FROM two_hop
                        ) x
                        ORDER BY edge_id, hop, relation_rank DESC
                    )
                    SELECT se.name AS source,
                           se.canonical_name AS source_canonical_name,
                           se.entity_type AS source_type,
                           s.relation_type,
                           te.name AS target,
                           te.canonical_name AS target_canonical_name,
                           te.entity_type AS target_type,
                           s.relation_group_key,
                           s.description,
                           s.source_chunk_id,
                           s.hop,
                           s.relation_rank
                    FROM selected s
                    JOIN graph_entities se ON se.id = s.source_entity_id
                    JOIN graph_entities te ON te.id = s.target_entity_id
                    ORDER BY s.hop, s.relation_rank DESC, s.edge_id
                    LIMIT %s
                    """,
                    (linked_ids, max(k, 10)),
                )
                edges = list(cur.fetchall())

            chunk_ids = sorted(
                {
                    row.get("source_chunk_id")
                    for row in [*linked_entities, *edges]
                    if row.get("source_chunk_id") is not None
                }
            )[: max(k, 10)]
            chunks_by_id: dict[int, dict] = {}
            if chunk_ids:
                cur.execute(
                    """
                    SELECT id, law_name, doc_type, heading, left(text, 700) AS text_preview
                    FROM legal_chunks
                    WHERE id = ANY(%s)
                    """,
                    (chunk_ids,),
                )
                chunks_by_id = {row["id"]: row for row in cur.fetchall()}

    results: list[dict] = []
    for row in linked_entities[: max(3, k // 2)]:
        chunk = chunks_by_id.get(row["source_chunk_id"])
        results.append(
            {
                "kind": "linked_entity",
                "id": row["id"],
                "name": row["name"],
                "canonical_name": row.get("canonical_name") or row["name"],
                "entity_type": row["entity_type"],
                "description": row["description"],
                "source_chunk_id": row["source_chunk_id"],
                "matched_alias": row.get("matched_alias"),
                "link_score": float(row.get("score") or 0),
                "vector_score": float(row.get("vector_score") or 0),
                "lexical_score": float(row.get("lexical_score") or 0),
                "chunk": chunk,
            }
        )
    for row in edges[:k]:
        chunk = chunks_by_id.get(row["source_chunk_id"])
        results.append(
            {
                "kind": "edge_path",
                "source": row["source"],
                "source_canonical_name": row["source_canonical_name"],
                "source_type": row["source_type"],
                "relation_type": row["relation_type"],
                "target": row["target"],
                "target_canonical_name": row["target_canonical_name"],
                "target_type": row["target_type"],
                "relation_group_key": row["relation_group_key"],
                "description": row["description"],
                "source_chunk_id": row["source_chunk_id"],
                "hop": row["hop"],
                "relation_priority": RELATION_PRIORITY.get(row["relation_type"], 0),
                "chunk": chunk,
            }
        )
    return results[: k + max(3, k // 2)]


def graph_context_search(query: str, k: int = 10, settings: Settings | None = None) -> list[dict]:
    return graph_search(query, k, settings)


def _legacy_graph_search(query: str, k: int = 10, settings: Settings | None = None) -> list[dict]:
    cfg = settings or Settings()
    terms = _query_terms(query)
    if not terms:
        terms = [query[:20]]
    entity_clauses = " OR ".join(["e.name ILIKE %s OR e.description ILIKE %s"] * len(terms))
    source_clauses = " OR ".join(["se.name ILIKE %s OR se.description ILIKE %s"] * len(terms))
    target_clauses = " OR ".join(["te.name ILIKE %s OR te.description ILIKE %s"] * len(terms))
    term_params: list[str] = []
    for term in terms:
        pattern = f"%{term}%"
        term_params.extend([pattern, pattern])
    with connect(cfg) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT e.id, e.name, e.entity_type, e.description, e.source_chunk_id
                FROM graph_entities e
                WHERE {entity_clauses}
                ORDER BY e.id
                LIMIT %s
                """,
                [*term_params, k],
            )
            entities = list(cur.fetchall())

            cur.execute(
                f"""
                SELECT se.name AS source, ge.relation_type, te.name AS target,
                       ge.description, ge.source_chunk_id
                FROM graph_edges ge
                JOIN graph_entities se ON se.id = ge.source_entity_id
                JOIN graph_entities te ON te.id = ge.target_entity_id
                WHERE {source_clauses} OR {target_clauses}
                ORDER BY ge.id
                LIMIT %s
                """,
                [*term_params, *term_params, k],
            )
            edges = list(cur.fetchall())
    return [{"kind": "entity", **row} for row in entities] + [{"kind": "edge", **row} for row in edges]


def get_chunk(chunk_id: int, settings: Settings | None = None) -> dict | None:
    cfg = settings or Settings()
    with connect(cfg) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, law_name, doc_type, source_path, heading, text
                FROM legal_chunks
                WHERE id = %s
                """,
                (chunk_id,),
            )
            return cur.fetchone()
