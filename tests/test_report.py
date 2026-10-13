from typer.testing import CliRunner

from modernizer import cli
from modernizer.indexer import build_graph
from modernizer.report import render_report, write_report


def test_report_flags_hidden_rules_and_shared_orders(tmp_path):
    graph, _ = build_graph(conn_str=None)

    report = render_report("OnlineShop", graph=graph)

    assert "Gold customer discount (10% off)" in report
    assert "@Total = @Total * 0.90" in report
    assert "Shipped-order cancellation rule" in report
    assert "Cannot cancel a shipped order." in report
    assert "| `Orders` | OnlineShop, Reporting | Reporting |" in report
    assert "## Endpoint Complexity" in report
    assert "## Unresolved Links" in report

    path = write_report("OnlineShop", graph=graph, output_dir=tmp_path)
    assert path.name == "OnlineShop-migration-plan.md"
    assert path.read_text(encoding="utf-8") == report


def test_report_is_deterministic():
    graph, _ = build_graph(conn_str=None)

    assert render_report("OnlineShop", graph=graph) == render_report("OnlineShop", graph=graph)


def test_cli_report_generates_and_prints_report(monkeypatch, tmp_path):
    graph, _ = build_graph(conn_str=None)
    monkeypatch.setattr(cli, "load_graph", lambda: graph)
    monkeypatch.setattr(
        cli,
        "write_report",
        lambda name, graph: write_report(name, graph=graph, output_dir=tmp_path),
    )

    result = CliRunner().invoke(cli.app, ["report", "OnlineShop"])

    assert result.exit_code == 0, result.output
    assert "Wrote" in result.output
    assert "Gold customer discount" in result.output
    assert (tmp_path / "OnlineShop-migration-plan.md").exists()