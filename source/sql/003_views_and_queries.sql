-- Views and query helpers matching the MCP/agent read patterns.

BEGIN;
SET search_path TO woori_poc, public;

CREATE OR REPLACE VIEW v_semantic_graph_search AS
SELECT
  n.node_id,
  n.node_type,
  n.label,
  n.description,
  n.properties,
  coalesce(
    jsonb_agg(DISTINCT e.data_path) FILTER (WHERE e.data_path IS NOT NULL),
    '[]'::jsonb
  ) AS related_paths
FROM semantic_node n
LEFT JOIN semantic_edge e
  ON e.source_node_id = n.node_id OR e.target_node_id = n.node_id
GROUP BY n.node_id, n.node_type, n.label, n.description, n.properties;

CREATE OR REPLACE VIEW v_audit_risk_map AS
SELECT
  finding.node_id AS finding_id,
  finding.label AS finding,
  risk.node_id AS risk_id,
  risk.label AS risk,
  failure.node_id AS failure_mode_id,
  failure.label AS failure_mode,
  control.node_id AS control_id,
  control.label AS control,
  remediation.node_id AS remediation_id,
  remediation.label AS remediation,
  edge_finding_risk.data_path AS data_path,
  edge_finding_risk.evidence AS evidence
FROM semantic_node finding
LEFT JOIN semantic_edge edge_finding_risk
  ON edge_finding_risk.source_node_id = finding.node_id
 AND edge_finding_risk.edge_type = 'MENTIONS_RISK'
LEFT JOIN semantic_node risk
  ON risk.node_id = edge_finding_risk.target_node_id
LEFT JOIN semantic_edge edge_failure_risk
  ON edge_failure_risk.target_node_id = risk.node_id
 AND edge_failure_risk.edge_type = 'INCREASES_RISK'
LEFT JOIN semantic_node failure
  ON failure.node_id = edge_failure_risk.source_node_id
LEFT JOIN semantic_edge edge_control_risk
  ON edge_control_risk.target_node_id = risk.node_id
 AND edge_control_risk.edge_type = 'MITIGATES'
LEFT JOIN semantic_node control
  ON control.node_id = edge_control_risk.source_node_id
LEFT JOIN semantic_edge edge_remediation_finding
  ON edge_remediation_finding.target_node_id = finding.node_id
 AND edge_remediation_finding.edge_type = 'SUPPORTS_REMEDIATION'
LEFT JOIN semantic_node remediation
  ON remediation.node_id = edge_remediation_finding.source_node_id
WHERE finding.node_type = 'AuditFinding';

CREATE OR REPLACE VIEW v_document_evidence AS
SELECT
  d.document_id,
  d.collection_name,
  d.data_path,
  d.title,
  e.edge_type,
  e.evidence,
  e.source_node_id,
  src.label AS source_label,
  src.node_type AS source_type,
  e.target_node_id,
  tgt.label AS target_label,
  tgt.node_type AS target_type
FROM semantic_document d
JOIN semantic_edge e
  ON e.data_path = d.data_path
LEFT JOIN semantic_node src ON src.node_id = e.source_node_id
LEFT JOIN semantic_node tgt ON tgt.node_id = e.target_node_id;

COMMIT;

-- Example semantic graph search.
-- SELECT *
-- FROM v_semantic_graph_search
-- WHERE label ILIKE '%계좌%' OR description ILIKE '%계좌%'
-- ORDER BY node_type, label
-- LIMIT 20;

-- Example audit risk map.
-- SELECT finding, risk, failure_mode, control, remediation, data_path
-- FROM v_audit_risk_map
-- WHERE finding ILIKE '%계좌%'
-- LIMIT 20;

-- Example full text search over chunks.
-- SELECT area, artifact_or_data_path, chunk_index, ts_rank(content_tsv, plainto_tsquery('simple', '내부통제 계좌개설')) AS rank, left(content, 500) AS snippet
-- FROM search_chunk
-- WHERE content_tsv @@ plainto_tsquery('simple', '내부통제 계좌개설')
-- ORDER BY rank DESC
-- LIMIT 10;
