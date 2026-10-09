"""Indexer — turn parser facts into the knowledge graph (sections 8 and 9).

Reads ``portfolio.yaml``, runs the three parsers, builds the nodes and intra-source edges,
then hands off to :mod:`modernizer.linker` for the cross-source links. The shared ``ShopDB``
is parsed once (both apps ``CONTAINS`` the single ``Database`` node). The result is a
NetworkX graph, saved to ``output/graph.json`` by :func:`build_and_save`.
"""
from __future__ import annotations

from pathlib import Path

import networkx as nx

from modernizer import linker
from modernizer.config import (
    RepoConfig,
    get_connection_string,
    load_env,
    load_portfolio,
)
from modernizer.graph_store import (
    GRAPH_PATH,
    add_edge,
    add_node,
    apicall_id,
    app_id,
    class_id,
    db_id,
    endpoint_id,
    method_id,
    new_graph,
    proc_id,
    repo_id,
    save_graph,
    table_id,
    ui_id,
    view_id,
)
from modernizer.linker import normalize_url
from modernizer.parsers.dotnet_parser import DotNetFacts, parse_dotnet
from modernizer.parsers.react_parser import parse_react
from modernizer.parsers.sql_parser import SqlFacts, parse_sql

_UNSET = object()


def _add_sql_nodes(graph: nx.MultiDiGraph, database: str, facts: SqlFacts) -> None:
    for table in facts.tables:
        tid = table_id(database, table.name)
        add_node(
            graph,
            tid,
            type="Table",
            name=table.name,
            columns=[{"name": c.name, "type": c.data_type} for c in table.columns],
        )
        add_edge(graph, db_id(database), tid, "CONTAINS")

    for routine in facts.routines:
        if routine.kind == "view":
            node_id, node_type = view_id(database, routine.name), "View"
        else:
            node_id, node_type = proc_id(database, routine.name), "StoredProcedure"
        add_node(
            graph,
            node_id,
            type=node_type,
            name=routine.name,
            definition=routine.definition,
            routine_kind=routine.kind,
        )
        add_edge(graph, db_id(database), node_id, "CONTAINS")
        for name in routine.reads:
            target = _relation_node(graph, database, name)
            if target is not None:
                add_edge(graph, node_id, target, "READS", confidence="inferred")
        for name in routine.writes:
            target = table_id(database, name)
            if graph.has_node(target):
                add_edge(graph, node_id, target, "WRITES", confidence="inferred")


def _relation_node(graph: nx.MultiDiGraph, database: str, name: str) -> str | None:
    """A READS target may be a table or (less often) a view."""
    table = table_id(database, name)
    if graph.has_node(table):
        return table
    view = view_id(database, name)
    if graph.has_node(view):
        return view
    return None


def _add_react_nodes(graph: nx.MultiDiGraph, repo: RepoConfig, app: str) -> None:
    for fact in parse_react(repo.abs_path):
        component = ui_id(repo.name, fact.component)
        add_node(
            graph,
            component,
            type="UIComponent",
            name=fact.component,
            app=app,
            repo=repo.name,
            file=fact.file,
        )
        add_edge(graph, repo_id(repo.name), component, "CONTAINS")

        normalized = normalize_url(fact.raw_url)
        call = apicall_id(repo.name, fact.component, fact.method, normalized)
        add_node(
            graph,
            call,
            type="ApiCall",
            name=f"{fact.method} {normalized}",
            app=app,
            repo=repo.name,
            file=fact.file,
            line=fact.line,
            method=fact.method,
            raw_url=fact.raw_url,
            normalized_url=normalized,
        )
        add_edge(graph, component, call, "MAKES_CALL")


