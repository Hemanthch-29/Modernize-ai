"""Linker — connect facts across sources (section 9.4).

Two independently-built halves of the graph are stitched together here:

* ``normalize_url`` turns a frontend template literal and a .NET route attribute into the
  same canonical string, so ``ApiCall`` → ``ApiEndpoint`` can be matched on
  ``(method, normalized_url)`` → ``HANDLED_BY`` (``confidence=exact``).
* .NET SQL usage facts become ``EXECUTES`` (code → stored procedure, ``exact``) and
  ``READS`` / ``WRITES`` (inline SQL → table/view, ``inferred``).
"""
from __future__ import annotations

import re

import networkx as nx

from modernizer.graph_store import add_edge, class_id, method_id

_HOST_RE = re.compile(r"^[a-z][a-z0-9+.\-]*://[^/]+", re.IGNORECASE)
_DOLLAR_RE = re.compile(r"\$\{[^}]*\}")
_BRACE_RE = re.compile(r"\{[^}]*\}")


def normalize_url(url: str) -> str:
    """Canonicalise a URL so both sides of a call match (section 9.4).

    Drops any host, lowercases, collapses ``${...}`` and ``{id:int}`` / ``{id}`` to ``{}``,
    forces a leading ``/`` and strips a trailing one.

    >>> normalize_url("`/api/orders/${id}/cancel`".strip("`"))
    '/api/orders/{}/cancel'
    >>> normalize_url("api/orders/{id:int}")
    '/api/orders/{}'
    """
    cleaned = url.strip().strip("`'\"")
    cleaned = _HOST_RE.sub("", cleaned)
    cleaned = cleaned.lower()
    cleaned = _DOLLAR_RE.sub("{}", cleaned)
    cleaned = _BRACE_RE.sub("{}", cleaned)
    if not cleaned.startswith("/"):
        cleaned = "/" + cleaned
    if len(cleaned) > 1:
        cleaned = cleaned.rstrip("/")
    return cleaned


def link_api_calls(graph: nx.MultiDiGraph) -> int:
    """Match every ``ApiCall`` to an ``ApiEndpoint`` on ``(method, normalized_url)``.

    Returns the number of API calls left ``unresolved`` (no matching endpoint).
    """
    endpoints: dict[tuple[str, str], str] = {}
    for node, data in graph.nodes(data=True):
        if data.get("type") == "ApiEndpoint":
            endpoints[(data["method"].upper(), data["normalized_url"])] = node

    unresolved = 0
    for node, data in graph.nodes(data=True):
        if data.get("type") != "ApiCall":
            continue
        target = endpoints.get((data["method"].upper(), data["normalized_url"]))
        if target is not None:
            add_edge(graph, node, target, "HANDLED_BY", confidence="exact")
        else:
            data["unresolved"] = True
            unresolved += 1
    return unresolved


def _owner_node(graph: nx.MultiDiGraph, repo: str, owner_class: str, owner_method: str | None) -> str | None:
    """The graph node that owns a SQL usage: its method if known, else its class."""
    if owner_method:
        candidate = method_id(repo, f"{owner_class}.{owner_method}")
        if graph.has_node(candidate):
            return candidate
    candidate = class_id(repo, owner_class)
    if graph.has_node(candidate):
        return candidate
    return None


def link_code_to_sql(graph: nx.MultiDiGraph, dotnet_facts_by_repo) -> None:
    """Create ``EXECUTES`` / ``READS`` / ``WRITES`` edges from C# code into the database."""
    procs: dict[str, str] = {}
    tables: dict[str, str] = {}
    relations: dict[str, str] = {}  # tables + views (a READS target may be a view)
    for node, data in graph.nodes(data=True):
        kind = data.get("type")
        if kind == "StoredProcedure":
            procs[data["name"].lower()] = node
        elif kind == "Table":
            tables[data["name"].lower()] = node
            relations[data["name"].lower()] = node
        elif kind == "View":
            relations[data["name"].lower()] = node

    for repo, facts in dotnet_facts_by_repo:
        for usage in facts.sql_usages:
            source = _owner_node(graph, repo, usage.owner_class, usage.owner_method)
            if source is None:
                continue
            if usage.kind == "proc" and usage.proc:
                target = procs.get(usage.proc.lower())
                if target is not None:
                    add_edge(graph, source, target, "EXECUTES", confidence="exact")
                continue
            for name in usage.reads:
                target = relations.get(name.lower())
                if target is not None:
                    add_edge(graph, source, target, "READS", confidence="inferred")
            for name in usage.writes:
                target = tables.get(name.lower())
                if target is not None:
                    add_edge(graph, source, target, "WRITES", confidence="inferred")


def link(graph: nx.MultiDiGraph, dotnet_facts_by_repo) -> dict[str, int]:
    """Run every cross-source link; return simple stats (unresolved API calls)."""
    unresolved = link_api_calls(graph)
    link_code_to_sql(graph, dotnet_facts_by_repo)
    return {"unresolved_api_calls": unresolved}
