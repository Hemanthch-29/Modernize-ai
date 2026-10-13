"""Orders endpoints — legacy OrdersController -> FastAPI (PROJECT_CONTEXT.md sections 6.2, 9.11).

GET /api/orders/{id} is the demo **v1**: it computes the total in Python from OrderItems
with a plain SELECT and does NOT call ``usp_GetOrderById`` — so the hidden Gold 10% discount
is intentionally missing (order 2 will read 450.00 instead of 405.00 until the parity fix).
Cancellation keeps calling ``usp_CancelOrder`` so its shipped-order rule is preserved.
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError

from app.db import get_connection
from app.schemas import OrderItemOut, OrderOut

router = APIRouter(prefix="/api/orders", tags=["orders"])

# pyodbc surfaces THROW as "[driver][SQL Server]<message> (50001) (SQLExecDirectW)";
# strip the trailing "(<number>) (<api>)" so the 409 body matches the legacy message.
_SQL_SUFFIX_RE = re.compile(r"\s*\(\d+\)(?:\s*\(\w+\))?\s*$")


def _sql_error_message(exc: Exception) -> str:
    orig = getattr(exc, "orig", exc)
    args = getattr(orig, "args", ())
    raw = args[1] if len(args) > 1 else str(orig)
    return _SQL_SUFFIX_RE.sub("", raw.split("]")[-1]).strip() or str(orig)


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: int, conn: Connection = Depends(get_connection)) -> OrderOut:
    header = conn.execute(
        text(
            "SELECT o.Id AS OrderId, c.Name AS CustomerName, o.Status AS Status "
            "FROM Orders o JOIN Customers c ON c.Id = o.CustomerId "
            "WHERE o.Id = :order_id"
        ),
        {"order_id": order_id},
    ).mappings().first()
    if header is None:
        raise HTTPException(status_code=404)

    item_rows = conn.execute(
        text(
            "SELECT p.Name AS ProductName, oi.Quantity AS Quantity, oi.UnitPrice AS UnitPrice "
            "FROM OrderItems oi JOIN Products p ON p.Id = oi.ProductId "
            "WHERE oi.OrderId = :order_id ORDER BY oi.Id"
        ),
        {"order_id": order_id},
    ).mappings().all()

    items = [
        OrderItemOut(
            productName=row["ProductName"],
            quantity=row["Quantity"],
            unitPrice=float(row["UnitPrice"]),
        )
        for row in item_rows
    ]
    # v1 total: plain subtotal, WITHOUT the Gold discount applied by usp_GetOrderById.
    total = round(sum(row["Quantity"] * row["UnitPrice"] for row in item_rows), 2)

    return OrderOut(
        orderId=header["OrderId"],
        customerName=header["CustomerName"],
        status=header["Status"],
        total=float(total),
        items=items,
    )


@router.post("/{order_id}/cancel")
def cancel_order(order_id: int, conn: Connection = Depends(get_connection)):
    exists = conn.execute(
        text("SELECT 1 FROM Orders WHERE Id = :order_id"),
        {"order_id": order_id},
    ).first()
    if exists is None:
        raise HTTPException(status_code=404)

    try:
        conn.execute(text("EXEC usp_CancelOrder :OrderId"), {"OrderId": order_id})
        conn.commit()
    except DBAPIError as exc:
        conn.rollback()
        return JSONResponse(status_code=409, content={"error": _sql_error_message(exc)})
    return Response(status_code=204)
