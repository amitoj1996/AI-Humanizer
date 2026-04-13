from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from ..db.connection import get_session
from ..schemas.documents import (
    DocumentCreate,
    DocumentRead,
    DocumentRename,
    ProjectCreate,
    ProjectRead,
    RevisionCreate,
    RevisionRead,
)
from ..services import documents as svc

router = APIRouter(prefix="/api", tags=["documents"])


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------
@router.post("/projects", response_model=ProjectRead)
def create_project(req: ProjectCreate, session: Session = Depends(get_session)):
    return svc.create_project(session, req.name)


@router.get("/projects", response_model=list[ProjectRead])
def list_projects(session: Session = Depends(get_session)):
    return svc.list_projects(session)


@router.get("/projects/{project_id}", response_model=ProjectRead)
def get_project(project_id: str, session: Session = Depends(get_session)):
    p = svc.get_project(session, project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return p


@router.delete("/projects/{project_id}")
def delete_project(project_id: str, session: Session = Depends(get_session)):
    if not svc.delete_project(session, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------
@router.post("/documents", response_model=DocumentRead)
def create_document(req: DocumentCreate, session: Session = Depends(get_session)):
    if not svc.get_project(session, req.project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return svc.create_document(
        session,
        project_id=req.project_id,
        title=req.title,
        source_type=req.source_type,
        initial_content=req.initial_content,
        initial_format=req.initial_format,
    )


@router.get("/projects/{project_id}/documents", response_model=list[DocumentRead])
def list_documents(project_id: str, session: Session = Depends(get_session)):
    if not svc.get_project(session, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return svc.list_documents(session, project_id)


@router.get("/documents/{document_id}", response_model=DocumentRead)
def get_document(document_id: str, session: Session = Depends(get_session)):
    d = svc.get_document(session, document_id)
    if not d:
        raise HTTPException(status_code=404, detail="Document not found")
    return d


@router.patch("/documents/{document_id}", response_model=DocumentRead)
def rename_document(
    document_id: str,
    req: DocumentRename,
    session: Session = Depends(get_session),
):
    d = svc.rename_document(session, document_id, req.title)
    if not d:
        raise HTTPException(status_code=404, detail="Document not found")
    return d


@router.delete("/documents/{document_id}")
def delete_document(document_id: str, session: Session = Depends(get_session)):
    if not svc.delete_document(session, document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Revisions
# ---------------------------------------------------------------------------
@router.post(
    "/documents/{document_id}/revisions", response_model=RevisionRead
)
def save_revision(
    document_id: str,
    req: RevisionCreate,
    session: Session = Depends(get_session),
):
    rev = svc.save_revision(
        session,
        document_id,
        content=req.content,
        ai_score=req.ai_score,
        note=req.note,
        format=req.format,
    )
    if rev is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return rev


@router.get(
    "/documents/{document_id}/revisions", response_model=list[RevisionRead]
)
def list_revisions(document_id: str, session: Session = Depends(get_session)):
    if not svc.get_document(session, document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    return svc.list_revisions(session, document_id)


@router.get(
    "/documents/{document_id}/revisions/{revision_id}",
    response_model=RevisionRead,
)
def get_revision(
    document_id: str,
    revision_id: str,
    session: Session = Depends(get_session),
):
    rev = svc.get_revision(session, revision_id)
    if not rev or rev.document_id != document_id:
        raise HTTPException(status_code=404, detail="Revision not found")
    return rev


@router.post(
    "/documents/{document_id}/revisions/{revision_id}/restore",
    response_model=RevisionRead,
)
def restore_revision(
    document_id: str,
    revision_id: str,
    session: Session = Depends(get_session),
):
    rev = svc.restore_revision(session, document_id, revision_id)
    if rev is None:
        raise HTTPException(status_code=404, detail="Revision not found")
    return rev
