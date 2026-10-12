---
description: .NET → Python (FastAPI) / Angular / AWS migration mapping rules for the ModernizeAI sample app.
applyTo: "migrated/**"
---

# Migration mapping rules (.NET → Python/Angular/AWS)

Apply these rules when converting the legacy app (React + ASP.NET Web API + SQL Server) to the target
stack. **Preserve behaviour exactly**: the new API must return the same routes, the same HTTP status
codes, and the **same camelCase JSON field names** as the legacy API, including any business rules that
live in stored procedures (e.g. the Gold-customer 10% discount in `usp_GetOrderById`).

## Mapping table

| Legacy | Target |
|---|---|
| ASP.NET controller | FastAPI `APIRouter` in `app/routers/<name>.py` |
| Constructor DI | FastAPI `Depends(...)` |
| C# model / DTO | Pydantic model in `app/schemas.py` (**keep the same camelCase JSON field names**, using `alias` / `populate_by_name`) |
| Dapper + stored proc | SQLAlchemy `text("EXEC usp_X :p")` (Wave 1: keep the procs) |
| Inline SQL | SQLAlchemy `text(...)` with bound parameters (never string-concatenate SQL) |
| `NotFound()` | `HTTPException(404)` |
| SQL `RAISERROR` / `THROW` business errors | `HTTPException(409)` with the same message |
| React page | Angular **standalone** component + `inject(HttpClient)` service + TypeScript interface |
| `useEffect` + axios | Angular service returning `Observable`, `toSignal` in the component |
| `react-router-dom` routes / `useParams` | Angular `Routes` in `app.routes.ts` / `ActivatedRoute` (or `input()` with `withComponentInputBinding`) |
| Vite dev proxy (`vite.config.ts`) | Angular dev proxy (`proxy.conf.json`) |
| `useState` | Angular `signal()` |
| `web.config` / `appsettings.json` secrets | AWS Secrets Manager / SSM Parameter Store (env vars locally) |
| MSMQ / queues | Amazon SQS |
| Windows Service / scheduled job | AWS Lambda + EventBridge Scheduler |
| IIS-hosted API | Container on Amazon ECS Fargate behind ALB / API Gateway |
| SQL Server | Amazon RDS for SQL Server (Wave 1) → Aurora PostgreSQL (later) |

## Hard requirements

- **JSON parity:** field names, casing, nesting and types must match the legacy response byte-for-byte
  where practical. For `GET /api/orders/{id}` that means
  `{ "orderId", "customerName", "status", "total", "items": [ { "productName", "quantity", "unitPrice" } ] }`.
- **Status codes:** missing resource → `404`; business-rule violation raised by a proc (`THROW`) →
  `409` with the original message; otherwise mirror the legacy behaviour.
- **Keep hidden business rules:** rules implemented in stored procedures (discounts, totals, status
  checks) must be preserved. In Wave 1 keep calling the existing procs rather than re-implementing the
  logic in Python, so nothing is lost in translation.
- **Security:** parameterized SQL only — never interpolate or concatenate user input into SQL. Keep
  connection strings and secrets in environment variables / `.env` locally (never in code or YAML),
  and in AWS Secrets Manager / SSM in the cloud.
- **Config:** read the database connection from the `SHOPDB_CONN` environment variable via
  `python-dotenv`; the dev proxy forwards `/api` to the backend so the UI keeps using relative URLs.
