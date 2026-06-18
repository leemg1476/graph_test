# Product Context

## Users / Stakeholders

- Analysts working with Korean financial regulation.
- AI agents preparing summaries, knowledge graphs, or retrieval indexes.
- Developers building downstream tooling on top of this legal corpus.

## Business Context

The repository narrows a broad Korean law corpus into a focused finance-governance dataset. This reduces noise for analysis involving internal control, compliance, duty allocation, governance, and accountability in financial institutions.

## Key Workflows

- Inspect selected laws under `kr/`.
- Search for financial governance concepts across the corpus.
- Add worklogs and ADRs when filter rules or downstream processing choices change.
- Use `memory-bank/` to preserve project scope and context across AI sessions.

## Domain Constraints

- Legal text must be traceable to the upstream source.
- Filtering changes should be explained in durable project memory.
- Avoid adding unrelated legal domains unless the user explicitly broadens scope.
- Do not store sensitive or private data.

## Open Questions

- Whether to create a manifest with source path, law name, file count, and inclusion rationale.
- Whether to split 법률, 시행령, 시행규칙 files into structured chunks for retrieval.
