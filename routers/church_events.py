from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
from database import get_db
from models import Event, Church

router = APIRouter(prefix="/api/church", tags=["church-events"])

# ============== Models ==============
class EventCreate(BaseModel):
    title: str
    description: str | None = None
    start_time: datetime
    end_time: datetime
    location: str | None = None
    category: str | None = None

class EventUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    location: str | None = None
    category: str | None = None
    is_published: bool | None = None

class EventResponse(BaseModel):
    id: int
    church_id: int
    title: str
    description: str | None
    start_time: datetime
    end_time: datetime
    location: str | None
    category: str | None
    is_published: bool
    interested_count: int
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True

# ============== Routes ==============
@router.post("/events", response_model=dict)
def create_event(church_id: int, request: EventCreate, db: Session = Depends(get_db)):
    """Create a new event"""
    # Validate description length
    if request.description and len(request.description) > 100:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Description must be 100 characters or less")
    
    # Validate times
    if request.start_time >= request.end_time:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Start time must be before end time")
    
    # Create event
    new_event = Event(
        church_id=church_id,
        title=request.title,
        description=request.description,
        start_time=request.start_time,
        end_time=request.end_time,
        location=request.location,
        category=request.category,
        is_published=False
    )
    
    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    
    return {
        "message": "Event created successfully",
        "event_id": new_event.id
    }

@router.get("/events/{event_id}", response_model=EventResponse)
def get_event(event_id: int, db: Session = Depends(get_db)):
    """Get event by ID"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    
    return event

@router.get("/events", response_model=dict)
def list_events(
    church_id: int,
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    sort_by: str = "created_at",
    db: Session = Depends(get_db)
):
    """List church events with pagination and search"""
    query = db.query(Event).filter(Event.church_id == church_id)
    
    # Search by title
    if search:
        query = query.filter(Event.title.ilike(f"%{search}%"))
    
    # Sorting
    if sort_by == "start_time":
        query = query.order_by(Event.start_time.desc())
    else:
        query = query.order_by(Event.created_at.desc())
    
    total = query.count()
    events = query.offset(skip).limit(limit).all()
    
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "events": events
    }

@router.put("/events/{event_id}", response_model=dict)
def update_event(event_id: int, request: EventUpdate, db: Session = Depends(get_db)):
    """Update event"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    
    # Validate description length if provided
    if request.description and len(request.description) > 100:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Description must be 100 characters or less")
    
    # Validate times if provided
    start_time = request.start_time or event.start_time
    end_time = request.end_time or event.end_time
    if start_time >= end_time:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Start time must be before end time")
    
    # Update fields
    if request.title:
        event.title = request.title
    if request.description is not None:
        event.description = request.description
    if request.start_time:
        event.start_time = request.start_time
    if request.end_time:
        event.end_time = request.end_time
    if request.location is not None:
        event.location = request.location
    if request.category is not None:
        event.category = request.category
    if request.is_published is not None:
        event.is_published = request.is_published
    
    event.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(event)
    
    return {"message": "Event updated successfully"}

@router.delete("/events/{event_id}", response_model=dict)
def delete_event(event_id: int, db: Session = Depends(get_db)):
    """Delete event"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    
    db.delete(event)
    db.commit()
    
    return {"message": "Event deleted successfully"}

@router.post("/events/{event_id}/interested", response_model=dict)
def mark_interested(event_id: int, user_id: int, db: Session = Depends(get_db)):
    """Mark event as interested"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    
    event.interested_count += 1
    db.commit()
    
    return {"message": "Marked as interested"}

@router.post("/events/{event_id}/publish", response_model=dict)
def publish_event(event_id: int, db: Session = Depends(get_db)):
    """Publish event"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    
    event.is_published = True
    db.commit()
    
    return {"message": "Event published successfully"}
