"""SQLite connection + session factory.

Uses SQLModel's metadata (which is SQLAlchemy's underneath).  Configured with
WAL mode for concurrent reads, foreign keys on, and `synchronous=NORMAL`
which is safe for a single-user desktop app and a measurable speed win
over `FULL`.
"""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from ..config import APP_DATA_DIR, DB_PATH

_engine: Engine | None = None


def _db_url(path: Path | None = None) -> str:
    p = Path(path) if path else DB_PATH
    return f"sqlite:///{p}"


def _on_connect(dbapi_conn, _record) -> None:
    """Apply SQLite pragmas to every new connection."""
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode = WAL")
    cur.execute("PRAGMA foreign_keys = ON")
    cur.execute("PRAGMA synchronous = NORMAL")
    cur.close()


def init_db(url: str | None = None) -> Engine:
    """Create tables and return the engine.  Idempotent — safe to call many times."""
    global _engine

    if url is None:
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        url = _db_url()

    engine = create_engine(url, echo=False, connect_args={"check_same_thread": False})
    event.listen(engine, "connect", _on_connect)

    # Import models so metadata is populated before create_all
    from . import models  # noqa: F401

    SQLModel.metadata.create_all(engine)

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
