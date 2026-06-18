# Active Context

## Current Goal

Maintain a filtered Korean legal corpus focused on financial industry, internal control, compliance, duties/accountability, and governance, with AX2 project template scaffolding applied.

## Current State

- The upstream `legalize-kr/legalize-kr` repository was cloned into `legalize-kr`.
- Unrelated `kr/` law folders were removed.
- `kr/` currently contains 25 selected law folders and 55 markdown files.
- AX2 project template files were copied in, excluding the template `.git` directory.
- README, LLM entrypoint, and memory-bank core context were adjusted for this filtered corpus.

## Recently Completed

- Filtered the upstream legal corpus by deleting unrelated folders after full clone.
- Applied AX2 project template structure:
  - `AGENTS.md`
  - `llms.txt`
  - `docs/`
  - `memory-bank/`
  - `.ai-worklog/`
  - `adr/`
  - `prompts/`
  - `.graphifyignore`

## In Progress

- None.

## Next Steps

- Review the remaining `kr/` folder list before committing.
- Decide whether to add a machine-readable manifest of selected laws.
- Decide whether to normalize metadata for search, graph ingestion, or RAG indexing.

## Open Questions

- Whether the filter should include only explicit internal-control/compliance/accountability references or also adjacent financial-sector laws.
- Whether to preserve upstream Git history or convert this into a new project repository.

## Next Prompt

Read `README.md`, `AGENTS.md`, `memory-bank/activeContext.md`, and `memory-bank/progress.md`. Preserve the selected `kr/` corpus unless explicitly asked to re-filter it.
