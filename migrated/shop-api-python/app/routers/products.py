"""Products endpoint — legacy ProductsController -> FastAPI (PROJECT_CONTEXT.md section 6.2).

Mirrors the legacy inline query ``SELECT Id, Name, Price FROM Products`` (no stored proc).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db import get_connection
from app.schemas import ProductOut

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("", response_model=list[ProductOut])
def get_products(conn: Connection = Depends(get_connection)) -> list[ProductOut]:
    rows = conn.execute(text("SELECT Id, Name, Price FROM Products")).mappings().all()
    return [ProductOut(id=row["Id"], name=row["Name"], price=float(row["Price"])) for row in rows]
