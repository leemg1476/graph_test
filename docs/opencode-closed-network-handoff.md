# Opencode Closed Network Handoff

This document is the handoff brief for an opencode agent that will continue this project in a closed-network environment.

The closed network is expected to provide production-grade internal services:

- vLLM-compatible Qwen3 embedding server
- Qwen3 reranking server
- OpenSearch
- Postgres with pgvector
- Postgres with Apache AGE
- Qwen3.6 27B FP8 or equivalent chat/extraction model

Do not assume internet access. Do not commit `.env`, API keys, internal URLs, raw chat logs, or secrets.

## Current Project State

This repository started from `legalize-kr/legalize-kr`. It has been filtered so that `kr/` only keeps finance, internal-control, compliance, and accountability related laws.

The project now contains a first-pass GraphRAG pipeline:

1. Ingest Markdown law files from `kr/`.
2. Chunk legal text into `legal_chunks`.
3. Store chunk embeddings.
4. Use an LLM to extract graph entities and edges.
5. Store graph data in relational mirror tables and Apache AGE.
6. Run a ReAct audit-finding agent that calls retrieval tools.
7. Generate basic test cases and evaluation reports.

Important current local counts:

```text
legal_documents: 55
legal_chunks: 1,520
graph_extractions: 300
graph_entities: 2,908
graph_entity_aliases: 6,841
graph_edges: 5,312

RELATED_TO: 4,505
COMBINES_TO: 506
CHANGED_TO: 301
failed_extractions: 23
bad_edges: 0
```

The counts above may change if more chunks are processed.

## Important Files

Read these first:

```text
src/legal_graph_rag/chunking.py
src/legal_graph_rag/ingest.py
src/legal_graph_rag/embedding.py
src/legal_graph_rag/graph_extract.py
src/legal_graph_rag/tools.py
src/legal_graph_rag/agent.py
src/legal_graph_rag/llm.py
src/legal_graph_rag/config.py
db/init.sql
scripts/ingest_legal_corpus.py
scripts/extract_graph.py
scripts/rebuild_age_graph.py
scripts/run_audit_agent_cases.py
scripts/evaluate_rag_quality.py
tests/
```

## Current Known Limitations

### Temporary Embeddings

`src/legal_graph_rag/embedding.py` currently uses `HashingEmbedder`, a deterministic local placeholder. It is only good enough for development tests. Replace it with the closed-network Qwen3 embedding service.

### Search Infrastructure Is Not Production-Grade

Current `vector_search` is still simple Postgres cosine search over stored vectors. In the closed network, implement proper hybrid retrieval:

- pgvector for dense semantic search
- OpenSearch for BM25 lexical search
- Qwen3 reranker for final candidate ranking

### Graph Extraction Still Has Failures

Out of 300 processed chunks, 23 fell back because the LLM output was invalid JSON. The existing code has repair retry, but it is not enough. Use structured output or stricter JSON schema handling with the closed-network Qwen3.6 model.

### Graph Search Is Improved But Still Basic

`graph_search` currently:

- extracts query terms
- uses vector similarity between the full input sentence and entity text to choose seed entities
- applies small lexical boosts for alias/name matches
- traverses 1-hop and 2-hop graph edges
- returns source chunk previews

This is better than the earlier `ILIKE` search, but it still needs real embeddings, type weighting, reranking, and path scoring.

### Evaluation Pipeline Is Present But Needs Closed-Network Judge LLM

`scripts/evaluate_rag_quality.py` contains RAGAS and DeepEval evaluation wiring. In the previous environment, the vLLM judge endpoint returned `503`, so the report produced `n/a` scores. In the closed network, rerun it against the internal judge model.

## Current Graph Model

Entities are stored with canonicalization:

```text
graph_entities
- id
- name
- canonical_name
- canonical_key
- entity_type
- description
- source_chunk_id
```

Aliases:

```text
graph_entity_aliases
- entity_id
- alias
- alias_key
- entity_type
```

Edges are limited to exactly three relation types:

```text
RELATED_TO   -- a -> b, related by requirement/supervision/reporting/obligation/basis
COMBINES_TO  -- a+b -> c, multiple sources combine into a meaningful concept/control/obligation
CHANGED_TO   -- a -> a', name/institution/article/role changed
```

