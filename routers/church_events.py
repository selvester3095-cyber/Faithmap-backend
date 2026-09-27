from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

router = APIRouter(prefix="/api/church", tags=["church-events"])

# ============ Models ============
class EventCreate(BaseModel):
    title: str
    description: str
    start_time: datetime
    end_time: datetime
    venue: str
    refreshments: bool = False
    notes: Optional[str] = None
    is_published: bool = False

class EventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    venue: Optional[str] = None
    refreshments: Optional[bool] = None
    notes: Optional[str] = None
    is_published: Optional[bool] = None

class EventResponse(BaseModel):
    id: int
    title: str
    description: str
    start_time: datetime
    end_time: datetime
    venue: str
    refreshments: bool
    notes: Optional[str]
    is_published: bool
    church_id: int
    interest_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class DeleteEventRequest(BaseModel):
    reason: str

# ============ Routes ============

@router.get("/events", response_model=List[EventResponse])
def list_events(
    church_id: int = Depends(get_current_church),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = None,
    sort_by: str = Query("date", enum=["date", "name"]),
    db: Session = Depends()
):
    """
    Get all events for a church with pagination and search
    """
    from main import Event

    query = db.query(Event).filter(Event.church_id == church_id)

    # Search by title
    if search:
        query = query.filter(Event.title.ilike(f"%{search}%"))

    # Sort
    if sort_by == "date":
        query = query.order_by(Event.start_time.desc())
    elif sort_by == "name":
        query = query.order_by(Event.title.asc())

    events = query.offset(skip).limit(limit).all()
    return events


@router.post("/events", response_model=EventResponse)
def create_event(
    request: EventCreate,
    church_id: int = Depends(get_current_church),
    db: Session = Depends()
):
    """
    Create a new event
    """
    from main import Event

    # Validate times
    if request.start_time >= request.end_time:
        raise HTTPException(status_code=400, detail="Start time must be before end time")

    # Validate description length
    if len(request.description) > 100:
        raise HTTPException(status_code=400, detail="Description must be 100 characters or less")

    event = Event(
        title=request.title,
        description=request.description,
        start_time=request.start_time,
        end_time=request.end_time,
        venue=request.venue,
        refreshments=request.refreshments,
        notes=request.notes,
        is_published=request.is_published,
        church_id=church_id
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    return event


@router.get("/events/{event_id}", response_model=EventResponse)
def get_event(
    event_id: int,
    church_id: int = Depends(get_current_church),
    db: Session = Depends()
):
    """
    Get a specific event
    """
    from main import Event

    event = db.query(Event).filter(
        Event.id == event_id,
        Event.church_id == church_id
    ).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return event


@router.put("/events/{event_id}", response_model=EventResponse)
def update_event(
    event_id: int,
    request: EventUpdate,
    church_id: int = Depends(get_current_church),
    db: Session = Depends()
):
    """
    Update an event (all fields editable)
    """
    from main import Event

    event = db.query(Event).filter(
        Event.id == event_id,
        Event.church_id == church_id
    ).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Validate description if provided
    if request.description and len(request.description) > 100:
        raise HTTPException(status_code=400, detail="Description must be 100 characters or less")

    # Validate times if both provided
    if request.start_time and request.end_time:
        if request.start_time >= request.end_time:
            raise HTTPException(status_code=400, detail="Start time must be before end time")

    # Update fields
    update_data = request.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(event, field, value)

    event.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(event)

    return event


@router.delete("/events/{event_id}")
def delete_event(
    event_id: int,
    request: DeleteEventRequest,
    church_id: int = Depends(get_current_church),
    db: Session = Depends()
):
    """
    Delete an event with required reason
    """
    from main import Event

    if not request.reason or len(request.reason.strip()) == 0:
        raise HTTPException(status_code=400, detail="Reason for deletion is required")

    event = db.query(Event).filter(
        Event.id == event_id,
        Event.church_id == church_id
    ).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Log deletion reason (optional - could store in audit table)
    # audit_log = AuditLog(church_id=church_id, event_id=event_id, action="delete", reason=request.reason)
    # db.add(audit_log)

    db.delete(event)
    db.commit()

    return {"message": "Event deleted successfully", "reason": request.reason}


@router.get("/events/{event_id}/interests")
def get_event_interests(
    event_id: int,
    church_id: int = Depends(get_current_church),
    db: Session = Depends()
):
    """
    Get list of people interested in an event
    Admin only - shows who clicked "I'm Interested"
    """
    from main import Event, Interest

    event = db.query(Event).filter(
        Event.id == event_id,
        Event.church_id == church_id
    ).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    interests = db.query(Interest).filter(Interest.event_id == event_id).all()

    return {
        "event_id": event_id,
        "event_title": event.title,
        "total_interests": len(interests),
        "interests": interests
    }


# ============ Helper Functions ============
def get_current_church(token: str):
    """Verify JWT token and return church_id"""
    from church_auth import get_current_church as auth_get_current_church
    return auth_get_current_church(token)
