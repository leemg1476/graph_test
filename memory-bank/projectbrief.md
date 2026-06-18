# Project Brief

## Project Name

legalize-kr finance governance subset

## Purpose

Create a focused local corpus from `legalize-kr/legalize-kr` containing only Korean legal documents relevant to financial industry regulation, internal control, compliance, duties/accountability, and governance.

## Scope

- Preserve selected legal markdown files under `kr/`.
- Keep AX2 project-management scaffolding for future AI-assisted analysis.
- Track project context in `memory-bank/`.
- Use `.ai-worklog/` for session history and `adr/` for hard-to-reverse decisions.
- Support future downstream work such as summarization, Graphify ingestion, RAG indexing, or compliance-domain extraction.

## Non-Goals

- Do not build an application runtime in this step.
- Do not keep unrelated Korean law folders from the upstream corpus.
- Do not store secrets, raw transcripts, internal URLs, customer-sensitive data, or raw incident logs.

## Success Criteria

- The repository contains the filtered legal corpus and template management files.
- Future agents can understand the dataset scope from `README.md`, `llms.txt`, and `memory-bank/`.
- The selected legal corpus remains easy to inspect and extend.
