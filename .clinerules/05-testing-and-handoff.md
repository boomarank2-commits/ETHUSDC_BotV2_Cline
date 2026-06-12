# Testing and Handoff

After every code change:
- run the matching test if available
- if no test exists, suggest or create a minimal useful test
- clearly say what was tested and what was not

No success without proof.

Handoff after each task:
Use at most 10 lines.

Short format:
1. Changed:
2. Tests:
3. Result:
4. Next:

Avoid long repeated "not read" or "not built" lists unless there was a concrete risk.
Tasks may include multiple closely related files.

Forbidden:
- saying "done" without test or explanation
- hiding old errors
- adapting README to wrong code
- creating fake results
- loosening quality gates just to make results look better
- reading old bot files
- reading docs-archive/ unless explicitly requested
- inventing domain rules