`COMBINES_TO` may be extracted from multiple sources. Relational storage expands it into binary rows, grouped by `relation_group_key`.

## Target Architecture

The target retrieval flow should be:

```text
Audit finding
 -> entity mention extraction
 -> entity linking
 -> graph path retrieval
 -> legal chunk hybrid retrieval
 -> reranking
 -> graph/vector cross-check
 -> cited answer
 -> RAGAS/DeepEval quality measurement
```

The graph must not be a decorative tool. It should narrow the legal search space by finding compliance, accountability, internal-control, reporting, obligation, sanction, and change relationships.

## Priority 1: Replace Embeddings With Qwen3

Replace `HashingEmbedder` with a Qwen3 embedding client.

Requirements:

- OpenAI-compatible or internal HTTP client, depending on the closed-network server
- batch embedding
- timeout
- retry with exponential backoff
- configurable model name
- configurable embedding dimension
- deterministic error handling
- no secret logging

Recommended config keys:

```env
EMBEDDING_PROVIDER=qwen3
QWEN3_EMBEDDING_BASE_URL=http://...
QWEN3_EMBEDDING_API_KEY=...
QWEN3_EMBEDDING_MODEL=...
QWEN3_EMBEDDING_DIM=...
```

Migration target:

```sql
ALTER TABLE legal_chunks
ADD COLUMN IF NOT EXISTS embedding vector(<qwen_dim>);

ALTER TABLE graph_entities
ADD COLUMN IF NOT EXISTS embedding vector(<qwen_dim>);

-- optional
ALTER TABLE graph_entity_aliases
ADD COLUMN IF NOT EXISTS embedding vector(<qwen_dim>);
```

Use pgvector indexes:

```sql
CREATE INDEX IF NOT EXISTS legal_chunks_embedding_hnsw_idx
ON legal_chunks
USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS graph_entities_embedding_hnsw_idx
ON graph_entities
USING hnsw (embedding vector_cosine_ops);
```

If HNSW is unavailable, use IVFFLAT with an appropriate `lists` value and `ANALYZE`.

## Priority 2: Rebuild Chunk Ingestion

Update `src/legal_graph_rag/ingest.py` so ingestion does this:

1. Read `kr/**/*.md`.
2. Parse metadata and text.
3. Chunk text.
4. Batch embed chunks with Qwen3.
5. Upsert chunks into `legal_chunks`.
6. Store pgvector embeddings.

Keep source traceability:

```text
law_name
doc_type
source_path
heading
chunk_index
text
embedding
```

Add a script option:

```powershell
python scripts\ingest_legal_corpus.py --reembed
```

Expected behavior:

- Without `--reembed`, do not recompute existing embeddings unless missing.
- With `--reembed`, recompute all chunk embeddings.

## Priority 3: Add OpenSearch Indexing

Create an OpenSearch indexing script, for example:

```text
scripts/index_opensearch.py
```

Index `legal_chunks` into OpenSearch.

Recommended document:

```json
{
  "chunk_id": 123,
  "law_name": "...",
  "doc_type": "...",
  "source_path": "...",
  "heading": "...",
  "text": "...",
  "metadata": {
    "entity_types": [],
    "law_category": "finance"
  }
}
```

Use Korean analyzer if available. If not, start with default analyzer plus exact keyword fields.

Required functions:

- create index if missing
- bulk index
- delete stale docs
- health check

Recommended config:

```env
OPENSEARCH_URL=http://...
OPENSEARCH_USER=...
OPENSEARCH_PASSWORD=...
OPENSEARCH_INDEX_LEGAL_CHUNKS=legal_chunks
```

## Priority 4: Hybrid Retrieval With Reranker

Update `vector_search` in `src/legal_graph_rag/tools.py`. It should become a hybrid legal retrieval tool.

Recommended flow:

1. Embed query with Qwen3 embedding.
2. Query pgvector top 30.
3. Query OpenSearch BM25 top 30.
4. Merge by `chunk_id`.
5. Send merged candidates to Qwen3 reranker.
6. Return final top k.

Return shape:

```json
{
  "chunk_id": 123,
  "law_name": "...",
  "doc_type": "...",
  "heading": "...",
  "text": "...",
  "dense_score": 0.82,
  "bm25_score": 13.2,
  "rerank_score": 0.91
}
```

