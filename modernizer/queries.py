"""Graph queries — pure functions used by the CLI and the MCP server (section 9.5).

Each function takes an optional ``graph`` (so tests can pass one in) and otherwise loads
``output/graph.json``. Name matching is case-insensitive and accepts short names
(``OrderDetails``, ``Orders``, ``usp_GetOrderById``).
"""
from __future__ import annotations

import networkx as nx

from modernizer.graph_store import app_id, load_graph

# Relationships that carry the "flow" from a screen down to the tables. Followed forwards
# for a trace and backwards for dependents; CONTAINS (ownership) is deliberately excluded.
_FLOW_RELS = {
    "MAKES_CALL",
    "HANDLED_BY",
    "IMPLEMENTED_BY",
    "CALLS",
    "EXECUTES",
    "READS",
    "WRITES",
}
_REL_ORDER = {rel: i for i, rel in enumerate(
    ["MAKES_CALL", "HANDLED_BY", "IMPLEMENTED_BY", "CALLS", "EXECUTES", "READS", "WRITES"]
)}
# When a bare name matches several nodes, trace from the most "upstream" kind first.
_TRACE_PRIORITY = {
    "UIComponent": 0,
    "ApiEndpoint": 1,
    "CSharpMethod": 2,
    "CSharpClass": 3,
    "StoredProcedure": 4,
    "View": 5,
    "Table": 6,
}
_VIEW_ATTRS = (
    "app",
    "repo",
    "file",
    "line",
    "method",
    "route",
    "normalized_url",
    "raw_url",
    "kind",
    "routine_kind",
    "signature",
    "handler",
    "definition",
    "unresolved",
)


def _graph(graph: nx.MultiDiGraph | None) -> nx.MultiDiGraph:
    return graph if graph is not None else load_graph()


def _node_view(graph: nx.MultiDiGraph, node_id: str) -> dict:
    data = graph.nodes[node_id]
    view: dict[str, object] = {"id": node_id, "type": data.get("type"), "name": data.get("name")}
    for key in _VIEW_ATTRS:
        value = data.get(key)
        if value is not None:
            view[key] = value
    return view


def resolve(graph: nx.MultiDiGraph, name: str) -> list[str]:
    """Node ids matching ``name``: exact node-name, then id, then a ``Class.method`` suffix."""
    low = name.lower()
    exact = [n for n, d in graph.nodes(data=True) if str(d.get("name", "")).lower() == low]
    if exact:
        return exact
    if graph.has_node(name):
        return [name]
    by_id = [n for n in graph.nodes if n.lower() == low]
    if by_id:
        return by_id
    return [n for n, d in graph.nodes(data=True) if str(d.get("name", "")).lower().endswith("." + low)]


def _flow_successors(graph: nx.MultiDiGraph, node_id: str) -> list[tuple[str, str, str | None]]:
    edges: list[tuple[str, str, str | None]] = []
    for _, dst, key, data in graph.out_edges(node_id, keys=True, data=True):
        rel = data.get("rel", key)
        if rel in _FLOW_RELS:
            edges.append((rel, dst, data.get("confidence")))
    edges.sort(key=lambda e: (_REL_ORDER.get(e[0], 99), str(graph.nodes[e[1]].get("name", ""))))
    return edges


def _build_tree(graph: nx.MultiDiGraph, node_id: str, path: frozenset[str]) -> dict:
    node = _node_view(graph, node_id)
    children: list[dict] = []
    if node_id not in path:
        for rel, dst, confidence in _flow_successors(graph, node_id):
            child = _build_tree(graph, dst, path | {node_id})
            child["edge"] = rel
            if confidence is not None:
                child["edge_confidence"] = confidence
            children.append(child)
    else:
        node["cycle"] = True
    node["children"] = children
    return node


