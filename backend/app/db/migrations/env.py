"""Alembic environment — drives migrations against our SQLite DB.

Imports the app config for the DB path so dev/test/prod all migrate the
same file their runtime uses.  SQLModel metadata is the autogeneration
source.
"""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

# Pull in all model modules so SQLModel.metadata is fully populated.
from app.db import connection  # noqa: F401
from app.db import models  # noqa: F401

# Alembic config object
cfg = context.config

if cfg.config_file_name:
    fileConfig(cfg.config_file_name)

# Respect env-var overrides at migration-run time (so tests using
# AI_HUMANIZER_DB_PATH migrate their tmp DBs, not the default app path).
# If the caller already set sqlalchemy.url (e.g. init_db), keep it.
if cfg.get_main_option("sqlalchemy.url") in (None, "driver://user:pass@localhost/dbname"):
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{connection._current_db_path()}")

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    url = cfg.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite needs batch-mode for ALTER
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        cfg.get_section(cfg.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
