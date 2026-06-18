# System Patterns

## Repository Pattern

This repository is a starter template. Keep shared scaffolding clear and avoid coupling all future projects to one application architecture.

Recommended template structure:

```text
AGENTS.md
README.md
llms.txt
docs/
  conventions/
  llm-wiki.md
memory-bank/
.ai-worklog/
adr/
prompts/
```

Project-specific repositories may add runtime folders such as `src/`, `app/`, `packages/`, `tests/`, or deployment configuration after the architecture is known.

## Documentation Pattern

- Keep `README.md` human-oriented and concise.
- Keep `AGENTS.md` focused on agent operating rules and memory routing.
- Keep durable project context in `memory-bank/`.
- Keep chronological session records in `.ai-worklog/`.
- Keep decision records in `adr/`.
- Keep reusable prompts in `prompts/`.

## Project Management Pattern

- Separate facts, assumptions, decisions, risks, blockers, and open questions.
- Do not mark work done unless completion evidence exists.
- Use `TBD` instead of inventing owners, dates, or commitments.
- Record important decisions when they happen.
- Update `activeContext.md` and `progress.md` after meaningful progress.

## Development Conventions

- Read `docs/conventions/general.md` before broad changes.
- Read `docs/conventions/react.md` before React or TypeScript UI changes.
- Read `docs/conventions/python.md` before Python changes.
- Read `docs/conventions/langgraph.md` before LangGraph or agent orchestration changes.
- Prefer the receiving project's existing structure when this template is applied to a non-empty project.
- Add dependencies only when the benefit is clear and documented.

## Graphify Pattern

- Use `.graphifyignore` to keep generated and irrelevant paths out of graph inputs.
- Read `graphify-out/GRAPH_REPORT.md` before broad analysis when it exists.
- Treat missing or stale Graphify output as untrusted until regenerated.