def list_applications(graph: nx.MultiDiGraph | None = None) -> list[dict]:
    """Applications with their repos, databases, wave and status."""
    graph = _graph(graph)
    apps: list[dict] = []
    for node, data in graph.nodes(data=True):
        if data.get("type") != "Application":
            continue
        repos = [
            graph.nodes[dst]["name"]
            for _, dst, key in graph.out_edges(node, keys=True)
            if graph.nodes[dst].get("type") == "Repo"
        ]
        databases = [
            graph.nodes[dst]["name"]
            for _, dst, key in graph.out_edges(node, keys=True)
            if graph.nodes[dst].get("type") == "Database"
        ]
        apps.append(
            {
                "name": data.get("name"),
                "owner": data.get("owner"),
                "wave": data.get("wave"),
                "status": data.get("status"),
                "repos": sorted(repos),
                "databases": sorted(databases),
            }
        )
    return sorted(apps, key=lambda a: str(a["name"]))


def trace_feature(name: str, graph: nx.MultiDiGraph | None = None) -> dict:
    """Trace a UI component / endpoint / method down to the tables it touches.

    Returns a ``tree`` (nested dict, for the indented CLI view) and a flat ``nodes`` list of
    everything reachable downstream — including stored-procedure ``definition`` text so the
    hidden business rules are visible.
    """
    graph = _graph(graph)
    matches = resolve(graph, name)
    if not matches:
        return {"name": name, "found": False, "root": None, "tree": None, "nodes": []}

    root = min(matches, key=lambda n: _TRACE_PRIORITY.get(graph.nodes[n].get("type"), 99))
    tree = _build_tree(graph, root, frozenset())

    reachable: list[str] = []
    seen: set[str] = set()
    stack = [root]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        reachable.append(current)
        for _, dst, confidence in _flow_successors(graph, current):
            stack.append(dst)
    nodes = [_node_view(graph, n) for n in reachable]
    return {"name": name, "found": True, "root": root, "tree": tree, "nodes": nodes}


def get_dependents(name: str, graph: nx.MultiDiGraph | None = None) -> dict:
    """Everything upstream of a table/proc/class — across every app that depends on it.

    Walks the flow edges backwards (procs, views, methods, endpoints, UI components) and
    then adds the owning ``Application`` for each node reached, so a shared table surfaces
    dependents in more than one app.
    """
    graph = _graph(graph)
    matches = resolve(graph, name)
    if not matches:
        return {"name": name, "found": False, "target": None, "dependents": []}

    target = matches[0]
    seen: set[str] = set()
    stack = [target]
    while stack:
        current = stack.pop()
        for src, _, key, data in graph.in_edges(current, keys=True, data=True):
            rel = data.get("rel", key)
            if rel in _FLOW_RELS and src not in seen:
                seen.add(src)
                stack.append(src)

    apps: set[str] = set()
    for node_id in seen:
        owner = graph.nodes[node_id].get("app")
        if owner and graph.has_node(app_id(owner)):
            apps.add(app_id(owner))

    result = sorted(seen | apps)
    dependents = [_node_view(graph, n) for n in result]
    return {"name": name, "found": True, "target": target, "dependents": dependents}


def get_definition(name: str, graph: nx.MultiDiGraph | None = None) -> dict:
    """Source / SQL text (plus file and line) for the best match of ``name``."""
    graph = _graph(graph)
    matches = resolve(graph, name)
    if not matches:
        return {"name": name, "found": False}
    node_id = matches[0]
    view = _node_view(graph, node_id)
    view["found"] = True
    view["matches"] = [graph.nodes[n]["name"] for n in matches]
    return view


def search(text: str, graph: nx.MultiDiGraph | None = None) -> dict:
    """Keyword search over node names and their source / SQL text (case-insensitive)."""
    graph = _graph(graph)
    low = text.lower()
    haystack_keys = ("name", "definition", "signature", "route", "raw_url", "normalized_url", "handler")
    results: list[dict] = []
    for node, data in graph.nodes(data=True):
        blob = " ".join(str(data.get(key, "")) for key in haystack_keys).lower()
        if low in blob:
            results.append(_node_view(graph, node))
    results.sort(key=lambda r: (_TRACE_PRIORITY.get(r.get("type"), 99), str(r.get("name"))))
    return {"query": text, "count": len(results), "results": results}