Recommended reranker config:

```env
RERANK_PROVIDER=qwen3
QWEN3_RERANK_BASE_URL=http://...
QWEN3_RERANK_API_KEY=...
QWEN3_RERANK_MODEL=...
```

If the reranker API accepts pairs:

```text
query: audit finding or graph-guided legal query
document: chunk heading + chunk text
```

If it accepts listwise inputs, pass query and candidate list.

## Priority 5: Entity Embeddings And Entity Linking

The first seed entity should be found by vector similarity between the input sentence and graph entity text.

Current implementation already does this with `HashingEmbedder`. Replace that with Qwen3 embeddings and pgvector.

Entity text should be:

```text
name + canonical_name + aliases + entity_type + description
```

Candidate generation should combine:

1. pgvector entity top k
2. alias exact match
3. alias normalized match
4. OpenSearch entity index BM25, optional
5. deterministic keyword fallback

Candidate reranking should use Qwen3 reranker:

```text
query: full audit finding
candidate: entity text
```

Recommended seed selection:

```text
top 3 to 5 entities
minimum score threshold
type priority boost
```

Suggested entity type priority:

```text
법령_조항
내부통제기준
준법감시인
책무
감사위원회
이사회
위험관리
금융회사
감독기관
제재
보고
Concept
```

Entity linking score:

```text
entity_score =
  entity_vector_score * 0.55
+ rerank_score * 0.30
+ alias_exact_boost * 0.10
+ entity_type_boost * 0.05
```

Do not use pairwise entity matching across all existing entities during ingestion. Canonical key and alias indexes should remain the deduplication mechanism.

## Priority 6: Graph Path Retrieval

Improve `graph_search` beyond the current 1-hop/2-hop traversal.

Requirements:

- Use linked seed entities.
- Retrieve 1-hop and 2-hop paths.
- Group `COMBINES_TO` rows by `relation_group_key`.
- Attach source chunk text or preview.
- Penalize paths without source chunks.
- Rerank graph paths against the audit finding.

Path score:

```text
path_score =
  seed_entity_score * 0.35
+ edge_type_score * 0.15
+ source_chunk_rerank_score * 0.30
+ path_coherence_score * 0.20
```

Edge type score:

```text
CHANGED_TO: 0.90
COMBINES_TO: 0.85
RELATED_TO: 0.60
```

Return shape:

```json
{
  "kind": "edge_path",
  "source": "...",
  "relation_type": "COMBINES_TO",
  "target": "...",
  "hop": 1,
  "path_score": 0.82,
  "source_chunk_id": 123,
  "chunk": {
    "law_name": "...",
    "heading": "...",
    "text": "..."
  }
}
```

For `COMBINES_TO`, return grouped form where possible:

```json
{
  "kind": "combine_path",
  "sources": ["a", "b"],
  "relation_type": "COMBINES_TO",
  "target": "c",
  "relation_group_key": "...",
  "source_chunk_id": 123
}
```

## Priority 7: Graph Extraction Improvements

Update `src/legal_graph_rag/graph_extract.py` to use the closed-network Qwen3.6 27B FP8 model.

Config:

```env
activate_model_name=vllm
VLLM_BASE_URL=http://...
VLLM_API_KEY=...
VLLM_MODEL_NAME=Qwen/Qwen3.6-27B-FP8
VLLM_ENABLE_THINKING=false
```

Extraction constraints:

- Return JSON only.
- Enforce schema.
- Limit entities per chunk.
- Limit edges per chunk.
- Do not invent edges if relation is weak.
- Allow only `RELATED_TO`, `COMBINES_TO`, `CHANGED_TO`.

Recommended per-chunk limits:

```text
entities: max 20
edges: max 30
```

Retry policy:

1. first extraction
2. JSON parse
3. if failed, repair prompt
4. if still failed, store fallback with structured failure reason

Add failure fields if possible:

```text
graph_extractions.status
graph_extractions.error_type
graph_extractions.error_message
```

Then reprocess failed chunks:

```powershell
python scripts\extract_graph.py --failed-only --concurrency 20
```

If `--failed-only` does not exist yet, implement it.

## Priority 8: Agent Improvements

The current ReAct agent is in `src/legal_graph_rag/agent.py`.

