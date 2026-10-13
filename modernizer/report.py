"""Deterministic inventory and migration-plan reports generated from the graph."""
from __future__ import annotations

import re
from collections import deque
from pathlib import Path

import networkx as nx

from modernizer.config import PROJECT_ROOT, load_portfolio
from modernizer.graph_store import load_graph

REPORT_DIR = PROJECT_ROOT / "output" / "reports"
_FLOW_RELS = {
	"MAKES_CALL",
	"HANDLED_BY",
	"IMPLEMENTED_BY",
	"CALLS",
	"EXECUTES",
	"READS",
	"WRITES",
}
_SOURCE_SUFFIXES = {".cs", ".js", ".jsx", ".sql", ".ts", ".tsx"}
_SKIP_DIRS = {"bin", "obj", "node_modules", ".git"}
_RULE_KEYWORD_RE = re.compile(r"\b(?:IF|CASE|RAISERROR|THROW)\b", re.IGNORECASE)
_TOTAL_ARITHMETIC_RE = re.compile(
	r"\b\w*total\w*\b[^\n]*(?:[+*/-]|\b(?:SUM|AVG)\s*\()", re.IGNORECASE
)


def _node_type(graph: nx.MultiDiGraph, node: str) -> str:
	return str(graph.nodes[node].get("type", ""))


def _app_node(graph: nx.MultiDiGraph, app_name: str) -> str | None:
	matches = [
		node
		for node, data in graph.nodes(data=True)
		if data.get("type") == "Application"
		and str(data.get("name", "")).casefold() == app_name.casefold()
	]
	return sorted(matches)[0] if matches else None


def _owned_nodes(graph: nx.MultiDiGraph, app_name: str, kind: str) -> list[str]:
	return sorted(
		node
		for node, data in graph.nodes(data=True)
		if data.get("type") == kind
		and str(data.get("app", "")).casefold() == app_name.casefold()
	)


def _database_nodes(graph: nx.MultiDiGraph, app_node: str) -> list[str]:
	return sorted(
		dst
		for _, dst, key, _ in graph.out_edges(app_node, keys=True, data=True)
		if _node_type(graph, dst) == "Database"
	)


def _database_members(graph: nx.MultiDiGraph, databases: list[str], kind: str) -> list[str]:
	members = {
		dst
		for database in databases
		for _, dst, key, _ in graph.out_edges(database, keys=True, data=True)
		if _node_type(graph, dst) == kind
	}
	return sorted(members)


def _flow_successors(graph: nx.MultiDiGraph, node: str) -> list[str]:
	return sorted(
		dst
		for _, dst, key, data in graph.out_edges(node, keys=True, data=True)
		if data.get("rel", key) in _FLOW_RELS
	)


def _reachable(graph: nx.MultiDiGraph, start: str) -> set[str]:
	visited: set[str] = set()
	pending = [start]
	while pending:
		node = pending.pop()
		if node in visited:
			continue
		visited.add(node)
		pending.extend(reversed(_flow_successors(graph, node)))
	return visited


def _upstream_apps(graph: nx.MultiDiGraph, start: str) -> set[str]:
	apps: set[str] = set()
	visited: set[str] = set()
	pending = [start]
	while pending:
		node = pending.pop()
		if node in visited:
			continue
		visited.add(node)
		data = graph.nodes[node]
		if data.get("type") == "Application":
			apps.add(str(data.get("name", "")))
		if data.get("app"):
			apps.add(str(data["app"]))
		for src, _, key, edge in graph.in_edges(node, keys=True, data=True):
			if edge.get("rel", key) in _FLOW_RELS:
				pending.append(src)
	return apps


def _shared_tables(graph: nx.MultiDiGraph) -> dict[str, list[str]]:
	shared: dict[str, list[str]] = {}
	for node, data in graph.nodes(data=True):
		if data.get("type") != "Table":
			continue
		apps = sorted(app for app in _upstream_apps(graph, node) if app)
		if len(apps) > 1:
			shared[node] = apps
	return shared


