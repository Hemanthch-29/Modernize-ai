"""FastAPI application entrypoint — run with ``uvicorn app.main:app --port 8000``.

Mirrors the legacy ShopApi routes (PROJECT_CONTEXT.md section 6.6): same paths, status
codes and camelCase JSON field names, backed by the same ShopDB.
"""
from __future__ import annotations

from fastapi import FastAPI

from app.routers import customers, orders, products

app = FastAPI(title="ShopApi (migrated, FastAPI)")

app.include_router(orders.router)
app.include_router(customers.router)
app.include_router(products.router)
