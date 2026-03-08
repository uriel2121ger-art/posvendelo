Spawn 9 parallel reviewer subagents using model haiku to review all staged and recently modified files:

1. **Linter & static analysis** — Check for syntax errors, type issues, and lint violations in both Python (backend/) and TypeScript (frontend/src/)
2. **Top 5 code issues** — Identify the 5 most critical code issues across the changeset
3. **Security vulnerabilities** — Check for OWASP top 10: SQL injection, XSS, auth bypass, hardcoded secrets, IDOR, null byte issues
4. **Code quality & style** — Verify naming conventions (English code, Spanish business vars), proper error handling, consistent patterns
5. **Dependency problems** — Check for missing imports, circular dependencies, unused dependencies
6. **Complexity hotspots** — Flag functions over 50 lines, deeply nested logic, high cyclomatic complexity
7. **Duplication detection** — Find copy-pasted code blocks that should be abstracted
8. **Test coverage gaps** — Map changed code to existing tests, flag untested paths
9. **Performance issues** — N+1 queries, missing indexes, unnecessary re-renders, blocking I/O in async context

Rules for all reviewers:
- Only report issues with HIGH confidence (>80%)
- Include file path and line number for each finding
- Severity levels: CRITICAL, HIGH, MEDIUM (skip LOW)
- Context: This is TITAN POS — FastAPI + asyncpg backend, React + Electron frontend
- Security rules from CLAUDE.md apply: never trust client prices, SHA256 PINs, manager PIN for cancellations

Consolidate all findings into a single report sorted by severity before allowing the commit.
