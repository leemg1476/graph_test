# Progress

## Done

- Cloned `legalize-kr/legalize-kr`.
- Removed unrelated `kr/` law folders after full clone.
- Kept 25 selected law folders and 55 markdown files.
- Removed the earlier temporary `legalize-kr-filtered` attempt.
- Cloned `financial-ai-data-business/ax2-project-template` separately.
- Applied the AX2 template structure to this repository, excluding the template `.git`.
- Updated `README.md`, `llms.txt`, and core memory-bank documents for this project.
- Added Docker Compose for Postgres + Apache AGE.
- Added Postgres schema for documents, chunks, graph extraction mirror tables, audit findings, and cosine similarity.
- Added Python chunking, ingestion, Qwen/vLLM LLM config, graph extraction, and ReAct audit agent modules.
- Verified Docker container health and ingested 55 documents into 1,520 chunks.
- Added unit tests for chunking, Qwen/vLLM config, graph extraction helpers, and ReAct tool loop.
- Switched graph extraction to async LLM calls with configurable concurrency.
- Ran a 100 chunk extraction with concurrency 20. Current graph extraction state: 101 chunks processed, 1,003 entities, 1,265 mirror edges, and AGE graph rebuilt to 1,003 vertices / 1,265 edges.

## In Progress

- None.

## Blocked

- None.

## Deferred

- Re-run or repair 9 chunks whose Qwen responses were not valid JSON and were stored as fallback failure payloads.
- Continue full LLM graph extraction in batches after reviewing extraction quality.
- Add a selected-law manifest.
- Add automated validation for the filter criteria.

## Milestones

- 2026-06-18: Filtered Korean legal corpus for finance/internal-control/compliance/accountability scope.
- 2026-06-18: Applied AX2 project template scaffolding.
