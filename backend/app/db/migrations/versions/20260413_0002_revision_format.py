"""Add Revision.format column ('text' or 'prosemirror').

Existing revisions are plain text — backfill 'text' for them.

Revision ID: 0002_revision_format
Revises: 0001_initial
Create Date: 2026-04-13 00:00:00 UTC
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0002_revision_format"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("revisions", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "format",
                sqlmodel.sql.sqltypes.AutoString(),
                nullable=False,
                server_default="text",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("revisions", schema=None) as batch_op:
        batch_op.drop_column("format")
