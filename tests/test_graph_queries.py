"""Linker, graph and query tests for Phase 3 (no database needed).

The graph is built with ``conn_str=None`` so the SQL parser uses the ``init.sql`` fallback
and the whole suite runs without a live SQL Server.
"""
import networkx as nx
import pytest

from modernizer import queries
from modernizer.graph_store import (
    apicall_id,
    app_id,
    endpoint_id,
    method_id,
    proc_id,
    save_graph,
    load_graph,
    table_id,
    ui_id,
)
from modernizer.indexer import build_graph
from modernizer.linker import normalize_url


@pytest.fixture(scope="module")
def graph() -> nx.MultiDiGraph:
    g, _ = build_graph(conn_str=None)
    return g


# --- normalize_url (section 9.4) -------------------------------------------------------

def test_normalize_url_examples():
    assert normalize_url("/api/orders/${id}/cancel") == "/api/orders/{}/cancel"
    assert normalize_url("api/orders/{id:int}") == "/api/orders/{}"
    assert normalize_url("http://localhost:5000/api/Products/") == "/api/products"
    assert normalize_url("/api/customers/${customerId}/orders") == "/api/customers/{}/orders"


# --- the full chain from section 8.3 ---------------------------------------------------

def test_section_8_3_full_chain_exists(graph: nx.MultiDiGraph):
    ui = ui_id("shop-ui", "OrderDetails")
    call = apicall_id("shop-ui", "OrderDetails", "GET", "/api/orders/{}")
    endpoint = endpoint_id("shop-api", "GET", "/api/orders/{}")
    controller = method_id("shop-api", "OrdersController.GetOrder")
    service = method_id("shop-api", "OrderService.GetOrder")
    repository = method_id("shop-api", "OrderRepository.GetById")
    proc = proc_id("ShopDB", "usp_GetOrderById")

    assert graph.has_edge(ui, call, key="MAKES_CALL")
    assert graph.has_edge(call, endpoint, key="HANDLED_BY")
    assert graph.has_edge(endpoint, controller, key="IMPLEMENTED_BY")
    assert graph.has_edge(controller, service, key="CALLS")
    assert graph.has_edge(service, repository, key="CALLS")
    assert graph.has_edge(repository, proc, key="EXECUTES")
    for table in ("Orders", "OrderItems", "Customers", "Products"):
        assert graph.has_edge(proc, table_id("ShopDB", table), key="READS"), table


def test_shared_shopdb_is_deduplicated(graph: nx.MultiDiGraph):
    databases = [n for n, d in graph.nodes(data=True) if d.get("type") == "Database"]
    assert databases == ["db:ShopDB"]
    # both apps CONTAIN the one shared database node
    assert graph.has_edge(app_id("OnlineShop"), "db:ShopDB", key="CONTAINS")
    assert graph.has_edge(app_id("Reporting"), "db:ShopDB", key="CONTAINS")


def test_no_unresolved_api_calls(graph: nx.MultiDiGraph):
    unresolved = [
        n for n, d in graph.nodes(data=True)
        if d.get("type") == "ApiCall" and d.get("unresolved")
    ]
    assert unresolved == []


# --- trace_feature (section 9.5) -------------------------------------------------------

def test_trace_order_details_surfaces_gold_discount(graph: nx.MultiDiGraph):
    result = queries.trace_feature("OrderDetails", graph=graph)

    assert result["found"] is True
    names = {n["name"] for n in result["nodes"]}
    assert {"usp_GetOrderById", "usp_CancelOrder", "Orders", "Customers"} <= names

    proc = next(n for n in result["nodes"] if n["name"] == "usp_GetOrderById")
    assert "0.90" in proc["definition"]
    assert "discount" in proc["definition"].lower()


# --- get_dependents (section 9.5) ------------------------------------------------------

def test_dependents_orders_spans_both_apps(graph: nx.MultiDiGraph):
    result = queries.get_dependents("Orders", graph=graph)
    assert result["found"] is True

    by_name = {d["name"]: d for d in result["dependents"]}
    for required in (
        "usp_GetOrderById",
        "usp_CancelOrder",
        "vw_DailySales",
        "DailySalesReport",
        "OrderDetails",
        "CustomerOrders",
    ):
        assert required in by_name, (required, sorted(by_name))

    # DailySalesReport belongs to the Reporting app; the UI screens to OnlineShop.
    assert by_name["DailySalesReport"]["app"] == "Reporting"
    assert by_name["OrderDetails"]["app"] == "OnlineShop"
    assert by_name["CustomerOrders"]["app"] == "OnlineShop"

    apps = {d["name"] for d in result["dependents"] if d["type"] == "Application"}
    assert {"OnlineShop", "Reporting"} <= apps


def test_dependents_includes_both_hidden_rule_procs(graph: nx.MultiDiGraph):
    # The Status column lives on Orders: cancelling (usp_CancelOrder) and the daily view
    # both depend on it, proving cross-app impact.
    result = queries.get_dependents("Orders", graph=graph)
    types = {(d["type"], d["name"]) for d in result["dependents"]}
    assert ("View", "vw_DailySales") in types
    assert ("StoredProcedure", "usp_CancelOrder") in types


# --- definition / search (section 9.5) -------------------------------------------------

def test_definition_returns_proc_sql(graph: nx.MultiDiGraph):
    result = queries.get_definition("usp_GetOrderById", graph=graph)
    assert result["found"] is True
    assert result["type"] == "StoredProcedure"
    assert "CREATE PROCEDURE" in result["definition"]


def test_search_discount_finds_the_proc(graph: nx.MultiDiGraph):
    result = queries.search("discount", graph=graph)
    names = {r["name"] for r in result["results"]}
    assert "usp_GetOrderById" in names


# --- graph_store round-trip ------------------------------------------------------------

def test_graph_json_round_trip(graph: nx.MultiDiGraph, tmp_path):
    path = save_graph(graph, tmp_path / "graph.json")
    reloaded = load_graph(path)
    assert reloaded.number_of_nodes() == graph.number_of_nodes()
    assert reloaded.number_of_edges() == graph.number_of_edges()
    proc = proc_id("ShopDB", "usp_GetOrderById")
    assert reloaded.has_edge(
        method_id("shop-api", "OrderRepository.GetById"), proc, key="EXECUTES"
    )
