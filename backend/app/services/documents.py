"""Business logic for projects, documents, and revisions.

All functions take a `Session` so they're testable in isolation and callers
(API routes) control transaction boundaries.
"""
from __future__ import annotations

import hashlib
import time
from typing import Optional

from sqlmodel import Session, select

from ..db.models import (
    Document,
    Project,
    ProvenanceEvent,
    ProvenanceSession,
    Revision,
)


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------
def create_project(session: Session, name: str) -> Project:
    project = Project(name=name)
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def list_projects(session: Session) -> list[Project]:
    return list(
        session.exec(select(Project).order_by(Project.updated_at.desc())).all()
    )


def get_project(session: Session, project_id: str) -> Optional[Project]:
    return session.get(Project, project_id)


def delete_project(session: Session, project_id: str) -> bool:
    project = session.get(Project, project_id)
    if not project:
        return False

    # Cascade delete: documents + revisions + provenance for this project.
    # Explicit (rather than FK ON DELETE CASCADE) — clearer in code review
    # and avoids SQLAlchemy relationship config for a simple case.
    docs = session.exec(
        select(Document).where(Document.project_id == project_id)
    ).all()
    for doc in docs:
        _delete_document_cascade(session, doc.id)
        session.delete(doc)
    session.delete(project)
    session.commit()
    return True


def _delete_document_cascade(session: Session, document_id: str) -> None:
    """Remove all dependent rows for a document.  Caller commits."""
    # Clear Document.current_revision_id before deleting revisions so the FK
    # self-reference on the row being deleted doesn't throw.
    doc = session.get(Document, document_id)
    if doc:
        doc.current_revision_id = None
        session.add(doc)
        session.flush()

    # Provenance events → sessions → revisions
    session.exec(
        ProvenanceEvent.__table__.delete().where(
            ProvenanceEvent.document_id == document_id
        )
    )
    session.exec(
        ProvenanceSession.__table__.delete().where(
            ProvenanceSession.document_id == document_id
        )
    )
    session.exec(
        Revision.__table__.delete().where(Revision.document_id == document_id)
    )


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------
def create_document(
    session: Session,
    project_id: str,
    title: str,
    source_type: str = "blank",
    initial_content: str | None = None,
) -> Document:
    doc = Document(project_id=project_id, title=title, source_type=source_type)
    session.add(doc)
    session.flush()  # assign doc.id before we create the initial revision

    if initial_content is not None:
        rev = _create_revision_inner(session, doc.id, initial_content)
        doc.current_revision_id = rev.id

    session.commit()
    session.refresh(doc)
    return doc


def list_documents(session: Session, project_id: str) -> list[Document]:
    return list(
        session.exec(
            select(Document)
            .where(Document.project_id == project_id)
            .order_by(Document.updated_at.desc())
        ).all()
    )


def get_document(session: Session, document_id: str) -> Optional[Document]:
    return session.get(Document, document_id)


def rename_document(
    session: Session, document_id: str, title: str
) -> Optional[Document]:
    doc = session.get(Document, document_id)
    if not doc:
        return None
    doc.title = title
    doc.updated_at = int(time.time() * 1000)
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc


def delete_document(session: Session, document_id: str) -> bool:
    doc = session.get(Document, document_id)
    if not doc:
        return False
    _delete_document_cascade(session, document_id)
    session.delete(doc)
    session.commit()
    return True


# ---------------------------------------------------------------------------
# Revisions
# ---------------------------------------------------------------------------
def _create_revision_inner(
    session: Session,
    document_id: str,
    content: str,
    ai_score: float | None = None,
    note: str | None = None,
) -> Revision:
    """Insert a revision without committing.  Caller is responsible."""
    parent = _current_head(session, document_id)
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    rev = Revision(
        document_id=document_id,
        parent_id=parent.id if parent else None,
        content=content,
        content_hash=content_hash,
        ai_score=ai_score,
        note=note,
    )
    session.add(rev)
    session.flush()
    return rev


def save_revision(
    session: Session,
    document_id: str,
    content: str,
    ai_score: float | None = None,
    note: str | None = None,
) -> Optional[Revision]:
    """Append a new revision and update the document HEAD pointer.

    If the content is identical to the current HEAD, no-op and return the
    existing head (dedup).
    """
    doc = session.get(Document, document_id)
    if not doc:
        return None

    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    head = _current_head(session, document_id)
    if head and head.content_hash == content_hash:
        return head  # no change, don't create a duplicate

    rev = _create_revision_inner(
        session, document_id, content, ai_score=ai_score, note=note
    )
    doc.current_revision_id = rev.id
    doc.updated_at = int(time.time() * 1000)
    session.add(doc)
    session.commit()
    session.refresh(rev)
    return rev


def list_revisions(session: Session, document_id: str) -> list[Revision]:
    return list(
        session.exec(
            select(Revision)
            .where(Revision.document_id == document_id)
            .order_by(Revision.created_at.desc())
        ).all()
    )


def get_revision(session: Session, revision_id: str) -> Optional[Revision]:
    return session.get(Revision, revision_id)


def restore_revision(
    session: Session, document_id: str, revision_id: str
) -> Optional[Revision]:
    """Make an old revision the current HEAD by appending a new revision
    with the same content and a restore note."""
    target = session.get(Revision, revision_id)
    if not target or target.document_id != document_id:
        return None
    return save_revision(
        session,
        document_id,
        target.content,
        ai_score=target.ai_score,
        note=f"Restored from {revision_id[:8]}",
    )


def _current_head(session: Session, document_id: str) -> Optional[Revision]:
    doc = session.get(Document, document_id)
    if not doc or not doc.current_revision_id:
        return None
    return session.get(Revision, doc.current_revision_id)
