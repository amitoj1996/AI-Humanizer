import json

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from ..db.connection import get_session
from ..provenance import service
from ..schemas.provenance import (
    EventRead,
    EventsAppendRequest,
    EventsAppendResponse,
    SessionRead,
    SessionStartRequest,
    VerificationResponse,
)

router = APIRouter(prefix="/api", tags=["provenance"])


@router.post("/sessions", response_model=SessionRead)
def start_session(
    req: SessionStartRequest, session: Session = Depends(get_session)
):
    ps = service.start_session(session, req.document_id)
    if ps is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return ps


@router.get("/documents/{document_id}/active-session", response_model=SessionRead | None)
def get_active_session(document_id: str, session: Session = Depends(get_session)):
    ps = service.get_active_session_for_document(session, document_id)
    return ps


@router.post("/sessions/{session_id}/events", response_model=EventsAppendResponse)
def append_events(
    session_id: str,
    req: EventsAppendRequest,
    session: Session = Depends(get_session),
):
    events = [
        {
            "event_type": e.event_type,
            "timestamp": e.timestamp,
            "payload": e.payload,
        }
        for e in req.events
    ]
    appended, error = service.append_events(session, session_id, events)
    if error and appended == 0:
        raise HTTPException(status_code=400, detail=error)
    return EventsAppendResponse(appended=appended, error=error)


@router.post("/sessions/{session_id}/seal", response_model=SessionRead)
def seal_session(session_id: str, session: Session = Depends(get_session)):
    ps = service.seal_session(session, session_id)
    if ps is None:
        raise HTTPException(status_code=400, detail="Session not found or already sealed")
    return ps


@router.get("/sessions/{session_id}/verify", response_model=VerificationResponse)
def verify(session_id: str, session: Session = Depends(get_session)):
    result = service.verify_session_chain(session, session_id)
    return VerificationResponse(
        valid=result.valid,
        total_events=result.total_events,
        broken_at=result.broken_at,
        reason=result.reason,
    )


@router.get("/sessions/{session_id}/events", response_model=list[EventRead])
def list_events(session_id: str, session: Session = Depends(get_session)):
    events = service.list_events(session, session_id)
    return [
        EventRead(
            id=e.id,
            session_id=e.session_id,
            sequence=e.sequence,
            event_type=e.event_type,
            timestamp=e.timestamp,
            payload=json.loads(e.payload),
            prev_hash=e.prev_hash,
            self_hash=e.self_hash,
        )
        for e in events
    ]


@router.get("/documents/{document_id}/provenance/report")
def provenance_report(
    document_id: str, session: Session = Depends(get_session)
):
    report = service.build_report(session, document_id)
    if not report:
        raise HTTPException(status_code=404, detail="Document not found")
    return report
