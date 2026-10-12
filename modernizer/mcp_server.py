"""MCP server — exposes the knowledge-graph queries as tools for GitHub Copilot (section 9.6).

Run over stdio::

    python -m modernizer.mcp_server

It is registered in ``.vscode/mcp.json`` so VS Code starts it and the **Modernizer** custom agent
can call its tools. The graph (``output/graph.json``) is loaded once and reused for every call; run
``python -m modernizer.cli index`` first to (re)generate it.

Tool docstrings matter: Copilot reads them to decide which tool to call, so each one explains what it
answers and which arguments it accepts.

Note: this project has ``mcp`` v2 installed, where the v1 ``FastMCP`` class (section 9.6) is renamed
to :class:`mcp.server.mcpserver.MCPServer`; the decorator/``run`` API is otherwise the same.
"""
from __future__ import annotations

import networkx as nx
from mcp.server.mcpserver import MCPServer

from modernizer import queries
from modernizer.graph_store import load_graph

mcp = MCPServer("modernizer")

_GRAPH: nx.MultiDiGraph | None = None


def _graph() -> nx.MultiDiGraph:
    """Load ``output/graph.json`` once and reuse it for every tool call."""
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = load_graph()
    return _GRAPH


@mcp.tool()
def list_applications() -> list[dict]:
    """List every application in the portfolio with its repos, databases, migration wave and status.

    Use this for an overview of what exists before tracing a specific feature or planning a migration.
    """
    return queries.list_applications(graph=_graph())


@mcp.tool()
def trace_feature(name: str) -> dict:
    """Trace a UI component, API endpoint, or C# method DOWN to the database tables it touches.

    Follows the full-stack flow: React screen -> API endpoint -> C# controller/service/repository ->
    stored procedure -> tables. Returns a nested ``tree`` plus a flat ``nodes`` list that includes each
    stored-procedure ``definition``, so hidden business rules (e.g. the Gold-customer 10% discount in
    ``usp_GetOrderById``) are visible. Use this to answer "how does screen X work end to end?" or
    "how is a value calculated?". ``name`` is case-insensitive and accepts short names such as
    ``OrderDetails``, ``GetOrder`` or ``usp_GetOrderById``.
    """
    return queries.trace_feature(name, graph=_graph())


@mcp.tool()
def get_dependents(name: str) -> dict:
    """List everything UPSTREAM of a table, stored procedure, or class — across every application.

    Walks the flow backwards (tables <- procs/views <- C# methods <- endpoints <- UI components) and
    adds each owning application, so a shared table like ``Orders`` surfaces dependents in BOTH the
    OnlineShop and Reporting apps. Use this to answer "what breaks if I change/rename X?". ``name`` is
    case-insensitive and accepts short names such as ``Orders`` or ``usp_CancelOrder``.
    """
    return queries.get_dependents(name, graph=_graph())


@mcp.tool()
def get_definition(name: str) -> dict:
    """Return the source code / SQL text (with file and line) for the best match of ``name``.

    Use this to read the exact body of a stored procedure, C# method or UI component — for example to
    quote the SQL that implements a business rule. ``name`` is case-insensitive and accepts short names
    such as ``usp_CancelOrder`` or ``OrderService.GetOrder``.
    """
    return queries.get_definition(name, graph=_graph())


@mcp.tool()
def search_code(text: str) -> dict:
    """Keyword-search node names and their source / SQL text (case-insensitive).

    Returns matching nodes ordered from the UI down to the tables. Use this to find where a term such
    as ``discount``, ``Gold`` or ``cancel`` appears anywhere across all repos and the database.
    """
    return queries.search(text, graph=_graph())


@mcp.tool()
def app_summary(name: str) -> dict:
    """Summarise one application: counts, unresolved API links, and shared databases.

    Returns the number of UI components, API endpoints, C# classes, stored procedures and tables, the
    list of unresolved API calls (UI calls with no matching endpoint), and which databases this app
    shares with other applications. ``name`` is an application name (e.g. ``OnlineShop``),
    case-insensitive.
    """
    return queries.app_summary(name, graph=_graph())


@mcp.tool()
def run_parity_tests() -> dict:
    """Run the legacy-vs-new API parity tests (``parity/cases.yaml``) and report any mismatches.

    This calls the same request against the legacy and migrated APIs and compares the responses, which
    is how the missing Gold discount is caught. The parity tester is built in Phase 6; until then this
    reports that it is not yet available.
    """
    from modernizer import parity

    runner = getattr(parity, "run_parity_tests", None)
    if runner is None:
        return {
            "status": "not_available",
            "message": (
                "Parity testing is implemented in Phase 6 (modernizer/parity.py) and is not available "
                "yet. Once it exists, this tool will run parity/cases.yaml against the legacy and new "
                "APIs and report mismatches."
            ),
        }
    return runner()


def main() -> None:
    _graph()  # load output/graph.json once at start (section 9.6)
    mcp.run()  # stdio transport


if __name__ == "__main__":
    main()
