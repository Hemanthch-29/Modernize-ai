"""Load ``portfolio.yaml`` and environment configuration (``.env``).

See PROJECT_CONTEXT.md sections 7 and 9. Secrets never live in YAML: a database's
``connection_env`` names the environment variable that holds its connection string.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PORTFOLIO_PATH = PROJECT_ROOT / "portfolio.yaml"
ENV_PATH = PROJECT_ROOT / ".env"
INIT_SQL_PATH = PROJECT_ROOT / "sample-legacy" / "database" / "init.sql"


@dataclass(frozen=True)
class RepoConfig:
    name: str
    path: str
    type: str

    @property
    def abs_path(self) -> Path:
        return (PROJECT_ROOT / self.path).resolve()


@dataclass(frozen=True)
class DatabaseConfig:
    name: str
    type: str
    connection_env: str
    mode: str = "schema-only"


@dataclass(frozen=True)
class ApplicationConfig:
    name: str
    owner: str
    wave: int | None
    status: str
    repos: tuple[RepoConfig, ...]
    databases: tuple[DatabaseConfig, ...]


@dataclass(frozen=True)
class Portfolio:
    name: str
    defaults: dict
    applications: tuple[ApplicationConfig, ...]

    def application(self, name: str) -> ApplicationConfig | None:
        for app in self.applications:
            if app.name.lower() == name.lower():
                return app
        return None

    def repos(self) -> list[RepoConfig]:
        seen: dict[str, RepoConfig] = {}
        for app in self.applications:
            for repo in app.repos:
                seen.setdefault(repo.name, repo)
        return list(seen.values())

    def databases(self) -> list[DatabaseConfig]:
        """Unique databases; the same DB shared by two apps is returned once."""
        seen: dict[str, DatabaseConfig] = {}
        for app in self.applications:
            for db in app.databases:
                seen.setdefault(db.name, db)
        return list(seen.values())


def load_env(path: str | Path = ENV_PATH) -> None:
    """Load variables from ``.env`` if present (a missing file is a no-op)."""
    load_dotenv(path)


def get_connection_string(env_name: str) -> str | None:
    """Return the connection string held in ``env_name``, or ``None`` if unset."""
    return os.environ.get(env_name)


def load_portfolio(path: str | Path = PORTFOLIO_PATH) -> Portfolio:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}

    applications: list[ApplicationConfig] = []
    for app in data.get("applications", []) or []:
        migration = app.get("migration", {}) or {}
        repos = tuple(
            RepoConfig(name=r["name"], path=r["path"], type=r["type"])
            for r in app.get("repos", []) or []
        )
        databases = tuple(
            DatabaseConfig(
                name=d["name"],
                type=d["type"],
                connection_env=d["connection_env"],
                mode=d.get("mode", "schema-only"),
            )
            for d in app.get("databases", []) or []
        )
        applications.append(
            ApplicationConfig(
                name=app["name"],
                owner=app.get("owner", ""),
                wave=migration.get("wave"),
                status=migration.get("status", ""),
                repos=repos,
                databases=databases,
            )
        )

    return Portfolio(
        name=data.get("portfolio", ""),
        defaults=data.get("defaults", {}) or {},
        applications=tuple(applications),
    )


if __name__ == "__main__":  # pragma: no cover - manual inspection helper
    load_env()
    portfolio = load_portfolio()
    print(f"portfolio: {portfolio.name}")
    for application in portfolio.applications:
        print(
            f"  app {application.name} (wave {application.wave}, {application.status})"
        )
        for repo in application.repos:
            print(f"    repo {repo.name} [{repo.type}] -> {repo.path}")
        for database in application.databases:
            print(f"    db   {database.name} [{database.type}] env={database.connection_env}")
