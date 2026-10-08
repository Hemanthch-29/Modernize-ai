# Copilot instructions

- **Read `PROJECT_CONTEXT.md` first** — it is the single source of truth. Work one phase at a time and run each phase's "Done when" checks before moving on.
- Python 3.11+, type hints, small functions, `dataclasses` for parser facts. Keep file names and paths exactly as in section 5.
- Never commit secrets: use `.env` (gitignored) and environment variables; keep connection strings out of YAML/code.
- Parameterized SQL only in new Python code; the indexer runs **read-only** queries against SQL Server.
- Prefer the simplest option that makes the demo work (regex parsers, NetworkX, JSON storage) and record any new decision in the Decision Log (section 14).
