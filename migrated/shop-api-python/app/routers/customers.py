"""Customers endpoints — legacy CustomersController -> FastAPI (PROJECT_CONTEXT.md section 6.2).

Wave 1 keeps calling ``usp_GetOrdersByCustomer`` so the proc stays the source of truth.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db import get_connection
from app.schemas import OrderSummaryOut

router = APIRouter(prefix="/api/customers", tags=["customers"])


@router.get("/{customer_id}/orders", response_model=list[OrderSummaryOut])
def get_customer_orders(
    customer_id: int, conn: Connection = Depends(get_connection)
) -> list[OrderSummaryOut]:
    rows = conn.execute(
        text("EXEC usp_GetOrdersByCustomer :CustomerId"),
        {"CustomerId": customer_id},
    ).mappings().all()
    return [OrderSummaryOut(orderId=row["OrderId"], status=row["Status"]) for row in rows]
