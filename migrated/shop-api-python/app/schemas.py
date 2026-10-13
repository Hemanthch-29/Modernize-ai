"""Pydantic response models — the camelCase JSON must match the legacy .NET API exactly.

Monetary values are serialized as JSON numbers (``float``); a Pydantic ``Decimal`` field
would serialize to a JSON string and break numeric parity with the legacy responses.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class OrderItemOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    product_name: str = Field(alias="productName")
    quantity: int
    unit_price: float = Field(alias="unitPrice")


class OrderOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    order_id: int = Field(alias="orderId")
    customer_name: str = Field(alias="customerName")
    status: str
    total: float
    items: list[OrderItemOut]


class OrderSummaryOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    order_id: int = Field(alias="orderId")
    status: str


class ProductOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    name: str
    price: float
