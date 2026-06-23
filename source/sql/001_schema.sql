-- Woori Financial PoC offline PostgreSQL schema.
-- Target: PostgreSQL 15+
-- Optional: pgvector is supported when installed, but the schema also works without it.

BEGIN;

CREATE SCHEMA IF NOT EXISTS woori_poc;
SET search_path TO woori_poc, public;

CREATE EXTENSION IF NOT EXISTS pg_trgm;

DO $$
BEGIN
  CREATE EXTENSION IF NOT EXISTS vector;
EXCEPTION
  WHEN undefined_file THEN
    RAISE NOTICE 'pgvector is not installed. woori_poc.search_embedding.embedding_jsonb will still be usable.';
END $$;

CREATE TABLE IF NOT EXISTS collection (
  collection_id bigserial PRIMARY KEY,
  name text NOT NULL UNIQUE,
  path text NOT NULL UNIQUE,
  has_index boolean NOT NULL DEFAULT false,
  has_readme boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS source_document (
  document_id text PRIMARY KEY,
  collection_name text NOT NULL REFERENCES collection(name) ON UPDATE CASCADE,
  title text,
  document_type text,
  source_url text,
  source_date text,
  data_path text,
  index_path text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_source_document_collection ON source_document(collection_name);
CREATE INDEX IF NOT EXISTS ix_source_document_path ON source_document(data_path);
CREATE INDEX IF NOT EXISTS ix_source_document_metadata ON source_document USING gin (metadata);
CREATE INDEX IF NOT EXISTS ix_source_document_title_trgm ON source_document USING gin (title gin_trgm_ops);

CREATE TABLE IF NOT EXISTS source_file (
  file_id bigserial PRIMARY KEY,
  collection_name text NOT NULL REFERENCES collection(name) ON UPDATE CASCADE,
  data_path text NOT NULL UNIQUE,
  extension text,
  is_binary boolean NOT NULL DEFAULT false,
  size_bytes bigint,
  sha256 text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_source_file_collection ON source_file(collection_name);
CREATE INDEX IF NOT EXISTS ix_source_file_path_trgm ON source_file USING gin (data_path gin_trgm_ops);

CREATE TABLE IF NOT EXISTS wiki_page (
  page_id bigserial PRIMARY KEY,
  page_name text NOT NULL UNIQUE,
  artifact_path text NOT NULL UNIQUE,
  content text NOT NULL,
  content_tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', coalesce(content, ''))) STORED,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_wiki_page_tsv ON wiki_page USING gin (content_tsv);
CREATE INDEX IF NOT EXISTS ix_wiki_page_content_trgm ON wiki_page USING gin (content gin_trgm_ops);

CREATE TABLE IF NOT EXISTS graph_node (
  node_id text PRIMARY KEY,
  label text NOT NULL,
  node_type text NOT NULL,
  properties jsonb NOT NULL DEFAULT '{}'::jsonb,
  artifact_path text NOT NULL DEFAULT 'graph/nodes.jsonl',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_graph_node_type ON graph_node(node_type);
CREATE INDEX IF NOT EXISTS ix_graph_node_label_trgm ON graph_node USING gin (label gin_trgm_ops);
CREATE INDEX IF NOT EXISTS ix_graph_node_properties ON graph_node USING gin (properties);

CREATE TABLE IF NOT EXISTS graph_edge (
  edge_pk bigserial PRIMARY KEY,
  source_node_id text NOT NULL,
  target_node_id text NOT NULL,
  edge_type text NOT NULL,
  properties jsonb NOT NULL DEFAULT '{}'::jsonb,
  artifact_path text NOT NULL DEFAULT 'graph/edges.jsonl',
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source_node_id, target_node_id, edge_type, properties)
);

CREATE INDEX IF NOT EXISTS ix_graph_edge_source ON graph_edge(source_node_id);
CREATE INDEX IF NOT EXISTS ix_graph_edge_target ON graph_edge(target_node_id);
CREATE INDEX IF NOT EXISTS ix_graph_edge_type ON graph_edge(edge_type);
CREATE INDEX IF NOT EXISTS ix_graph_edge_properties ON graph_edge USING gin (properties);

CREATE TABLE IF NOT EXISTS semantic_node (
  node_id text PRIMARY KEY,
  label text NOT NULL,
  node_type text NOT NULL CHECK (
    node_type IN (
      'Document',
      'AuditFinding',
      'Risk',
      'FailureMode',
      'Control',
      'RegulationTopic',
      'Remediation',
      'Evidence'
    )
  ),
  description text,
  mentions integer,
  confidence numeric(5,4),
  source text,
  properties jsonb NOT NULL DEFAULT '{}'::jsonb,
  artifact_path text NOT NULL DEFAULT 'graph/semantic_nodes.jsonl',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_semantic_node_type ON semantic_node(node_type);
CREATE INDEX IF NOT EXISTS ix_semantic_node_label_trgm ON semantic_node USING gin (label gin_trgm_ops);
CREATE INDEX IF NOT EXISTS ix_semantic_node_properties ON semantic_node USING gin (properties);

CREATE TABLE IF NOT EXISTS semantic_edge (
  edge_pk bigserial PRIMARY KEY,
  source_node_id text NOT NULL,
  target_node_id text NOT NULL,
  edge_type text NOT NULL CHECK (
    edge_type IN (
      'MENTIONS_RISK',
      'EVIDENCES_FAILURE',
      'INCREASES_RISK',
      'MITIGATES',
      'DETECTS',
      'REQUIRES_CONTROL',
      'SUPPORTS_REMEDIATION',
      'RELATED_TO_TOPIC',
      'HAS_EVIDENCE'
    )
  ),
  evidence text,
  data_path text,
  confidence numeric(5,4),
  source text,
  properties jsonb NOT NULL DEFAULT '{}'::jsonb,
  artifact_path text NOT NULL DEFAULT 'graph/semantic_edges.jsonl',
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source_node_id, target_node_id, edge_type, coalesce(data_path, ''), coalesce(evidence, ''))
);

CREATE INDEX IF NOT EXISTS ix_semantic_edge_source ON semantic_edge(source_node_id);
CREATE INDEX IF NOT EXISTS ix_semantic_edge_target ON semantic_edge(target_node_id);
CREATE INDEX IF NOT EXISTS ix_semantic_edge_type ON semantic_edge(edge_type);
CREATE INDEX IF NOT EXISTS ix_semantic_edge_path ON semantic_edge(data_path);
CREATE INDEX IF NOT EXISTS ix_semantic_edge_evidence_trgm ON semantic_edge USING gin (evidence gin_trgm_ops);
CREATE INDEX IF NOT EXISTS ix_semantic_edge_properties ON semantic_edge USING gin (properties);

CREATE TABLE IF NOT EXISTS semantic_document (
  document_id text PRIMARY KEY,
  title text,
  collection_name text NOT NULL REFERENCES collection(name) ON UPDATE CASCADE,
  data_path text NOT NULL UNIQUE,
  chars integer,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_semantic_document_collection ON semantic_document(collection_name);
CREATE INDEX IF NOT EXISTS ix_semantic_document_path ON semantic_document(data_path);

CREATE TABLE IF NOT EXISTS llm_insight (
  collection_name text PRIMARY KEY REFERENCES collection(name) ON UPDATE CASCADE,
  document_count integer,
  insight jsonb NOT NULL DEFAULT '{}'::jsonb,
  artifact_path text NOT NULL DEFAULT 'graph/llm_insights.jsonl',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS search_chunk (
  chunk_id integer PRIMARY KEY,
  area text NOT NULL CHECK (area IN ('data', 'artifacts')),
  artifact_or_data_path text NOT NULL,
  chunk_index integer NOT NULL,
  content text NOT NULL,
  content_tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', coalesce(content, ''))) STORED,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS ix_search_chunk_path ON search_chunk(artifact_or_data_path);
CREATE INDEX IF NOT EXISTS ix_search_chunk_tsv ON search_chunk USING gin (content_tsv);
CREATE INDEX IF NOT EXISTS ix_search_chunk_content_trgm ON search_chunk USING gin (content gin_trgm_ops);

CREATE TABLE IF NOT EXISTS bm25_index (
  chunk_id integer PRIMARY KEY REFERENCES search_chunk(chunk_id) ON DELETE CASCADE,
  doc_length integer NOT NULL,
  term_freq jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS bm25_config (
  config_id boolean PRIMARY KEY DEFAULT true CHECK (config_id),
  k1 numeric NOT NULL,
  b numeric NOT NULL,
  avgdl numeric NOT NULL,
  total_docs integer NOT NULL,
  doc_freq jsonb NOT NULL DEFAULT '{}'::jsonb,
  loaded_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS embedding_config (
  config_id boolean PRIMARY KEY DEFAULT true CHECK (config_id),
  model text NOT NULL,
  dimension integer NOT NULL,
  chunk_chars integer,
  chunk_overlap integer,
  batch_size integer,
  chunks integer,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  loaded_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS search_embedding (
  chunk_id integer PRIMARY KEY REFERENCES search_chunk(chunk_id) ON DELETE CASCADE,
  model text NOT NULL,
  dimension integer NOT NULL,
  embedding_jsonb jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
    EXECUTE 'ALTER TABLE woori_poc.search_embedding ADD COLUMN IF NOT EXISTS embedding_vector vector(1536)';
    EXECUTE 'CREATE INDEX IF NOT EXISTS ix_search_embedding_vector_cosine ON woori_poc.search_embedding USING ivfflat (embedding_vector vector_cosine_ops) WITH (lists = 100)';
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS llm_batch_job (
  job_name text PRIMARY KEY,
  batch_id text,
  provider text,
  model text,
  status text,
  input_file_id text,
  output_file_id text,
  request_total integer,
  request_completed integer,
  request_failed integer,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  loaded_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS load_audit (
  load_id bigserial PRIMARY KEY,
  artifact_name text NOT NULL,
  row_count integer NOT NULL,
  loaded_at timestamptz NOT NULL DEFAULT now(),
  notes text
);

COMMIT;
