# ModernizeAI

AI assistant that reads legacy **.NET** repos plus their **SQL Server** database, links them into a
**knowledge graph**, and helps migrate the stack to **Angular + Python (FastAPI) + AWS**. It exposes
full-stack trace queries to GitHub Copilot through an MCP server and a custom "Modernizer" agent.

> **[PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) is the single source of truth** for the idea, the
> specification and the phase-by-phase plan. Read it first.

## Status

Project scaffolding (**Phase 0** complete). The project is built **one phase at a time** — see
section 10 of [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md).

## Prerequisites

Python 3.11+, SQL Server LocalDB, `sqlcmd`, ODBC Driver 18, .NET SDK 8+, Node.js 20+, and
VS Code + GitHub Copilot (Agent mode + MCP enabled). Details in section 4 of the context document.

## Dev setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env   # adjust if your LocalDB/driver differ
```

## Quick start (once later phases are built)

```powershell
.\scripts\setup-db.ps1          # create/reset ShopDB on LocalDB
.\scripts\start-legacy.ps1      # .NET API :5000 + React UI :5173
python -m modernizer.cli index  # build output/graph.json
.\scripts\start-modern.ps1      # FastAPI :8000 + Angular UI :4200
python -m modernizer.cli parity # compare legacy vs new APIs
```

## Layout

See section 5 of [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md).
