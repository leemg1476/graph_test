# Project Management System Import

## Date

2026-05-26

## Goal

Port only project-management skills and operating features from `ra-agent-template` into `ax2-project-template`, excluding agent-development framework code.

## Context Read

- `ra-agent-template-source/AGENTS.md`
- `ra-agent-template-source/memory-bank/*.md`
- `ra-agent-template-source/.ai-worklog/_template.md`
- `ra-agent-template-source/prompts/session-start.md`
- `ra-agent-template-source/docs/llm-wiki.md`
- `ax2-project-template/AGENTS.md`
- `ax2-project-template/README.md`

## Files Changed

- `AGENTS.md`: added repository memory protocol and session start/close rules.
- `README.md`: documented project-management assets now included in the template.
- `llms.txt`: added short LLM entrypoint.
- `docs/llm-wiki.md`: added agent-readable project management wiki.
- `memory-bank/`: initialized reusable project memory files.
- `.ai-worklog/`: initialized worklog index and templates.
- `adr/0000-template.md`: added ADR template.
- `prompts/`: added session start and close prompts.
- `.graphifyignore`: added Graphify ignore rules.

## Decisions

- Decision: Do not copy `src/`, `tests/`, `pyproject.toml`, Docker files, or agent/MCP runtime README content.
- Rationale: The target repository is a general AX2 project template; the user requested project-management features only.
- Impact: The template gets reusable management workflow without coupling new projects to the agent framework implementation.

## Tests / Validation

- Command: `git diff --stat`
- Result: Pending in this session.
- Notes: Documentation-only change; no application build is expected.

## Security / Redaction Notes

No secrets, tokens, raw incident logs, or customer-sensitive values were added.

## Remaining TODOs

- TODO: Project teams should replace placeholder owners, validation commands, and project-specific context after creating a new repository.
- Owner: TBD
- Status: todo

## Next Prompt

Read `AGENTS.md`, `memory-bank/activeContext.md`, `memory-bank/progress.md`, and `.ai-worklog/index.md`. Then classify the next request, inspect the directly relevant files, and update the memory files after meaningful progress.
