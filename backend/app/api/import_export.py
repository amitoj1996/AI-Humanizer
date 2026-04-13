"""File import and export endpoints.

Import: POST /api/documents/import (multipart) → creates a document with the
parsed text as its initial revision.

Export: GET /api/documents/{id}/export?format=docx|md|txt returns the current
revision as a file download.  Also: GET /api/documents/{id}/provenance/export
returns the writing-process report.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlmodel import Session

from ..db.connection import get_session
from ..export import docx as docx_export
from ..export import report as report_export
from ..export import text as text_export
from ..ingest.dispatcher import UnsupportedFileError, parse_file
from ..provenance import service as provenance_service
from ..schemas.import_export import ImportResult
from ..services import documents as doc_service

router = APIRouter(prefix="/api", tags=["import-export"])

def _content_disposition(filename: str) -> str:
    """RFC 6266 header — safe ASCII fallback + UTF-8 extended form.

    HTTP header values must be latin-1 encodable, so we strip unicode from
    the plain `filename=` parameter and include a full UTF-8 version via
    RFC 5987's `filename*=UTF-8''`.
    """
    ascii_fallback = filename.encode("ascii", errors="replace").decode("ascii")
    return (
        f'attachment; filename="{ascii_fallback}"; '
        f"filename*=UTF-8''{quote(filename)}"
    )


EXPORT_FORMATS = {
    "md": ("text/markdown; charset=utf-8", ".md"),
    "txt": ("text/plain; charset=utf-8", ".txt"),
    "docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".docx",
    ),
}


@router.post("/documents/import", response_model=ImportResult)
async def import_document(
    project_id: str = Form(...),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    if not doc_service.get_project(session, project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    try:
        parsed = parse_file(file.filename or "", content)
    except UnsupportedFileError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001 — surface library-specific failures
        raise HTTPException(
            status_code=400, detail=f"Failed to parse file: {e}"
        ) from e

    title = Path(file.filename or "Imported document").stem or "Imported document"

    doc = doc_service.create_document(
        session,
        project_id=project_id,
        title=title,
        source_type=parsed["source_type"],
        initial_content=parsed["text"],
    )

    return ImportResult(
        document_id=doc.id,
        title=doc.title,
        source_type=parsed["source_type"],
        char_count=len(parsed["text"]),
        warnings=parsed["warnings"],
    )


@router.get("/documents/{document_id}/export")
def export_document(
    document_id: str,
    format: str = "md",
    session: Session = Depends(get_session),
):
    if format not in EXPORT_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown format {format!r}. Supported: {sorted(EXPORT_FORMATS)}",
        )

    doc = doc_service.get_document(session, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if not doc.current_revision_id:
        raise HTTPException(status_code=400, detail="Document has no content yet")

    revision = doc_service.get_revision(session, doc.current_revision_id)
    if revision is None:
        raise HTTPException(status_code=500, detail="Current revision missing")

    content = revision.content
    mime, ext = EXPORT_FORMATS[format]

    if format == "md":
        body = text_export.export_md(content)
    elif format == "txt":
        body = text_export.export_txt(content)
    else:
        body = docx_export.export(content, title=doc.title)

    safe_title = doc.title.replace("/", "_").replace("\\", "_")
    return Response(
        content=body,
        media_type=mime,
        headers={
            "Content-Disposition": _content_disposition(f"{safe_title}{ext}"),
        },
    )


@router.get("/documents/{document_id}/provenance/export")
def export_provenance(
    document_id: str,
    format: str = "md",
    session: Session = Depends(get_session),
):
    if format not in {"md", "docx"}:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown format {format!r}. Supported: md, docx",
        )

    report = provenance_service.build_report(session, document_id)
    if not report:
        raise HTTPException(status_code=404, detail="Document not found")

    if format == "md":
        body = report_export.report_to_markdown(report).encode("utf-8")
        mime = "text/markdown; charset=utf-8"
        ext = ".md"
    else:
        body = report_export.report_to_docx(report)
        mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ext = ".docx"

    safe_title = report["document_title"].replace("/", "_").replace("\\", "_")
    filename = f"{safe_title} — process report{ext}"
    return Response(
        content=body,
        media_type=mime,
        headers={
            "Content-Disposition": _content_disposition(filename),
        },
    )
