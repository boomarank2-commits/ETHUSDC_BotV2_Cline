# Token Discipline

Cline must work token-efficiently.

Rules:
- Read only relevant files.
- Do not read large archives unless explicitly asked.
- docs-archive/ is taboo by default.
- reports/ and logs/ are taboo by default.
- Do not read large files fully if targeted search is enough.
- Summarize results briefly.
- Final reports must be at most 10 lines.
- Do not repeat long "not read" or "not built" lists unless there was a real risk.
- Do not write detailed negative lists for every task.
- Do not write long historical documents.
- Do not create duplicate truths.

Short handoff format:
1. Changed:
2. Tests:
3. Result:
4. Next:

Memory Bank:
- memory-bank/ contains only current working context.
- Do not copy old runs into memory-bank.
- Do not duplicate large README content.
- Only decisions, current state, next task and open questions.

After each task:
- update memory-bank/progress.md briefly
- update memory-bank/activeContext.md only if current focus changed
- update memory-bank/openQuestions.md only if something is really open or contradictory

Task size:
- One task may include multiple closely related files.
- Still do not read old bot files.
- Still do not read docs-archive/.
- Still do not invent domain rules.
