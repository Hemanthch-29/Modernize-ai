"""SQL parser — database catalog facts with an ``init.sql`` fallback (section 9.3).

When a live SQL Server connection is available the parser reads ``sys.tables`` /
``sys.columns`` / ``sys.sql_modules`` (read-only). When it is not — for example in tests —
it parses ``sample-legacy/database/init.sql`` with the same regexes, so the whole tool
runs without a database.

:func:`extract_tables` is the shared helper (also used for inline SQL in C#): it returns
``(reads, writes)`` table-name sets for a snippet of SQL.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# FROM/JOIN -> read; INSERT INTO / UPDATE / DELETE FROM -> write.
_READ_RE = re.compile(r"\b(?:FROM|JOIN)\s+(?P<name>[\[\]\w.]+)", re.IGNORECASE)
_INSERT_RE = re.compile(r"\bINSERT\s+INTO\s+(?P<name>[\[\]\w.]+)", re.IGNORECASE)
_UPDATE_RE = re.compile(r"\bUPDATE\s+(?P<name>[\[\]\w.]+)", re.IGNORECASE)
_DELETE_RE = re.compile(r"\bDELETE\s+FROM\s+(?P<name>[\[\]\w.]+)", re.IGNORECASE)

_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?P<name>[\[\]\w.]+)\s*\(", re.IGNORECASE
)
_PROC_RE = re.compile(
    r"CREATE\s+PROC(?:EDURE)?\s+(?P<name>[\[\]\w.]+)(?P<body>.*?)(?=^\s*GO\s*$|\Z)",
    re.IGNORECASE | re.DOTALL | re.MULTILINE,
)
_VIEW_RE = re.compile(
    r"CREATE\s+VIEW\s+(?P<name>[\[\]\w.]+)(?P<body>.*?)(?=^\s*GO\s*$|\Z)",
    re.IGNORECASE | re.DOTALL | re.MULTILINE,
)


@dataclass(frozen=True)
class ColumnFact:
    name: str
    data_type: str


@dataclass(frozen=True)
class TableFact:
    database: str
    name: str
    columns: tuple[ColumnFact, ...]


@dataclass(frozen=True)
class RoutineFact:
    """A stored procedure, view or function and the tables it touches."""

    database: str
    name: str
    kind: str  # 'procedure' | 'view' | 'function'
    definition: str
    reads: frozenset[str]
    writes: frozenset[str]


@dataclass
class SqlFacts:
    database: str
    tables: list[TableFact] = field(default_factory=list)
    routines: list[RoutineFact] = field(default_factory=list)

    def routine(self, name: str) -> RoutineFact | None:
        for routine in self.routines:
            if routine.name.lower() == name.lower():
                return routine
        return None

    def table(self, name: str) -> TableFact | None:
        for table in self.tables:
            if table.name.lower() == name.lower():
                return table
        return None


def _clean_name(name: str) -> str:
    name = name.replace("[", "").replace("]", "")
    if "." in name:
        name = name.split(".")[-1]
    return name


def _blank_sql_comments(text: str) -> str:
    """Replace ``-- ...`` and ``/* ... */`` comments with spaces, preserving newlines."""
    without_line = re.sub(r"--[^\n]*", lambda m: " " * len(m.group(0)), text)
    return re.sub(
        r"/\*.*?\*/",
        lambda m: "".join("\n" if c == "\n" else " " for c in m.group(0)),
        without_line,
        flags=re.DOTALL,
    )


def extract_tables(sql: str) -> tuple[set[str], set[str]]:
    """Return ``(reads, writes)`` table names for a SQL snippet.

    Shared by the DB/``init.sql`` parsing and by inline SQL found in C#.
    """
    clean = _blank_sql_comments(sql)

    writes = {_clean_name(m.group("name")) for m in _INSERT_RE.finditer(clean)}
    writes |= {_clean_name(m.group("name")) for m in _UPDATE_RE.finditer(clean)}
    writes |= {_clean_name(m.group("name")) for m in _DELETE_RE.finditer(clean)}

    # Drop the FROM of "DELETE FROM x" so it is not also counted as a read.
    read_scan = _DELETE_RE.sub(lambda m: m.group(0).replace("FROM", "    ", 1).replace("from", "    ", 1), clean)
    reads = {_clean_name(m.group("name")) for m in _READ_RE.finditer(read_scan)}

    return reads, writes


def _balanced(text: str, open_paren: int) -> tuple[str, int]:
    """Return ``(inner, close_index)`` for the ``(`` at ``open_paren``."""
    depth = 0
    for i in range(open_paren, len(text)):
        char = text[i]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return text[open_paren + 1 : i], i
    return text[open_paren + 1 :], len(text)


def _split_top_level(text: str, sep: str = ",") -> list[str]:
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for char in text:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == sep and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    if current:
        parts.append("".join(current))
    return parts


def _parse_columns(column_block: str) -> tuple[ColumnFact, ...]:
    columns: list[ColumnFact] = []
    for piece in _split_top_level(column_block):
        tokens = piece.split()
        if len(tokens) < 2:
            continue
        first = tokens[0].upper()
        if first in {"CONSTRAINT", "PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "INDEX"}:
            continue
        columns.append(ColumnFact(name=_clean_name(tokens[0]), data_type=tokens[1]))
    return tuple(columns)


def parse_init_sql(path: str | Path, database: str = "ShopDB") -> SqlFacts:
    """Fallback parser: read schema + routines straight from ``init.sql``."""
    raw = Path(path).read_text(encoding="utf-8")
    # Comment-blanking preserves character offsets, so spans found on the blanked text
    # slice the ORIGINAL text — routine definitions keep their comments (e.g. the
    # "10% discount" note), which keyword search and the migration report rely on.
    text = _blank_sql_comments(raw)
    facts = SqlFacts(database=database)

    for match in _TABLE_RE.finditer(text):
        inner, _ = _balanced(text, match.end() - 1)
        facts.tables.append(
            TableFact(
                database=database,
                name=_clean_name(match.group("name")),
                columns=_parse_columns(inner),
            )
        )

    for match in _PROC_RE.finditer(text):
        start, end = match.span(0)
        definition = raw[start:end].strip()
        reads, writes = extract_tables(definition)
        facts.routines.append(
            RoutineFact(
                database=database,
                name=_clean_name(match.group("name")),
                kind="procedure",
                definition=definition,
                reads=frozenset(reads),
                writes=frozenset(writes),
            )
        )

    for match in _VIEW_RE.finditer(text):
        start, end = match.span(0)
        definition = raw[start:end].strip()
        reads, writes = extract_tables(definition)
        facts.routines.append(
            RoutineFact(
                database=database,
                name=_clean_name(match.group("name")),
                kind="view",
                definition=definition,
                reads=frozenset(reads),
                writes=frozenset(writes),
            )
        )

    return facts


def _routine_kind(type_desc: str) -> str:
    upper = (type_desc or "").upper()
    if "VIEW" in upper:
        return "view"
    if "FUNCTION" in upper:
        return "function"
    return "procedure"


def parse_database(conn_str: str, database: str = "ShopDB") -> SqlFacts:
    """Read schema + routines from a live SQL Server via read-only catalog queries."""
    import pyodbc  # imported lazily so tests never need a driver

    facts = SqlFacts(database=database)
    with pyodbc.connect(conn_str, readonly=True) as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT t.name AS table_name, c.name AS column_name, ty.name AS data_type
            FROM sys.tables t
            JOIN sys.columns c ON c.object_id = t.object_id
            JOIN sys.types ty ON ty.user_type_id = c.user_type_id
            ORDER BY t.name, c.column_id
            """
        )
        columns: dict[str, list[ColumnFact]] = {}
        for table_name, column_name, data_type in cursor.fetchall():
            columns.setdefault(table_name, []).append(
                ColumnFact(name=column_name, data_type=data_type)
            )
        facts.tables = [
            TableFact(database=database, name=name, columns=tuple(cols))
            for name, cols in columns.items()
        ]

        cursor.execute(
            """
            SELECT o.name, o.type_desc, m.definition
            FROM sys.sql_modules m
            JOIN sys.objects o ON o.object_id = m.object_id
            """
        )
        for name, type_desc, definition in cursor.fetchall():
            definition = definition or ""
            reads, writes = extract_tables(definition)
            facts.routines.append(
                RoutineFact(
                    database=database,
                    name=name,
                    kind=_routine_kind(type_desc),
                    definition=definition,
                    reads=frozenset(reads),
                    writes=frozenset(writes),
                )
            )

    return facts


def parse_sql(
    conn_str: str | None = None,
    init_sql_path: str | Path | None = None,
    database: str = "ShopDB",
) -> SqlFacts:
    """Prefer a live DB; fall back to ``init.sql`` when it is unavailable."""
    if conn_str:
        try:
            return parse_database(conn_str, database=database)
        except Exception:  # pragma: no cover - depends on local DB availability
            pass
    if init_sql_path is None:
        from modernizer.config import INIT_SQL_PATH

        init_sql_path = INIT_SQL_PATH
    return parse_init_sql(init_sql_path, database=database)


if __name__ == "__main__":  # pragma: no cover - manual inspection helper
    import sys

    from modernizer.config import INIT_SQL_PATH

    target = sys.argv[1] if len(sys.argv) > 1 else INIT_SQL_PATH
    sql_facts = parse_init_sql(target)
    print(f"database: {sql_facts.database}")
    for table in sql_facts.tables:
        cols = ", ".join(f"{c.name}:{c.data_type}" for c in table.columns)
        print(f"  table {table.name}  ({cols})")
    for routine in sql_facts.routines:
        print(
            f"  {routine.kind} {routine.name}  reads={sorted(routine.reads)} writes={sorted(routine.writes)}"
        )
