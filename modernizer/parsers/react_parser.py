"""React/TypeScript parser — find the HTTP API calls a screen makes (section 9.1).

Scans ``*.ts/*.tsx/*.js/*.jsx`` under a repo (skipping ``node_modules``) and returns a
flat list of :class:`ApiCallFact`. It is deliberately regex-based and deterministic; it
recognises two patterns:

* ``<identifier>.(get|post|put|delete|patch)(<url>)`` — axios / a shared client, where the
  identifier and the method may sit on separate lines (fluent ``client\n  .get(...)``).
* ``fetch(<url>)`` — method is ``GET`` unless a ``{ method: 'POST' }`` option follows.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

SOURCE_SUFFIXES = {".ts", ".tsx", ".js", ".jsx"}
_SKIP_DIRS = {"node_modules", "dist", "build", ".git", ".vite"}

# <ident>.get(`...`) / axios.post('...'); identifier and dot may be split across lines.
_HTTP_CALL = re.compile(
    r"(?P<ident>[A-Za-z_$][\w$]*)\s*\.\s*(?P<method>get|post|put|delete|patch)\s*\(\s*"
    r"(?P<q>['\"`])(?P<url>(?:\\.|[^'\"`\\])*)(?P=q)",
    re.IGNORECASE,
)

# fetch('...') / fetch(`...`); the options object (if any) is inspected for a method.
_FETCH_CALL = re.compile(
    r"\bfetch\s*\(\s*(?P<q>['\"`])(?P<url>(?:\\.|[^'\"`\\])*)(?P=q)",
    re.IGNORECASE,
)
_FETCH_METHOD = re.compile(r"method\s*:\s*['\"](?P<method>[A-Za-z]+)['\"]", re.IGNORECASE)


@dataclass(frozen=True)
class ApiCallFact:
    """One HTTP call a UI component makes (a raw fact, not a graph node)."""

    component: str
    file: str
    line: int
    method: str
    raw_url: str


def _line_at(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _call_args(text: str, open_paren: int) -> str:
    """Return the text between ``(`` at ``open_paren`` and its matching ``)``."""
    depth = 0
    for i in range(open_paren, len(text)):
        char = text[i]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return text[open_paren + 1 : i]
    return text[open_paren + 1 :]


def parse_file(path: Path, component: str | None = None) -> list[ApiCallFact]:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    name = component or Path(path).stem
    rel = Path(path).name
    facts: list[ApiCallFact] = []

    for match in _HTTP_CALL.finditer(text):
        url = match.group("url")
        if "/" not in url:  # skip things like searchParams.get('key')
            continue
        facts.append(
            ApiCallFact(
                component=name,
                file=rel,
                line=_line_at(text, match.start()),
                method=match.group("method").upper(),
                raw_url=url,
            )
        )

    for match in _FETCH_CALL.finditer(text):
        url = match.group("url")
        if "/" not in url:
            continue
        open_paren = text.index("(", match.start())
        args = _call_args(text, open_paren)
        method_opt = _FETCH_METHOD.search(args)
        method = method_opt.group("method").upper() if method_opt else "GET"
        facts.append(
            ApiCallFact(
                component=name,
                file=rel,
                line=_line_at(text, match.start()),
                method=method,
                raw_url=url,
            )
        )

    return facts


def iter_source_files(repo_path: str | Path):
    root = Path(repo_path)
    for path in sorted(root.rglob("*")):
        if path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        if any(part in _SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        yield path


def parse_react(repo_path: str | Path) -> list[ApiCallFact]:
    """Return every API call found under ``repo_path`` (component = file stem)."""
    root = Path(repo_path)
    facts: list[ApiCallFact] = []
    for path in iter_source_files(root):
        for fact in parse_file(path):
            rel = path.relative_to(root).as_posix()
            facts.append(
                ApiCallFact(
                    component=fact.component,
                    file=rel,
                    line=fact.line,
                    method=fact.method,
                    raw_url=fact.raw_url,
                )
            )
    return facts


if __name__ == "__main__":  # pragma: no cover - manual inspection helper
    import sys

    from modernizer.config import PROJECT_ROOT

    target = sys.argv[1] if len(sys.argv) > 1 else PROJECT_ROOT / "sample-legacy" / "shop-ui"
    for fact in parse_react(target):
        print(f"{fact.component:16} {fact.method:6} {fact.raw_url}  ({fact.file}:{fact.line})")