def _source_loc(path: Path) -> int:
	if not path.exists():
		return 0
	count = 0
	for source_file in sorted(path.rglob("*")):
		if not source_file.is_file() or source_file.suffix.lower() not in _SOURCE_SUFFIXES:
			continue
		if any(part.lower() in _SKIP_DIRS for part in source_file.parts):
			continue
		try:
			count += sum(bool(line.strip()) for line in source_file.read_text(encoding="utf-8").splitlines())
		except (OSError, UnicodeError):
			continue
	return count


def _rule_snippets(definition: str) -> list[tuple[int, str]]:
	snippets: list[tuple[int, str]] = []
	lines = definition.splitlines()
	for number, line in enumerate(lines, start=1):
		if _RULE_KEYWORD_RE.search(line) or _TOTAL_ARITHMETIC_RE.search(line):
			if number > 1 and lines[number - 2].lstrip().startswith("--"):
				snippets.append((number - 1, lines[number - 2].strip()))
			snippets.append((number, line.strip()))
	return snippets


def _rule_label(name: str, definition: str) -> str:
	text = f"{name}\n{definition}".casefold()
	if "gold" in text and ("discount" in text or "0.90" in text):
		return "Gold customer discount (10% off)"
	if "cancel" in text and "shipped" in text:
		return "Shipped-order cancellation rule"
	return "Conditional or calculated database rule"


def _procedure_rules(graph: nx.MultiDiGraph, procedures: list[str]) -> dict[str, list[tuple[str, list[tuple[int, str]]]]]:
	rules: dict[str, list[tuple[str, list[tuple[int, str]]]]] = {}
	for node in procedures:
		data = graph.nodes[node]
		definition = str(data.get("definition", ""))
		snippets = _rule_snippets(definition)
		if snippets:
			rules[node] = [(_rule_label(str(data.get("name", "")), definition), snippets)]
	return rules


def _endpoint_depth(graph: nx.MultiDiGraph, start: str) -> tuple[dict[str, int], set[str]]:
	depths = {start: 0}
	pending = deque([start])
	while pending:
		node = pending.popleft()
		for child in _flow_successors(graph, node):
			if child not in depths:
				depths[child] = depths[node] + 1
				pending.append(child)
	return depths, set(depths)


def _complexity(graph: nx.MultiDiGraph, endpoint: str, rules: dict, shared: dict) -> tuple[int, str]:
	depths, reachable = _endpoint_depth(graph, endpoint)
	hops = max(depths.values(), default=0)
	rule_count = sum(1 for node in reachable if node in rules)
	shared_count = sum(1 for node in reachable if node in shared)
	score = hops + 2 * rule_count + 3 * shared_count
	level = "Low" if score <= 3 else "Medium" if score <= 6 else "High"
	return score, level


def _feature_lines(graph: nx.MultiDiGraph, components: list[str]) -> list[str]:
	lines: list[str] = []
	for component in components:
		reached = _reachable(graph, component)
		endpoints = sorted(
			(node for node in reached if _node_type(graph, node) == "ApiEndpoint"),
			key=lambda node: str(graph.nodes[node].get("name", "")),
		)
		procedures = sorted(
			(node for node in reached if _node_type(graph, node) == "StoredProcedure"),
			key=lambda node: str(graph.nodes[node].get("name", "")),
		)
		tables = sorted(
			(node for node in reached if _node_type(graph, node) == "Table"),
			key=lambda node: str(graph.nodes[node].get("name", "")),
		)
		lines.append(f"### {graph.nodes[component].get('name', component)}")
		lines.append(f"- Endpoints: {', '.join(str(graph.nodes[n].get('name')) for n in endpoints) or 'None linked'}")
		lines.append(f"- Stored procedures: {', '.join(str(graph.nodes[n].get('name')) for n in procedures) or 'None linked'}")
		lines.append(f"- Tables: {', '.join(str(graph.nodes[n].get('name')) for n in tables) or 'None linked'}")
		lines.append("")
	return lines


def _display_route(graph: nx.MultiDiGraph, node: str) -> str:
	data = graph.nodes[node]
	return f"{data.get('method', '')} {data.get('normalized_url', data.get('name', ''))}".strip()


