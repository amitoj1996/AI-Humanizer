"""Initial schema — projects, documents, revisions, provenance.

Baseline migration.  Mirrors SQLModel metadata exactly as of this commit.
Future schema changes add new migrations; user DBs are upgraded via
`alembic upgrade head` on launch.

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-13 00:00:00 UTC
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projects_created_at", "projects", ["created_at"])
    op.create_index("ix_projects_updated_at", "projects", ["updated_at"])

    op.create_table(
        "documents",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "project_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "source_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column(
            "current_revision_id",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=True,
        ),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documents_project_id", "documents", ["project_id"])
    op.create_index(
        "ix_documents_current_revision_id",
        "documents",
        ["current_revision_id"],
    )
    op.create_index("ix_documents_updated_at", "documents", ["updated_at"])

    op.create_table(
        "revisions",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "document_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column(
            "parent_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column("content", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "content_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("ai_score", sa.Float(), nullable=True),
        sa.Column("note", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["parent_id"], ["revisions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_revisions_document_id", "revisions", ["document_id"])
    op.create_index("ix_revisions_content_hash", "revisions", ["content_hash"])
    op.create_index("ix_revisions_created_at", "revisions", ["created_at"])

    op.create_table(
        "provenance_sessions",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "document_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("started_at", sa.Integer(), nullable=False),
        sa.Column("ended_at", sa.Integer(), nullable=True),
        sa.Column(
            "genesis_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column(
            "final_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_provenance_sessions_document_id",
        "provenance_sessions",
        ["document_id"],
    )

    op.create_table(
        "provenance_events",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "session_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column(
            "document_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column(
            "event_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("timestamp", sa.Integer(), nullable=False),
        sa.Column("payload", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "prev_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column(
            "self_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.ForeignKeyConstraint(["session_id"], ["provenance_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_provenance_events_session_id",
        "provenance_events",
        ["session_id"],
    )
    op.create_index(
        "ix_provenance_events_document_id",
        "provenance_events",
        ["document_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_provenance_events_document_id", "provenance_events")
    op.drop_index("ix_provenance_events_session_id", "provenance_events")
    op.drop_table("provenance_events")
    op.drop_index(
        "ix_provenance_sessions_document_id", "provenance_sessions"
    )
    op.drop_table("provenance_sessions")
    op.drop_index("ix_revisions_created_at", "revisions")
    op.drop_index("ix_revisions_content_hash", "revisions")
    op.drop_index("ix_revisions_document_id", "revisions")
    op.drop_table("revisions")
    op.drop_index("ix_documents_updated_at", "documents")
    op.drop_index("ix_documents_current_revision_id", "documents")
    op.drop_index("ix_documents_project_id", "documents")
    op.drop_table("documents")
    op.drop_index("ix_projects_updated_at", "projects")
    op.drop_index("ix_projects_created_at", "projects")
    op.drop_table("projects")
