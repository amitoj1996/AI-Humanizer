"""SQLite connection + session factory.

Uses SQLModel's metadata (which is SQLAlchemy's underneath).  Configured with
WAL mode for concurrent reads, foreign keys on, and `synchronous=NORMAL`
which is safe for a single-user desktop app and a measurable speed win
over `FULL`.

Schema is managed by Alembic (app/db/migrations/).  `init_db()` calls
`alembic upgrade head` so new installs and upgrades both converge to the
latest schema — the baseline migration creates all tables for a fresh DB.
"""
from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

from ..config import APP_DATA_DIR, DB_PATH

_engine: Engine | None = None


def _current_db_path() -> Path:
    """Resolve the DB path fresh from env each call.

    `DB_PATH` from config is evaluated at import time, so tests that
    monkeypatch `AI_HUMANIZER_DB_PATH` wouldn't otherwise take effect.
    """
    override = os.environ.get("AI_HUMANIZER_DB_PATH")
    if override:
        return Path(override)
    return DB_PATH


def _current_data_dir() -> Path:
    override = os.environ.get("AI_HUMANIZER_DATA_DIR")
    if override:
        return Path(override)
    return APP_DATA_DIR

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_ALEMBIC_CFG = _REPO_ROOT / "alembic.ini"


def _db_url(path: Path | None = None) -> str:
    p = Path(path) if path else _current_db_path()
    return f"sqlite:///{p}"


def _on_connect(dbapi_conn, _record) -> None:
    """Apply SQLite pragmas to every new connection."""
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode = WAL")
    cur.execute("PRAGMA foreign_keys = ON")
    cur.execute("PRAGMA synchronous = NORMAL")
    cur.close()


def init_db(url: str | None = None) -> Engine:
    """Run migrations and return the engine.  Idempotent — safe to call many times."""
    global _engine

    if url is None:
        _current_data_dir().mkdir(parents=True, exist_ok=True)
        url = _db_url()

    engine = create_engine(url, echo=False, connect_args={"check_same_thread": False})
    event.listen(engine, "connect", _on_connect)

    # Ensure models are imported so their metadata is available to Alembic.
    from . import models  # noqa: F401

    # Run migrations up to head.  For a fresh DB this creates all tables;
    # for an existing DB it applies any pending migrations.  Works in-process
    # so we don't need an external alembic binary at runtime.
    alembic_cfg = Config(str(_ALEMBIC_CFG))
    alembic_cfg.set_main_option("script_location", str(_REPO_ROOT / "app" / "db" / "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(alembic_cfg, "head")

    _engine = engine
    return engine


def get_engine() -> Engine:
    if _engine is None:
        return init_db()
    return _engine


def get_session() -> Iterator[Session]:
    """FastAPI dependency.  Use via `Depends(get_session)` in routes."""
    engine = get_engine()
    with Session(engine) as session:
        yield session


def reset_engine() -> None:
    """Test helper — drop the cached engine so the next call re-initialises."""
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = None
