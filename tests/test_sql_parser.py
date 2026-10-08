"""SQL parser facts via the init.sql fallback (no database needed)."""
import pytest

from modernizer.config import INIT_SQL_PATH
from modernizer.parsers.sql_parser import SqlFacts, extract_tables, parse_init_sql


@pytest.fixture(scope="module")
def facts() -> SqlFacts:
    return parse_init_sql(INIT_SQL_PATH)


def test_get_order_by_id_reads_core_tables(facts: SqlFacts):
    proc = facts.routine("usp_GetOrderById")

    assert proc is not None
    assert {"Orders", "OrderItems", "Customers"} <= proc.reads, proc.reads


def test_cancel_order_writes_orders(facts: SqlFacts):
    proc = facts.routine("usp_CancelOrder")

    assert proc is not None
    assert "Orders" in proc.writes, proc.writes


def test_tables_and_columns_parsed(facts: SqlFacts):
    orders = facts.table("Orders")

    assert orders is not None
    column_names = {c.name for c in orders.columns}
    assert {"Id", "CustomerId", "Status", "CreatedAt"} <= column_names, column_names


def test_view_reads_orders(facts: SqlFacts):
    view = facts.routine("vw_DailySales")

    assert view is not None
    assert view.kind == "view"
    assert {"Orders", "OrderItems"} <= view.reads, view.reads


def test_extract_tables_reads_and_writes():
    reads, writes = extract_tables("SELECT * FROM dbo.Orders o JOIN OrderItems oi ON oi.OrderId = o.Id")
    assert reads == {"Orders", "OrderItems"}
    assert writes == set()

    reads, writes = extract_tables("UPDATE dbo.Orders SET Status = 'Cancelled' WHERE Id = 1")
    assert writes == {"Orders"}

    reads, writes = extract_tables("DELETE FROM OrderItems WHERE Id = 1")
    assert writes == {"OrderItems"}
    assert reads == set()
