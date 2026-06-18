# LLM Wiki

## Purpose

This wiki is the agent-readable project map for repositories created from the AX2 Project Template. It complements `README.md` for human onboarding, `AGENTS.md` for operating rules, and `memory-bank/` for long-lived project context.

## Current State

- The repository is a lightweight project template, not an application runtime.
- It provides operating rules, development conventions, project memory files, worklog templates, ADR templates, reusable prompts, and Graphify guidance.
- It intentionally does not include domain service code or agent/MCP framework implementation code.
- New projects should update the template placeholders with project-specific goals, owners, execution commands, deployment rules, and validation gates.

## Project Memory Model

Use `memory-bank/` for maintained context:

- `projectbrief.md`: goal, scope, non-goals, and success criteria.
- `productContext.md`: users, stakeholders, business workflows, and domain constraints.
- `techContext.md`: stack, environment, validation commands, and delivery constraints.
- `systemPatterns.md`: repository structure, conventions, and decision patterns.
- `activeContext.md`: current state, open questions, and next prompt.
- `progress.md`: done, in-progress, blocked, deferred, and milestone tracking.
- `knownIssues.md`: active issues and deferred observations.
- `glossary.md`: project vocabulary.

Use `.ai-worklog/` for dated session history. Use `adr/` for decisions that are hard to reverse.

## Project Management Workflow

1. Clarify the goal, scope, constraints, owner, expected output, and success criteria.
2. Separate confirmed facts, assumptions, opinions, and open questions.
3. Convert vague work into checkable tasks and milestones.
4. Track risks before they become blockers.
5. Record decisions when they are made, not after context is lost.
6. Preserve source links and evidence for important claims.
7. Close each session with current state, changed files, validation, risks, and next action.

## Development Workflow

1. Read `docs/conventions/general.md` before broad changes.
2. Read `docs/conventions/react.md` before React or TypeScript UI changes.
3. Read `docs/conventions/python.md` before Python changes.
4. Read `docs/conventions/langgraph.md` before LangGraph or agent orchestration changes.
5. Inspect directly related files, configuration, and tests before editing.
6. Keep changes narrowly scoped to the requested behavior.
7. Run the relevant lint, test, build, or documentation checks when available.

## Graphify Operations

Graphify may generate a project knowledge graph under `graphify-out/`.

Expected outputs:

- `graphify-out/GRAPH_REPORT.md`
- `graphify-out/graph.json`
- `graphify-out/graph.html`
- `graphify-out/wiki/index.md`

Operating rules:

- Read `graphify-out/GRAPH_REPORT.md` before broad repository analysis when it exists.
- Use `graphify-out/wiki/index.md` for graph wiki navigation when it exists.
- If the report is missing and the project has meaningful files, suggest or run `graphify .` to build the initial graph.
- After meaningful code or semantic documentation changes, run `graphify . --update` when a graph already exists.
- Do not assume the graph auto-updates unless a watcher, `.codex/hooks.json`, or a git hook has been verified.
- Keep generated caches and irrelevant artifacts out of the graph with `.graphifyignore`.

## Status Update Template

```markdown
## Status - YYYY-MM-DD

- Current state:
- Completed:
- In progress:
- Blocked:
- Risks:
- Decisions needed:
- Next actions:
```
