-- DML loader for generated JSONL artifacts.
-- Run with psql from the PoC root or edit the \copy file paths below.
--
-- Example:
--   psql "postgresql://user:pass@host:5432/db" -v ON_ERROR_STOP=1 -f source/sql/001_schema.sql
--   psql "postgresql://user:pass@host:5432/db" -v ON_ERROR_STOP=1 -f source/sql/002_load_artifacts.sql
--
-- This script assumes these files exist under the current working directory:
--   data/* indexes are represented by graph/search artifacts
--   artifacts/graph/nodes.jsonl
--   artifacts/graph/edges.jsonl
--   artifacts/graph/documents.jsonl
--   artifacts/graph/llm_insights.jsonl
--   artifacts/graph/semantic_nodes.jsonl
--   artifacts/graph/semantic_edges.jsonl
--   artifacts/graph/semantic_documents.jsonl
--   artifacts/search/chunks.jsonl
--   artifacts/search/bm25_index.json
--   artifacts/search/embedding_config.json
--   artifacts/graph/semantic_status.json

\set ON_ERROR_STOP on

BEGIN;
SET search_path TO woori_poc, public;

CREATE TEMP TABLE stg_jsonl(raw text) ON COMMIT DROP;
CREATE TEMP TABLE stg_one(raw jsonb) ON COMMIT DROP;
CREATE TEMP TABLE stg_text(line text) ON COMMIT DROP;

TRUNCATE TABLE
  search_embedding,
  bm25_index,
  bm25_config,
  search_chunk,
  llm_insight,
  semantic_edge,
  semantic_node,
  semantic_document,
  graph_edge,
  graph_node,
  source_document,
  source_file,
  wiki_page,
  collection,
  llm_batch_job
RESTART IDENTITY CASCADE;

-- Wiki pages. psql \copy reads lines; aggregate them back into a page body.
TRUNCATE stg_text;
\copy stg_text(line) FROM 'artifacts/wiki/index.md'

INSERT INTO wiki_page(page_name, artifact_path, content, metadata)
SELECT
  'index.md',
  'wiki/index.md',
  string_agg(line, E'\n' ORDER BY ctid),
  jsonb_build_object('source', 'artifacts/wiki/index.md')
FROM stg_text
ON CONFLICT (page_name) DO UPDATE
SET content = excluded.content,
    metadata = excluded.metadata,
    updated_at = now();

TRUNCATE stg_text;
\copy stg_text(line) FROM 'artifacts/wiki/감사원_적극행정_감사사례.md'

INSERT INTO wiki_page(page_name, artifact_path, content, metadata)
SELECT
  '감사원_적극행정_감사사례.md',
  'wiki/감사원_적극행정_감사사례.md',
  string_agg(line, E'\n' ORDER BY ctid),
  jsonb_build_object('source', 'artifacts/wiki/감사원_적극행정_감사사례.md')
FROM stg_text
ON CONFLICT (page_name) DO UPDATE
SET content = excluded.content,
    metadata = excluded.metadata,
    updated_at = now();

TRUNCATE stg_text;
\copy stg_text(line) FROM 'artifacts/wiki/금융감독_제재검사_내부통제자료.md'

INSERT INTO wiki_page(page_name, artifact_path, content, metadata)
SELECT
  '금융감독_제재검사_내부통제자료.md',
  'wiki/금융감독_제재검사_내부통제자료.md',
  string_agg(line, E'\n' ORDER BY ctid),
  jsonb_build_object('source', 'artifacts/wiki/금융감독_제재검사_내부통제자료.md')
FROM stg_text
ON CONFLICT (page_name) DO UPDATE
SET content = excluded.content,
    metadata = excluded.metadata,
    updated_at = now();

TRUNCATE stg_text;
\copy stg_text(line) FROM 'artifacts/wiki/금융감독원_감독규정시행세칙.md'

INSERT INTO wiki_page(page_name, artifact_path, content, metadata)
SELECT
  '금융감독원_감독규정시행세칙.md',
  'wiki/금융감독원_감독규정시행세칙.md',
  string_agg(line, E'\n' ORDER BY ctid),
  jsonb_build_object('source', 'artifacts/wiki/금융감독원_감독규정시행세칙.md')
FROM stg_text
ON CONFLICT (page_name) DO UPDATE
SET content = excluded.content,
    metadata = excluded.metadata,
    updated_at = now();

TRUNCATE stg_text;
\copy stg_text(line) FROM 'artifacts/wiki/법제처_법령해석례.md'

INSERT INTO wiki_page(page_name, artifact_path, content, metadata)
SELECT
  '법제처_법령해석례.md',
  'wiki/법제처_법령해석례.md',
  string_agg(line, E'\n' ORDER BY ctid),
  jsonb_build_object('source', 'artifacts/wiki/법제처_법령해석례.md')
FROM stg_text
ON CONFLICT (page_name) DO UPDATE
SET content = excluded.content,
    metadata = excluded.metadata,
    updated_at = now();

-- Collections are inferred from semantic_documents and metadata documents.
TRUNCATE stg_jsonl;
\copy stg_jsonl(raw) FROM 'artifacts/graph/semantic_documents.jsonl'

INSERT INTO collection(name, path, has_index, has_readme)
SELECT DISTINCT
  raw_json->>'collection' AS name,
  raw_json->>'collection' AS path,
  true,
  true
FROM (SELECT raw::jsonb AS raw_json FROM stg_jsonl WHERE btrim(raw) <> '') s
WHERE raw_json ? 'collection'
ON CONFLICT (name) DO UPDATE
SET has_index = excluded.has_index,
    has_readme = excluded.has_readme;

TRUNCATE stg_jsonl;
\copy stg_jsonl(raw) FROM 'artifacts/graph/documents.jsonl'

INSERT INTO collection(name, path, has_index, has_readme)
SELECT DISTINCT
  raw_json->>'collection' AS name,
  raw_json->>'collection' AS path,
  true,
  true
FROM (SELECT raw::jsonb AS raw_json FROM stg_jsonl WHERE btrim(raw) <> '') s
WHERE raw_json ? 'collection'
ON CONFLICT (name) DO NOTHING;

INSERT INTO source_document(
  document_id,
  collection_name,
  title,
  document_type,
  source_url,
  source_date,
  data_path,
  index_path,
  metadata
)
SELECT
  raw_json->>'id',
  raw_json->>'collection',
  raw_json->>'title',
  raw_json->>'document_type',
  raw_json->>'source_url',
  raw_json->>'date',
  raw_json->>'path',
  raw_json->>'_index',
  raw_json
FROM (SELECT raw::jsonb AS raw_json FROM stg_jsonl WHERE btrim(raw) <> '') s
WHERE raw_json ? 'id'
ON CONFLICT (document_id) DO UPDATE
SET collection_name = excluded.collection_name,
    title = excluded.title,
    document_type = excluded.document_type,
    source_url = excluded.source_url,
    source_date = excluded.source_date,
    data_path = excluded.data_path,
    index_path = excluded.index_path,
    metadata = excluded.metadata;

INSERT INTO load_audit(artifact_name, row_count, notes)
SELECT 'graph/documents.jsonl', count(*), 'metadata graph documents'
FROM stg_jsonl;

-- Metadata graph nodes.
TRUNCATE stg_jsonl;
\copy stg_jsonl(raw) FROM 'artifacts/graph/nodes.jsonl'

INSERT INTO graph_node(node_id, label, node_type, properties, artifact_path)
SELECT
  raw_json->>'id',
  raw_json->>'label',
  raw_json->>'type',
  coalesce(raw_json->'properties', '{}'::jsonb),
  'graph/nodes.jsonl'
FROM (SELECT raw::jsonb AS raw_json FROM stg_jsonl WHERE btrim(raw) <> '') s
WHERE raw_json ? 'id'
ON CONFLICT (node_id) DO UPDATE
SET label = excluded.label,
    node_type = excluded.node_type,
    properties = excluded.properties;

INSERT INTO load_audit(artifact_name, row_count, notes)
SELECT 'graph/nodes.jsonl', count(*), 'metadata graph nodes'
FROM stg_jsonl;

-- Metadata graph edges.
TRUNCATE stg_jsonl;
\copy stg_jsonl(raw) FROM 'artifacts/graph/edges.jsonl'

INSERT INTO graph_edge(source_node_id, target_node_id, edge_type, properties, artifact_path)
SELECT
  raw_json->>'source',
  raw_json->>'target',
  raw_json->>'type',
  coalesce(raw_json->'properties', '{}'::jsonb),
  'graph/edges.jsonl'
FROM (SELECT raw::jsonb AS raw_json FROM stg_jsonl WHERE btrim(raw) <> '') s
WHERE raw_json ? 'source' AND raw_json ? 'target'
ON CONFLICT DO NOTHING;

INSERT INTO load_audit(artifact_name, row_count, notes)
SELECT 'graph/edges.jsonl', count(*), 'metadata graph edges'
FROM stg_jsonl;

-- LLM collection insights.
TRUNCATE stg_jsonl;
\copy stg_jsonl(raw) FROM 'artifacts/graph/llm_insights.jsonl'

INSERT INTO llm_insight(collection_name, document_count, insight, artifact_path)
SELECT
  raw_json->>'collection',
  nullif(raw_json->>'document_count', '')::integer,
  coalesce(raw_json->'llm', raw_json),
  'graph/llm_insights.jsonl'
FROM (SELECT raw::jsonb AS raw_json FROM stg_jsonl WHERE btrim(raw) <> '') s
WHERE raw_json ? 'collection'
ON CONFLICT (collection_name) DO UPDATE
SET document_count = excluded.document_count,
    insight = excluded.insight;

INSERT INTO load_audit(artifact_name, row_count, notes)
SELECT 'graph/llm_insights.jsonl', count(*), 'collection-level LLM insights'
FROM stg_jsonl;

-- Semantic documents.
TRUNCATE stg_jsonl;
\copy stg_jsonl(raw) FROM 'artifacts/graph/semantic_documents.jsonl'

INSERT INTO semantic_document(document_id, title, collection_name, data_path, chars, metadata)
SELECT
  raw_json->>'id',
  raw_json->>'title',
  raw_json->>'collection',
  raw_json->>'path',
  nullif(raw_json->>'chars', '')::integer,
  raw_json
FROM (SELECT raw::jsonb AS raw_json FROM stg_jsonl WHERE btrim(raw) <> '') s
WHERE raw_json ? 'id'
ON CONFLICT (document_id) DO UPDATE
SET title = excluded.title,
    collection_name = excluded.collection_name,
    data_path = excluded.data_path,
    chars = excluded.chars,
    metadata = excluded.metadata;

INSERT INTO load_audit(artifact_name, row_count, notes)
SELECT 'graph/semantic_documents.jsonl', count(*), 'semantic graph documents'
FROM stg_jsonl;

-- Semantic nodes.
TRUNCATE stg_jsonl;
\copy stg_jsonl(raw) FROM 'artifacts/graph/semantic_nodes.jsonl'

INSERT INTO semantic_node(
  node_id,
  label,
  node_type,
  description,
  mentions,
  confidence,
  source,
  properties,
  artifact_path
)
SELECT
  raw_json->>'id',
  raw_json->>'label',
  raw_json->>'type',
  coalesce(raw_json#>>'{properties,description}', raw_json#>>'{properties,descriptions,0}'),
  nullif(raw_json#>>'{properties,mentions}', '')::integer,
  nullif(raw_json#>>'{properties,confidence}', '')::numeric,
  raw_json#>>'{properties,source}',
  coalesce(raw_json->'properties', '{}'::jsonb),
  'graph/semantic_nodes.jsonl'
FROM (SELECT raw::jsonb AS raw_json FROM stg_jsonl WHERE btrim(raw) <> '') s
WHERE raw_json ? 'id'
ON CONFLICT (node_id) DO UPDATE
SET label = excluded.label,
    node_type = excluded.node_type,
    description = excluded.description,
    mentions = excluded.mentions,
    confidence = excluded.confidence,
    source = excluded.source,
    properties = excluded.properties;

INSERT INTO load_audit(artifact_name, row_count, notes)
SELECT 'graph/semantic_nodes.jsonl', count(*), 'semantic graph nodes'
FROM stg_jsonl;

-- Semantic edges.
TRUNCATE stg_jsonl;
\copy stg_jsonl(raw) FROM 'artifacts/graph/semantic_edges.jsonl'

INSERT INTO semantic_edge(
  source_node_id,
  target_node_id,
  edge_type,
  evidence,
  data_path,
  confidence,
  source,
  properties,
  artifact_path
)
SELECT
  raw_json->>'source',
  raw_json->>'target',
  raw_json->>'type',
  raw_json#>>'{properties,evidence}',
  raw_json#>>'{properties,path}',
  nullif(raw_json#>>'{properties,confidence}', '')::numeric,
  raw_json#>>'{properties,source}',
  coalesce(raw_json->'properties', '{}'::jsonb),
  'graph/semantic_edges.jsonl'
FROM (SELECT raw::jsonb AS raw_json FROM stg_jsonl WHERE btrim(raw) <> '') s
WHERE raw_json ? 'source' AND raw_json ? 'target'
ON CONFLICT DO NOTHING;

INSERT INTO load_audit(artifact_name, row_count, notes)
SELECT 'graph/semantic_edges.jsonl', count(*), 'semantic graph edges'
FROM stg_jsonl;

-- Search chunks.
TRUNCATE stg_jsonl;
\copy stg_jsonl(raw) FROM 'artifacts/search/chunks.jsonl'

INSERT INTO search_chunk(chunk_id, area, artifact_or_data_path, chunk_index, content, metadata)
SELECT
  (raw_json->>'id')::integer,
  raw_json->>'area',
  raw_json->>'path',
  (raw_json->>'chunk_index')::integer,
  raw_json->>'text',
  raw_json - 'text'
FROM (SELECT raw::jsonb AS raw_json FROM stg_jsonl WHERE btrim(raw) <> '') s
ON CONFLICT (chunk_id) DO UPDATE
SET area = excluded.area,
    artifact_or_data_path = excluded.artifact_or_data_path,
    chunk_index = excluded.chunk_index,
    content = excluded.content,
    metadata = excluded.metadata;

INSERT INTO load_audit(artifact_name, row_count, notes)
SELECT 'search/chunks.jsonl', count(*), 'BM25/vector search chunks'
FROM stg_jsonl;

-- BM25 index: one JSON file containing global config and per-chunk term frequencies.
TRUNCATE stg_text;
TRUNCATE stg_one;
\copy stg_text(line) FROM 'artifacts/search/bm25_index.json'

INSERT INTO stg_one(raw)
SELECT string_agg(line, E'\n' ORDER BY ctid)::jsonb
FROM stg_text;

INSERT INTO bm25_config(config_id, k1, b, avgdl, total_docs, doc_freq)
SELECT
  true,
  (raw->>'k1')::numeric,
  (raw->>'b')::numeric,
  (raw->>'avgdl')::numeric,
  (raw->>'total_docs')::integer,
  raw->'doc_freq'
FROM stg_one
ON CONFLICT (config_id) DO UPDATE
SET k1 = excluded.k1,
    b = excluded.b,
    avgdl = excluded.avgdl,
    total_docs = excluded.total_docs,
    doc_freq = excluded.doc_freq,
    loaded_at = now();

INSERT INTO bm25_index(chunk_id, doc_length, term_freq)
SELECT
  ordinality::integer - 1 AS chunk_id,
  (raw->'doc_lengths'->>(ordinality::integer - 1))::integer AS doc_length,
  term_freq
FROM stg_one
CROSS JOIN LATERAL jsonb_array_elements(raw->'term_freqs') WITH ORDINALITY AS tf(term_freq, ordinality)
ON CONFLICT (chunk_id) DO UPDATE
SET doc_length = excluded.doc_length,
    term_freq = excluded.term_freq;

INSERT INTO load_audit(artifact_name, row_count, notes)
SELECT 'search/bm25_index.json', count(*), 'BM25 term frequencies'
FROM bm25_index;

-- Embedding config. Actual vectors from embeddings.npy require the companion Python loader or CSV export.
TRUNCATE stg_text;
TRUNCATE stg_one;
\copy stg_text(line) FROM 'artifacts/search/embedding_config.json'

INSERT INTO stg_one(raw)
SELECT string_agg(line, E'\n' ORDER BY ctid)::jsonb
FROM stg_text;

INSERT INTO embedding_config(
  config_id,
  model,
  dimension,
  chunk_chars,
  chunk_overlap,
  batch_size,
  chunks,
  metadata
)
SELECT
  true,
  raw->>'model',
  (raw->>'dimension')::integer,
  nullif(raw->>'chunk_chars', '')::integer,
  nullif(raw->>'chunk_overlap', '')::integer,
  nullif(raw->>'batch_size', '')::integer,
  nullif(raw->>'chunks', '')::integer,
  raw
FROM stg_one
ON CONFLICT (config_id) DO UPDATE
SET model = excluded.model,
    dimension = excluded.dimension,
    chunk_chars = excluded.chunk_chars,
    chunk_overlap = excluded.chunk_overlap,
    batch_size = excluded.batch_size,
    chunks = excluded.chunks,
    metadata = excluded.metadata,
    loaded_at = now();

-- Semantic graphify batch status.
TRUNCATE stg_text;
TRUNCATE stg_one;
\copy stg_text(line) FROM 'artifacts/graph/semantic_status.json'

INSERT INTO stg_one(raw)
SELECT string_agg(line, E'\n' ORDER BY ctid)::jsonb
FROM stg_text;

INSERT INTO llm_batch_job(
  job_name,
  batch_id,
  provider,
  model,
  status,
  input_file_id,
  output_file_id,
  request_total,
  request_completed,
  request_failed,
  metadata
)
SELECT
  coalesce(raw#>>'{metadata,job}', 'semantic_graphify'),
  raw->>'id',
  raw->>'provider',
  raw->>'model',
  raw->>'status',
  raw->>'input_file_id',
  raw->>'output_file_id',
  nullif(raw#>>'{request_counts,total}', '')::integer,
  nullif(raw#>>'{request_counts,completed}', '')::integer,
  nullif(raw#>>'{request_counts,failed}', '')::integer,
  raw
FROM stg_one
ON CONFLICT (job_name) DO UPDATE
SET batch_id = excluded.batch_id,
    provider = excluded.provider,
    model = excluded.model,
    status = excluded.status,
    input_file_id = excluded.input_file_id,
    output_file_id = excluded.output_file_id,
    request_total = excluded.request_total,
    request_completed = excluded.request_completed,
    request_failed = excluded.request_failed,
    metadata = excluded.metadata,
    loaded_at = now();

COMMIT;

ANALYZE woori_poc.collection;
ANALYZE woori_poc.source_document;
ANALYZE woori_poc.wiki_page;
ANALYZE woori_poc.graph_node;
ANALYZE woori_poc.graph_edge;
ANALYZE woori_poc.semantic_document;
ANALYZE woori_poc.semantic_node;
ANALYZE woori_poc.semantic_edge;
ANALYZE woori_poc.search_chunk;
ANALYZE woori_poc.bm25_index;