It has tools:

```text
graph_search
vector_search
get_chunk
final_answer
```

Keep this principle:

- Use graph first to identify entities and legal relationships.
- Use vector/hybrid search to retrieve legal text.
- Use source chunks to ground graph paths.
- If graph and source law conflict, trust source law.

The final answer must include citations.

Recommended output structure:

```text
1. 핵심 판단
2. 관련 법령/조항 근거
3. graph에서 확인된 entity-edge 관계
4. 내부통제상 결함
5. 개선 조치
6. 확인 필요 사항
```

Citation format:

```text
[금융지주회사법 제XX조, chunk_id=123]
```

Avoid uncited legal assertions.

If graph result is weak, say so explicitly:

```text
그래프에서는 직접적인 준법감시인-감사위원회 보고 edge가 약하게 검색되었으므로, 최종 판단은 법령 원문 chunk를 우선 근거로 삼았다.
```

## Priority 9: Evaluation

RAGAS and DeepEval evaluation wiring exists in:

```text
scripts/evaluate_rag_quality.py
```

Run it after the closed-network judge model is configured:

```powershell
python scripts\evaluate_rag_quality.py
```

Evaluate at least:

RAGAS:

```text
faithfulness
answer_relevancy
llm_context_precision_without_reference
context_recall, after golden answers are available
```

DeepEval:

```text
AnswerRelevancyMetric
FaithfulnessMetric
ContextualRelevancyMetric
ContextualPrecisionMetric
GEval custom metric
```

Create 10 to 20 golden answers. The current 5 audit cases are useful smoke tests but are not enough for quality claims.

Suggested custom GEval criteria:

```text
- legal basis accuracy
- citation correctness
- internal-control recommendation specificity
- graph context usage
- hallucination penalty
- answer structure quality
```

## Current Test Commands

Run before and after changes:

```powershell
python -m pytest tests -q
python -m compileall src scripts tests
```

Current expected result:

```text
10 passed
compileall success
```

## Recommended Closed-Network Work Order

Follow this order:

1. Confirm Postgres, Apache AGE, pgvector, OpenSearch, vLLM, embedding, reranker endpoints.
2. Add config keys without exposing secrets.
3. Implement Qwen3 embedding client.
4. Add pgvector schema migration.
5. Reingest or reembed all 1,520 chunks.
6. Generate and store entity embeddings.
7. Implement OpenSearch chunk indexing.
8. Implement hybrid retrieval and reranking.
9. Replace current seed entity ranking with pgvector entity search plus reranker.
10. Improve graph path scoring and `COMBINES_TO` grouping.
11. Reprocess failed graph extractions.
12. Expand graph extraction from 300 chunks to all 1,520 chunks.
13. Improve ReAct agent citations.
14. Re-run 5 smoke test cases.
15. Build 10 to 20 golden cases.
16. Run RAGAS and DeepEval.
17. Write final quality report.

## Quality Targets

Initial acceptable targets:

```text
graph extraction failure rate: < 3%
bad edge type count: 0
answer citation coverage: > 90%
RAGAS faithfulness: > 0.75
RAGAS answer relevancy: > 0.75
DeepEval faithfulness: > 0.75
DeepEval contextual relevancy: > 0.75
```

These are starting targets, not final production thresholds.

## Operational Notes

- Do not run destructive git commands.
- Do not revert the filtered `kr/` directory.
- Do not commit `.env`.
- Use `scripts/rebuild_age_graph.py` if AGE graph count diverges from mirror tables.
- Use `scripts/reset_graph_data.py` only when intentionally clearing generated graph data.
- Keep migrations idempotent.
- Keep all generated reports under `reports/`.
- Keep handoff/progress notes under `docs/` or `memory-bank/`.

## Immediate Next Step

Start by replacing the embedding layer.

The current `HashingEmbedder` is the biggest blocker because it affects:

- chunk search quality
- seed entity linking quality
- graph path relevance
- RAGAS/DeepEval context quality

After Qwen3 embedding and pgvector are working, re-run:

```powershell
python scripts\ingest_legal_corpus.py --reembed
python scripts\run_audit_agent_cases.py
python scripts\evaluate_rag_quality.py
```

Then inspect:

```text
reports/audit_agent_report.md
reports/rag_quality_eval.md
```
