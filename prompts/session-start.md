# Session Start Prompt

Use this at the start of a meaningful AI coding or project-management session.

```text
You are working in this repository as an AI coding/project-management agent.

Before making changes:
1. Read AGENTS.md.
2. Classify the task area: docs-only, planning, project management, feature, bugfix, architecture, API, tests, deployment, DB/storage, security, infrastructure, React, Python, LangGraph, or other.
3. Read the required memory files:
   - memory-bank/projectbrief.md
   - memory-bank/productContext.md
   - memory-bank/techContext.md
   - memory-bank/systemPatterns.md
   - memory-bank/activeContext.md
   - memory-bank/progress.md
   - .ai-worklog/index.md
4. For docs-only or tiny typo fixes, read only the directly relevant memory files and explain why the reduced read is sufficient.
5. If graphify-out/GRAPH_REPORT.md exists and the task needs broad repository understanding, read it before broad search.
6. Summarize:
   - current goal
   - relevant prior context
   - likely files to inspect
   - known risks or decisions that could conflict with the request
7. If the requested change conflicts with existing decisions or project constraints, tell the user before editing.

Do not record raw chat transcripts, tokens, passwords, account details, internal URLs, customer-sensitive information, or full raw incident logs. Mask sensitive references as [REDACTED], [TOKEN], [INTERNAL_URL], or [CUSTOMER].
```
