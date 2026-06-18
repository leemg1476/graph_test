# Session Close Prompt

Use this before ending a meaningful AI coding or project-management session.

```text
Close the session with durable project memory.

1. Summarize the goal, outcome, and current state.
2. List files changed and why.
3. Record commands run and validation results.
4. Separate decisions, assumptions, risks, blockers, and open questions.
5. Update:
   - .ai-worklog/YYYY-MM-DD_<task-slug>.md
   - .ai-worklog/index.md
   - memory-bank/activeContext.md
   - memory-bank/progress.md
   - memory-bank/knownIssues.md if issues were found
6. Add an ADR under adr/ if a hard-to-reverse decision was made.
7. Include a copyable Next Prompt for the next session.
8. Confirm that no secrets, raw transcripts, internal URLs, customer-sensitive information, or raw incident logs were recorded.
```
