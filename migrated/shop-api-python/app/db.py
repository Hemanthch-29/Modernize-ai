"""SQLAlchemy engine for ShopDB via ``mssql+pyodbc`` (connection from ``SHOPDB_CONN``).

Mirrors the legacy ``appsettings.json`` connection, but the secret lives only in the
environment / ``.env`` (never in code or YAML).
"""
from __future__ import annotations

import os
import urllib.parse
from collections.abc import Iterator
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, Engine

# ``.env`` lives at the repository root (…/modernize-ai/.env); fall back to a cwd-upward search.
_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(_ROOT_ENV if _ROOT_ENV.exists() else None)


def _build_engine() -> Engine:
    conn = os.environ.get("SHOPDB_CONN")
    if not conn:
        raise RuntimeError(
            "SHOPDB_CONN is not set. Copy .env.example to .env (see PROJECT_CONTEXT.md section 7)."
        )
    url = "mssql+pyodbc:///?odbc_connect=" + urllib.parse.quote_plus(conn)
    return create_engine(url, pool_pre_ping=True)


engine: Engine = _build_engine()


def get_connection() -> Iterator[Connection]:
    """FastAPI dependency: yield a pooled connection, closed after the request."""
    with engine.connect() as connection:
        yield connection
