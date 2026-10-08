""".NET parser facts (no database needed)."""
import pytest

from modernizer.config import PROJECT_ROOT
from modernizer.parsers.dotnet_parser import DotNetFacts, parse_dotnet, resolve_type

SHOP_API = PROJECT_ROOT / "sample-legacy" / "shop-api"


@pytest.fixture(scope="module")
def facts() -> DotNetFacts:
    return parse_dotnet(SHOP_API)


def test_get_order_route(facts: DotNetFacts):
    route = facts.find_route("GET", "api/orders/{id:int}")

    assert route is not None
    assert route.controller == "OrdersController"
    assert route.handler == "GetOrder"


def test_order_repository_get_by_id_uses_proc(facts: DotNetFacts):
    usages = facts.sql_usages_for("OrderRepository", "GetById")

    assert any(u.kind == "proc" and u.proc == "usp_GetOrderById" for u in usages), usages


def test_product_repository_inline_sql_reads_products(facts: DotNetFacts):
    usages = facts.sql_usages_for("ProductRepository", "GetAll")

    assert any(u.kind == "inline" and "Products" in u.reads for u in usages), usages


def test_di_resolves_order_service(facts: DotNetFacts):
    controller = facts.get_class("OrdersController")

    assert controller is not None
    assert "OrderService" in controller.di_map.values(), controller.di_map
    assert resolve_type("IOrderService") == "OrderService"


def test_calls_chain_controller_to_service(facts: DotNetFacts):
    callees = {c.callee for c in facts.calls if c.caller == "OrdersController.GetOrder"}

    assert "OrderService.GetOrder" in callees, callees
