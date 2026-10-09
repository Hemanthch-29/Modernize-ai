"""Knowledge-graph storage — a NetworkX ``MultiDiGraph`` (section 8).

Holds the node-id builders (so the indexer, linker and tests agree on ids), small
``add_node`` / ``add_edge`` helpers that de-duplicate, and ``save_graph`` / ``load_graph``
which round-trip ``output/graph.json`` via :func:`networkx.node_link_data`.
"""
from __future__ import annotations

import json
from pathlib import Path

import networkx as nx

from modernizer.config import PROJECT_ROOT

GRAPH_PATH = PROJECT_ROOT / "output" / "graph.json"


# node ids are "type:scope:name" strings; one builder per node type (section 8.1).
def app_id(name: str) -> str:
    return f"app:{name}"


def repo_id(name: str) -> str:
    return f"repo:{name}"


def db_id(name: str) -> str:
    return f"db:{name}"


def ui_id(repo: str, component: str) -> str:
    return f"ui:{repo}:{component}"


def apicall_id(repo: str, component: str, method: str, normalized_url: str) -> str:
    return f"apicall:{repo}:{component}:{method}:{normalized_url}"


def endpoint_id(repo: str, method: str, normalized_url: str) -> str:
    return f"endpoint:{repo}:{method}:{normalized_url}"


def class_id(repo: str, name: str) -> str:
    return f"class:{repo}:{name}"


def method_id(repo: str, qualified_name: str) -> str:
    return f"method:{repo}:{qualified_name}"


def proc_id(database: str, name: str) -> str:
    return f"proc:{database}:{name}"


def view_id(database: str, name: str) -> str:
    return f"view:{database}:{name}"


def table_id(database: str, name: str) -> str:
    return f"table:{database}:{name}"


def new_graph() -> nx.MultiDiGraph:
    return nx.MultiDiGraph()


def add_node(
    graph: nx.MultiDiGraph,
    node_id: str,
    *,
    type: str,
    name: str,
    app: str | None = None,
    repo: str | None = None,
    file: str | None = None,
    line: int | None = None,
    **attrs: object,
) -> str:
    """Add a node, or fill in any attributes still missing on an existing one.

    Re-adding a node (e.g. the shared ``ShopDB``) is a no-op beyond back-filling
    attributes that were previously ``None``.
    """
    data: dict[str, object] = {
        "type": type,
        "name": name,
        "app": app,
        "repo": repo,
        "file": file,
        "line": line,
    }
    data.update(attrs)
    if graph.has_node(node_id):
        existing = graph.nodes[node_id]
        for key, value in data.items():
            if value is not None and existing.get(key) is None:
                existing[key] = value
        return node_id
    graph.add_node(node_id, **data)
    return node_id


def add_edge(
    graph: nx.MultiDiGraph,
    source: str,
    target: str,
    rel: str,
    *,
    confidence: str | None = None,
    **attrs: object,
) -> None:
    """Add a relationship edge keyed by ``rel`` (one edge per ``rel`` between two nodes)."""
    if graph.has_edge(source, target, key=rel):
        return
    data: dict[str, object] = {"rel": rel}
    if confidence is not None:
        data["confidence"] = confidence
    data.update(attrs)
    graph.add_edge(source, target, key=rel, **data)


def save_graph(graph: nx.MultiDiGraph, path: str | Path = GRAPH_PATH) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = nx.node_link_data(graph, edges="edges")
    path.write_text(json.dumps(data, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return path


def load_graph(path: str | Path = GRAPH_PATH) -> nx.MultiDiGraph:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return nx.node_link_graph(data, directed=True, multigraph=True, edges="edges")