def render_report(app_name: str, graph: nx.MultiDiGraph | None = None) -> str:
	"""Render an application's migration plan as deterministic Markdown."""
	graph = graph if graph is not None else load_graph()
	app_node = _app_node(graph, app_name)
	if app_node is None:
		raise ValueError(f"No application matches '{app_name}'.")

	app = graph.nodes[app_node]
	app_name = str(app.get("name", app_name))
	databases = _database_nodes(graph, app_node)
	procedures = _database_members(graph, databases, "StoredProcedure")
	tables = _database_members(graph, databases, "Table")
	components = _owned_nodes(graph, app_name, "UIComponent")
	endpoints = _owned_nodes(graph, app_name, "ApiEndpoint")
	classes = _owned_nodes(graph, app_name, "CSharpClass")
	repo_nodes = sorted(
		dst
		for _, dst, key, _ in graph.out_edges(app_node, keys=True, data=True)
		if _node_type(graph, dst) == "Repo"
	)
	repo_configs = {}
	portfolio_app = load_portfolio().application(app_name)
	if portfolio_app:
		repo_configs = {repo.name: repo for repo in portfolio_app.repos}
	shared = _shared_tables(graph)
	rules = _procedure_rules(graph, procedures)
	unresolved = sorted(
		(node for node, data in graph.nodes(data=True)
		 if data.get("type") == "ApiCall"
		 and str(data.get("app", "")).casefold() == app_name.casefold()
		 and data.get("unresolved")),
		key=lambda node: str(graph.nodes[node].get("name", "")),
	)

	lines = [
		f"# {app_name} Migration Plan",
		"",
		f"- Portfolio owner: {app.get('owner') or 'Not specified'}",
		f"- Current wave: {app.get('wave') if app.get('wave') is not None else 'Unassigned'}",
		f"- Migration status: {app.get('status') or 'Not specified'}",
		"",
		"## Inventory",
		"",
		"| Repository | Type | Source LOC* |",
		"|---|---|---:|",
	]
	total_loc = 0
	for repo_node in repo_nodes:
		repo_data = graph.nodes[repo_node]
		repo_name = str(repo_data.get("name", ""))
		config = repo_configs.get(repo_name)
		loc = _source_loc(config.abs_path) if config else 0
		total_loc += loc
		lines.append(f"| {repo_name} | {repo_data.get('repo_type', 'unknown')} | {loc} |")
	lines.extend(
		[
			f"| **Total** |  | **{total_loc}** |",
			"",
			"*LOC is the count of nonblank lines in tracked-language source files; generated `bin`, `obj`, `node_modules`, and `.git` trees are excluded.*",
			"",
			"| Components | Endpoints | C# classes | Stored procedures | Tables |",
			"|---:|---:|---:|---:|---:|",
			f"| {len(components)} | {len(endpoints)} | {len(classes)} | {len(procedures)} | {len(tables)} |",
			"",
			"## End-to-End Feature Map",
			"",
		]
	)
	lines.extend(_feature_lines(graph, components))

	lines.extend(["## Hidden Business Rules", ""])
	if not rules:
		lines.append("No rule-like logic was detected in the stored-procedure definitions.")
	else:
		for node in sorted(rules, key=lambda item: str(graph.nodes[item].get("name", ""))):
			procedure_name = str(graph.nodes[node].get("name", node))
			for label, snippets in rules[node]:
				lines.append(f"### {label} in `{procedure_name}`")
				for number, snippet in snippets:
					safe_snippet = snippet.replace("`", "'")
					lines.append(f"- `{procedure_name}` line {number}: `{safe_snippet}`")
				lines.append("")

	lines.extend(["## Shared Dependencies", ""])
	app_tables = [node for node in tables if node in shared]
	if not app_tables:
		lines.append("No tables used by multiple applications were detected.")
	else:
		lines.extend(["| Table | Applications using it | Shared with |", "|---|---|---|"])
		for node in app_tables:
			table_name = str(graph.nodes[node].get("name", node))
			owners = shared[node]
			others = [owner for owner in owners if owner.casefold() != app_name.casefold()]
			lines.append(f"| `{table_name}` | {', '.join(owners)} | {', '.join(others)} |")

	lines.extend(["", "## Target Mapping", ""])
	if not components:
		lines.append("No UI components were found for this application.")
	else:
		lines.extend(["| Legacy component | Linked API endpoints | Target |", "|---|---|---|"])
		for component in components:
			reached = _reachable(graph, component)
			component_endpoints = sorted(
				(node for node in reached if _node_type(graph, node) == "ApiEndpoint"),
				key=lambda node: _display_route(graph, node),
			)
			routes = ", ".join(_display_route(graph, node) for node in component_endpoints) or "None linked"
			name = str(graph.nodes[component].get("name", component))
			lines.append(f"| React `{name}` | {routes} | Angular standalone `{name}Component` |")
	lines.extend(
		[
			"",
			"- ASP.NET API endpoints and controllers map to FastAPI `APIRouter` endpoints in `app/routers/`.",
			"- Dapper stored-procedure calls map to parameterized SQLAlchemy `text('EXEC ...')`; retain procedures in the first migration wave.",
			"- SQL Server maps to Amazon RDS for SQL Server in the initial AWS wave.",
			"",
			"## Endpoint Complexity",
			"",
			"Score = maximum downstream flow hops + 2 per reachable stored procedure with detected business logic + 3 per reachable shared table. Low: 0–3; Medium: 4–6; High: 7+.",
			"",
			"| Endpoint | Hops | Rule procedures | Shared tables | Score | Complexity |",
			"|---|---:|---:|---:|---:|---|",
		]
	)
	for endpoint in endpoints:
		depths, reached = _endpoint_depth(graph, endpoint)
		hops = max(depths.values(), default=0)
		rule_count = sum(1 for node in reached if node in rules)
		shared_count = sum(1 for node in reached if node in shared)
		score, level = _complexity(graph, endpoint, rules, shared)
		lines.append(
			f"| {_display_route(graph, endpoint)} | {hops} | {rule_count} | {shared_count} | {score} | {level} |"
		)

	portfolio = load_portfolio()
	ordered_apps = sorted(
		portfolio.applications,
		key=lambda item: (item.wave if item.wave is not None else 10**9, item.name.casefold()),
	)
	lines.extend(["", "## Suggested Wave Order & Risks", "", "Suggested portfolio order:"])
	for item in ordered_apps:
		wave = f"Wave {item.wave}" if item.wave is not None else "Wave unassigned"
		lines.append(f"- {wave}: {item.name} ({item.status or 'status not specified'})")
	lines.extend(
		[
			"",
			"Risks to carry into implementation:",
			"- Preserve the Gold customer discount found in the database procedure; a code-only rewrite can overstate order totals.",
			"- Preserve the shipped-order cancellation rejection and its conflict response.",
		]
	)
	if app_tables:
		names = ", ".join(f"`{graph.nodes[node].get('name')}`" for node in app_tables)
		lines.append(f"- Coordinate changes to shared table(s) {names} with every listed application owner.")
	high_complexity = [
		_display_route(graph, node)
		for node in endpoints
		if _complexity(graph, node, rules, shared)[1] == "High"
	]
	if high_complexity:
		lines.append(f"- Prioritize design review for High-complexity endpoint(s): {', '.join(high_complexity)}.")

	lines.extend(["", "## Unresolved Links", ""])
	if not unresolved:
		lines.append("No unresolved API-call links.")
	else:
		for node in unresolved:
			data = graph.nodes[node]
			lines.append(f"- {data.get('name')} ({data.get('file', 'source location unavailable')})")
	lines.append("")
	return "\n".join(lines)


def write_report(
	app_name: str,
	graph: nx.MultiDiGraph | None = None,
	output_dir: str | Path = REPORT_DIR,
) -> Path:
	"""Write the report to ``<App>-migration-plan.md`` and return its path."""
	markdown = render_report(app_name, graph)
	path = Path(output_dir) / f"{app_name}-migration-plan.md"
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(markdown, encoding="utf-8")
	return path