def _add_dotnet_nodes(graph: nx.MultiDiGraph, repo: RepoConfig, app: str, facts: DotNetFacts) -> None:
    for cls in facts.classes:
        cid = class_id(repo.name, cls.name)
        add_node(
            graph,
            cid,
            type="CSharpClass",
            name=cls.name,
            app=app,
            repo=repo.name,
            file=cls.file,
            line=cls.line,
            kind=cls.kind,
        )
        add_edge(graph, repo_id(repo.name), cid, "CONTAINS")
        for method in cls.methods:
            mid = method_id(repo.name, method.qualified_name)
            add_node(
                graph,
                mid,
                type="CSharpMethod",
                name=method.qualified_name,
                app=app,
                repo=repo.name,
                file=method.file,
                line=method.line,
                signature=method.signature,
                kind=cls.kind,
            )
            add_edge(graph, cid, mid, "CONTAINS")

    # Top-level programs (e.g. reports-batch) own SQL without a parsed class — make sure a
    # node exists so its EXECUTES/READS/WRITES edges have a source.
    for usage in facts.sql_usages:
        if usage.owner_method and graph.has_node(
            method_id(repo.name, f"{usage.owner_class}.{usage.owner_method}")
        ):
            continue
        cid = class_id(repo.name, usage.owner_class)
        if not graph.has_node(cid):
            add_node(
                graph,
                cid,
                type="CSharpClass",
                name=usage.owner_class,
                app=app,
                repo=repo.name,
                file=usage.file,
                line=usage.line,
                kind="program",
            )
            add_edge(graph, repo_id(repo.name), cid, "CONTAINS")

    for route in facts.routes:
        normalized = normalize_url(route.route)
        eid = endpoint_id(repo.name, route.http_method, normalized)
        add_node(
            graph,
            eid,
            type="ApiEndpoint",
            name=f"{route.http_method} {normalized}",
            app=app,
            repo=repo.name,
            file=route.file,
            line=route.line,
            method=route.http_method,
            route=route.route,
            normalized_url=normalized,
            handler=f"{route.controller}.{route.handler}",
        )
        add_edge(graph, repo_id(repo.name), eid, "CONTAINS")
        handler = method_id(repo.name, f"{route.controller}.{route.handler}")
        if graph.has_node(handler):
            add_edge(graph, eid, handler, "IMPLEMENTED_BY", confidence="exact")

    for call in facts.calls:
        source = method_id(repo.name, call.caller)
        target = method_id(repo.name, call.callee)
        if graph.has_node(source) and graph.has_node(target):
            add_edge(graph, source, target, "CALLS", confidence="exact")


def build_graph(conn_str: str | None | object = _UNSET) -> tuple[nx.MultiDiGraph, dict]:
    """Build the whole knowledge graph.

    ``conn_str`` defaults to ``SHOPDB_CONN`` from the environment; pass ``None`` to force the
    ``init.sql`` fallback (used by the tests so they never need a database).
    """
    load_env()
    if conn_str is _UNSET:
        conn_str = get_connection_string("SHOPDB_CONN")

    portfolio = load_portfolio()
    graph = new_graph()

    # Applications, repos and the (de-duplicated) shared databases.
    for application in portfolio.applications:
        add_node(
            graph,
            app_id(application.name),
            type="Application",
            name=application.name,
            app=application.name,
            owner=application.owner,
            wave=application.wave,
            status=application.status,
        )
        for repo in application.repos:
            add_node(
                graph,
                repo_id(repo.name),
                type="Repo",
                name=repo.name,
                app=application.name,
                repo_type=repo.type,
            )
            add_edge(graph, app_id(application.name), repo_id(repo.name), "CONTAINS")
        for database in application.databases:
            add_node(graph, db_id(database.name), type="Database", name=database.name, db_type=database.type)
            add_edge(graph, app_id(application.name), db_id(database.name), "CONTAINS")

    # Databases are parsed once each, even when shared by several apps.
    sql_facts: dict[str, SqlFacts] = {}
    for database in portfolio.databases():
        facts = parse_sql(conn_str if isinstance(conn_str, str) else None, database=database.name)
        sql_facts[database.name] = facts
        _add_sql_nodes(graph, database.name, facts)

    known_procs = {
        routine.name
        for facts in sql_facts.values()
        for routine in facts.routines
        if routine.kind == "procedure"
    }

    # Source repos.
    dotnet_facts_by_repo: list[tuple[str, DotNetFacts]] = []
    for application in portfolio.applications:
        for repo in application.repos:
            if repo.type == "react":
                _add_react_nodes(graph, repo, application.name)
            elif repo.type == "dotnet":
                facts = parse_dotnet(repo.abs_path, known_procs=known_procs)
                _add_dotnet_nodes(graph, repo, application.name, facts)
                dotnet_facts_by_repo.append((repo.name, facts))

    link_stats = linker.link(graph, dotnet_facts_by_repo)

    stats = {
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        **link_stats,
    }
    return graph, stats


def build_and_save(conn_str: str | None | object = _UNSET, path: str | Path = GRAPH_PATH) -> tuple[Path, dict]:
    graph, stats = build_graph(conn_str)
    saved = save_graph(graph, path)
    return saved, stats


if __name__ == "__main__":  # pragma: no cover - manual inspection helper
    saved_path, index_stats = build_and_save()
    print(f"wrote {saved_path}")
    print(index_stats)