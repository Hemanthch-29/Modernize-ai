"""React parser facts (no database needed)."""
from modernizer.config import PROJECT_ROOT
from modernizer.parsers.react_parser import ApiCallFact, parse_react

SHOP_UI = PROJECT_ROOT / "sample-legacy" / "shop-ui"


def _facts() -> list[ApiCallFact]:
    return parse_react(SHOP_UI)


def test_order_details_has_get_and_cancel():
    order_details = [f for f in _facts() if f.component == "OrderDetails"]

    assert any(
        f.method == "GET" and f.raw_url == "/api/orders/${id}" for f in order_details
    ), order_details
    assert any(
        f.method == "POST" and f.raw_url == "/api/orders/${id}/cancel"
        for f in order_details
    ), order_details


def test_product_list_uses_fetch_get():
    product_list = [f for f in _facts() if f.component == "ProductList"]

    assert any(
        f.method == "GET" and f.raw_url == "/api/products" for f in product_list
    ), product_list


def test_customer_orders_get():
    customer_orders = [f for f in _facts() if f.component == "CustomerOrders"]

    assert any(
        f.method == "GET" and f.raw_url == "/api/customers/${customerId}/orders"
        for f in customer_orders
    ), customer_orders
