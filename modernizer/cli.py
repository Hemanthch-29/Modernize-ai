"""Command-line interface (Typer) — the "connecting" part run from a terminal.

    python -m modernizer.cli index
    python -m modernizer.cli trace OrderDetails
    python -m modernizer.cli dependents Orders
    python -m modernizer.cli definition usp_GetOrderById
    python -m modernizer.cli search discount
"""
from __future__ import annotations

import typer

from modernizer import queries
from modernizer.graph_store import load_graph
from modernizer.indexer import build_and_save

app = typer.Typer(add_completion=False, help="ModernizeAI — index and query the knowledge graph.")


def _location(node: dict) -> str:
    file = node.get("file")
    if not file:
        return ""
    line = node.get("line")
    return f"  ({file}:{line})" if line else f"  ({file})"


def _print_tree(node: dict, indent: int = 0, shown_defs: set[str] | None = None) -> None:
    shown_defs = shown_defs if shown_defs is not None else set()
    pad = "  " * indent
    rel = node.get("edge")
    arrow = f"└─{rel}─▶ " if rel else ""
    confidence = node.get("edge_confidence")
    tag = f"  [{confidence}]" if confidence else ""
    typer.echo(f"{pad}{arrow}{node['type']} {node['name']}{_location(node)}{tag}")

    # Show stored-procedure / view SQL once, so business rules (the Gold discount) are visible.
    definition = node.get("definition")
    if definition and node["type"] in {"StoredProcedure", "View"} and node["id"] not in shown_defs:
        shown_defs.add(node["id"])
        for text_line in str(definition).splitlines():
            typer.echo(f"{pad}      | {text_line}")

    for child in node.get("children", []):
        _print_tree(child, indent + 1, shown_defs)


@app.command()
def index() -> None:
    """Parse every repo + the database and write ``output/graph.json``."""
    path, stats = build_and_save()
    typer.echo(f"Wrote {path}")
    typer.echo(
        f"nodes={stats['nodes']} edges={stats['edges']} "
        f"unresolved_api_calls={stats['unresolved_api_calls']}"
    )


@app.command()
def trace(name: str) -> None:
    """Trace a UI component / endpoint / method down to the database tables."""
    result = queries.trace_feature(name, graph=load_graph())
    if not result["found"]:
        typer.echo(f"No node matches '{name}'.")
        raise typer.Exit(code=1)
    _print_tree(result["tree"])


@app.command()
def dependents(name: str) -> None:
    """List everything upstream of a table/proc/class, across all apps."""
    result = queries.get_dependents(name, graph=load_graph())
    if not result["found"]:
        typer.echo(f"No node matches '{name}'.")
        raise typer.Exit(code=1)
    typer.echo(f"Dependents of {result['target']}:")
    for node in result["dependents"]:
        app_tag = f"  [{node['app']}]" if node.get("app") else ""
        typer.echo(f"  {node['type']:16} {node['name']}{app_tag}{_location(node)}")


@app.command()
def definition(name: str) -> None:
    """Show the source / SQL text (plus file and line) for a node."""
    result = queries.get_definition(name, graph=load_graph())
    if not result.get("found"):
        typer.echo(f"No node matches '{name}'.")
        raise typer.Exit(code=1)
    typer.echo(f"{result['type']} {result['name']}{_location(result)}")
    text = result.get("definition") or result.get("signature")
    if text:
        typer.echo("")
        typer.echo(str(text))
    else:
        typer.echo("(no stored definition for this node type)")


@app.command()
def search(text: str) -> None:
    """Keyword search over node names and their source / SQL text."""
    result = queries.search(text, graph=load_graph())
    typer.echo(f"{result['count']} match(es) for '{text}':")
    for node in result["results"]:
        typer.echo(f"  {node['type']:16} {node['name']}{_location(node)}")


if __name__ == "__main__":
    app()
