"""C#/.NET parser — classes, routes, DI, calls and SQL usage (section 9.2).

Regex-based and deterministic. For each ``*.cs`` file (skipping ``bin``/``obj``) it finds:

* classes (name, ``kind`` from the ``Controller``/``Service``/``Repository`` suffix);
* attribute routes: class ``[Route("...")]`` + method ``[HttpGet("...")]`` → combined route;
* constructor-injected dependencies, resolving ``IOrderService`` → ``OrderService`` (drop ``I``);
* ``CALLS`` between methods, resolving the receiver field via the DI map;
* SQL usage of each string literal — a ``usp_*`` proc name (``EXECUTES``) or inline
  ``SELECT/INSERT/UPDATE/DELETE`` whose tables come from :func:`extract_tables`.

Top-level statements (a program with no class, e.g. ``reports-batch``) are scanned too, so
their SQL is not lost.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from modernizer.parsers.sql_parser import extract_tables

_SKIP_DIRS = {"bin", "obj", ".git"}
_SQL_KEYWORD = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|MERGE)\b", re.IGNORECASE)
_PROC_NAME = re.compile(r"^[A-Za-z_]\w*$")

_CLASS_RE = re.compile(r"\bclass\s+(?P<name>[A-Za-z_]\w*)(?P<rest>[^{]*)\{")
_FIELD_RE = re.compile(
    r"\b(?:private|protected|public|internal)\s+(?:readonly\s+)?"
    r"(?P<type>[A-Za-z_][\w<>.]*)\s+(?P<name>[A-Za-z_]\w*)\s*;"
)
_METHOD_RE = re.compile(
    r"\b(?P<access>public|private|protected|internal)"
    r"(?:\s+(?:static|async|virtual|override|sealed|new|unsafe))*"
    r"\s+(?P<ret>[A-Za-z_][\w<>\[\].,?]*)"
    r"\s+(?P<name>[A-Za-z_]\w*)\s*"
    r"\((?P<params>[^;{}]*)\)\s*"
    r"(?P<body>=>|\{)"
)
_HTTP_ATTR_RE = re.compile(
    r"\[\s*Http(?P<verb>Get|Post|Put|Delete|Patch)"
    r"(?:\(\s*\"(?P<tmpl>[^\"]*)\"\s*\))?\s*\]",
    re.IGNORECASE,
)
_ROUTE_ATTR_RE = re.compile(r"\[\s*Route\(\s*\"(?P<route>[^\"]*)\"\s*\)\s*\]", re.IGNORECASE)
_CALL_RE = re.compile(r"(?P<recv>[A-Za-z_]\w*)\s*\.\s*(?P<method>[A-Za-z_]\w*)\s*\(")
_STRING_RE = re.compile(r"\"(?P<value>(?:\\.|[^\"\\])*)\"")


@dataclass(frozen=True)
class RouteFact:
    repo: str
    http_method: str
    route: str
    controller: str
    handler: str
    file: str
    line: int


@dataclass(frozen=True)
class SqlUsageFact:
    repo: str
    owner_class: str  # a class name, or the file stem for top-level programs
    owner_method: str | None
    kind: str  # 'proc' | 'inline'
    proc: str | None
    reads: frozenset[str]
    writes: frozenset[str]
    sql: str
    file: str
    line: int


@dataclass(frozen=True)
class CallFact:
    repo: str
    caller: str
    callee: str
    file: str
    line: int


@dataclass
class MethodFact:
    repo: str
    class_name: str
    name: str
    signature: str
    file: str
    line: int

    @property
    def qualified_name(self) -> str:
        return f"{self.class_name}.{self.name}"


@dataclass
class ClassFact:
    repo: str
    name: str
    kind: str
    file: str
    line: int
    base_types: tuple[str, ...] = ()
    di_map: dict[str, str] = field(default_factory=dict)
    methods: list[MethodFact] = field(default_factory=list)


@dataclass
class DotNetFacts:
    classes: list[ClassFact] = field(default_factory=list)
    routes: list[RouteFact] = field(default_factory=list)
    methods: list[MethodFact] = field(default_factory=list)
    calls: list[CallFact] = field(default_factory=list)
    sql_usages: list[SqlUsageFact] = field(default_factory=list)

    def get_class(self, name: str) -> ClassFact | None:
        for cls in self.classes:
            if cls.name.lower() == name.lower():
                return cls
        return None

    def find_route(self, http_method: str, route: str) -> RouteFact | None:
        for r in self.routes:
            if r.http_method.upper() == http_method.upper() and r.route.lower() == route.lower():
                return r
        return None

    def sql_usages_for(self, owner_class: str, owner_method: str | None = None) -> list[SqlUsageFact]:
        return [
            u
            for u in self.sql_usages
            if u.owner_class.lower() == owner_class.lower()
            and (owner_method is None or (u.owner_method or "").lower() == owner_method.lower())
        ]


def resolve_type(type_name: str) -> str:
    """``IOrderService`` → ``OrderService``; other names are returned unchanged."""
    core = type_name.split("<", 1)[0].strip()
    if len(core) >= 2 and core[0] == "I" and core[1].isupper():
        return core[1:]
    return core


def _line_at(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _blank_comments(text: str) -> str:
    """Blank ``//`` and ``/* */`` comments while keeping string literals intact."""
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                out.append(" ")
                i += 1
        elif ch == "/" and i + 1 < n and text[i + 1] == "*":
            out.append("  ")
            i += 2
            while i < n and not (text[i] == "*" and i + 1 < n and text[i + 1] == "/"):
                out.append("\n" if text[i] == "\n" else " ")
                i += 1
            if i < n:
                out.append("  ")
                i += 2
        elif ch == '"':
            out.append(ch)
            i += 1
            while i < n and text[i] != '"':
                if text[i] == "\\" and i + 1 < n:
                    out.append(text[i])
                    out.append(text[i + 1])
                    i += 2
                    continue
                out.append(text[i])
                i += 1
            if i < n:
                out.append('"')
                i += 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _match_block(text: str, open_brace: int) -> int:
    """Return the index just past the ``}`` matching the ``{`` at ``open_brace``."""
    depth = 0
    for i in range(open_brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i + 1
    return len(text)


def _method_body_span(text: str, body_marker: int) -> tuple[int, int]:
    """Return ``(start, end)`` of a method body given the ``{`` or ``=>`` position."""
    if text[body_marker] == "{":
        return body_marker, _match_block(text, body_marker)
    # expression body: from after "=>" to the terminating ';'
    i = body_marker + 2
    depth = 0
    while i < len(text):
        ch = text[i]
        if ch in "({[":
            depth += 1
        elif ch in ")}]":
            depth -= 1
        elif ch == ";" and depth == 0:
            return body_marker + 2, i
        i += 1
    return body_marker + 2, len(text)


def _kind_for(name: str) -> str:
    if name.endswith("Controller"):
        return "controller"
    if name.endswith("Service"):
        return "service"
    if name.endswith("Repository"):
        return "repository"
    return "other"


def _combine_route(class_route: str | None, template: str | None, controller: str) -> str:
    base = class_route or ""
    if "[controller]" in base:
        short = controller[: -len("Controller")] if controller.endswith("Controller") else controller
        base = base.replace("[controller]", short.lower())
    parts = [p for p in [base.strip("/"), (template or "").strip("/")] if p]
    return "/".join(parts)


def _di_from_params(params: str) -> dict[str, str]:
    di: dict[str, str] = {}
    for piece in params.split(","):
        tokens = piece.strip().split()
        if len(tokens) >= 2:
            di[tokens[-1]] = resolve_type(tokens[-2])
    return di


def _sql_usage(
    repo: str,
    owner_class: str,
    owner_method: str | None,
    body: str,
    body_start: int,
    text: str,
    file: str,
    known_procs: set[str],
) -> list[SqlUsageFact]:
    usages: list[SqlUsageFact] = []
    for match in _STRING_RE.finditer(body):
        value = match.group("value")
        line = _line_at(text, body_start + match.start())
        is_proc = value in known_procs or (value.startswith("usp_") and _PROC_NAME.match(value))
        if is_proc:
            usages.append(
                SqlUsageFact(
                    repo=repo,
                    owner_class=owner_class,
                    owner_method=owner_method,
                    kind="proc",
                    proc=value,
                    reads=frozenset(),
                    writes=frozenset(),
                    sql=value,
                    file=file,
                    line=line,
                )
            )
        elif _SQL_KEYWORD.search(value):
            reads, writes = extract_tables(value)
            usages.append(
                SqlUsageFact(
                    repo=repo,
                    owner_class=owner_class,
                    owner_method=owner_method,
                    kind="inline",
                    proc=None,
                    reads=frozenset(reads),
                    writes=frozenset(writes),
                    sql=value,
                    file=file,
                    line=line,
                )
            )
    return usages


def parse_text(
    text: str,
    repo: str,
    file: str,
    known_procs: set[str] | None = None,
) -> DotNetFacts:
    known_procs = known_procs or set()
    clean = _blank_comments(text)
    facts = DotNetFacts()
    covered: list[tuple[int, int]] = []

    for class_match in _CLASS_RE.finditer(clean):
        name = class_match.group("name")
        brace = class_match.end() - 1
        class_end = _match_block(clean, brace)
        covered.append((class_match.start(), class_end))
        body_text = clean[brace:class_end]
        body_offset = brace

        base_types = tuple(
            t.strip()
            for t in class_match.group("rest").lstrip(" :").split(",")
            if t.strip()
        )
        cls = ClassFact(
            repo=repo,
            name=name,
            kind=_kind_for(name),
            file=file,
            line=_line_at(text, class_match.start()),
            base_types=base_types,
        )

        # Dependency injection: field declarations + constructor parameters.
        for fmatch in _FIELD_RE.finditer(body_text):
            cls.di_map[fmatch.group("name")] = resolve_type(fmatch.group("type"))
        ctor_re = re.compile(r"\bpublic\s+" + re.escape(name) + r"\s*\((?P<params>[^)]*)\)")
        for cmatch in ctor_re.finditer(body_text):
            cls.di_map.update(_di_from_params(cmatch.group("params")))

        # Class-level [Route("...")] attribute (the nearest one before the class).
        class_route = None
        route_before = list(_ROUTE_ATTR_RE.finditer(clean, 0, class_match.start()))
        if route_before:
            class_route = route_before[-1].group("route")

        # Methods inside this class.
        for mmatch in _METHOD_RE.finditer(body_text):
            method_name = mmatch.group("name")
            m_abs_start = body_offset + mmatch.start()
            head = mmatch.group(0)
            head = re.sub(r"\s+", " ", head[: head.rfind("(")]).strip()
            params_clean = re.sub(r"\s+", " ", mmatch.group("params")).strip()
            method = MethodFact(
                repo=repo,
                class_name=name,
                name=method_name,
                signature=f"{head}({params_clean})",
                file=file,
                line=_line_at(text, m_abs_start),
            )
            cls.methods.append(method)
            facts.methods.append(method)

            body_marker = body_offset + mmatch.start("body")
            b_start, b_end = _method_body_span(clean, body_marker)
            method_body = clean[b_start:b_end]

            # Route (only meaningful on controller actions).
            attr_window = clean[max(0, m_abs_start - 200) : m_abs_start]
            http_attrs = list(_HTTP_ATTR_RE.finditer(attr_window))
            if http_attrs:
                attr = http_attrs[-1]
                facts.routes.append(
                    RouteFact(
                        repo=repo,
                        http_method=attr.group("verb").upper(),
                        route=_combine_route(class_route, attr.group("tmpl"), name),
                        controller=name,
                        handler=method_name,
                        file=file,
                        line=method.line,
                    )
                )

            # Calls to injected dependencies.
            for call in _CALL_RE.finditer(method_body):
                recv = call.group("recv")
                if recv in cls.di_map:
                    facts.calls.append(
                        CallFact(
                            repo=repo,
                            caller=f"{name}.{method_name}",
                            callee=f"{cls.di_map[recv]}.{call.group('method')}",
                            file=file,
                            line=_line_at(text, b_start + call.start()),
                        )
                    )

            facts.sql_usages.extend(
                _sql_usage(repo, name, method_name, method_body, b_start, text, file, known_procs)
            )

        facts.classes.append(cls)

    # Top-level statements (files with no class, e.g. reports-batch programs).
    stem = Path(file).stem
    last = 0
    for start, end in sorted(covered):
        region = clean[last:start]
        facts.sql_usages.extend(
            _sql_usage(repo, stem, None, region, last, text, file, known_procs)
        )
        last = end
    region = clean[last:]
    facts.sql_usages.extend(_sql_usage(repo, stem, None, region, last, text, file, known_procs))

    return facts


def iter_source_files(repo_path: str | Path):
    root = Path(repo_path)
    for path in sorted(root.rglob("*.cs")):
        if any(part in _SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        yield path


def parse_dotnet(repo_path: str | Path, known_procs: set[str] | None = None) -> DotNetFacts:
    """Parse every ``*.cs`` file under ``repo_path`` into a single :class:`DotNetFacts`."""
    root = Path(repo_path)
    repo = root.name
    combined = DotNetFacts()
    for path in iter_source_files(root):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        facts = parse_text(text, repo=repo, file=rel, known_procs=known_procs)
        combined.classes.extend(facts.classes)
        combined.routes.extend(facts.routes)
        combined.methods.extend(facts.methods)
        combined.calls.extend(facts.calls)
        combined.sql_usages.extend(facts.sql_usages)
    return combined


if __name__ == "__main__":  # pragma: no cover - manual inspection helper
    import sys

    from modernizer.config import PROJECT_ROOT

    target = sys.argv[1] if len(sys.argv) > 1 else PROJECT_ROOT / "sample-legacy" / "shop-api"
    result = parse_dotnet(target)
    for route in result.routes:
        print(f"ROUTE {route.http_method:5} {route.route:32} -> {route.controller}.{route.handler}")
    for call in result.calls:
        print(f"CALL  {call.caller} -> {call.callee}")
    for usage in result.sql_usages:
        where = f"{usage.owner_class}.{usage.owner_method}" if usage.owner_method else usage.owner_class
        detail = usage.proc if usage.kind == "proc" else f"reads={sorted(usage.reads)} writes={sorted(usage.writes)}"
        print(f"SQL   {where}: {usage.kind} {detail}")
