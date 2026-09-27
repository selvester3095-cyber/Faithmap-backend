from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
from database import SessionLocal
from models import Church, EditRequest

router = APIRouter(prefix="/api/church", tags=["church-profile"])

# ============== Models ==============
class EditRequestCreate(BaseModel):
    field_name: str
    new_value: str
    reason: str | None = None

class EditRequestResponse(BaseModel):
    id: int
    church_id: int
    field_name: str
    new_value: str
    reason: str | None
    status: str  # pending, approved, rejected
    requested_at: datetime
    responded_at: datetime | None

    class Config:
        from_attributes = True

class ChurchProfileResponse(BaseModel):
    id: int
    church_name: str
    email: str
    phone: str | None
    location: str | None
    description: str | None
    image_url: str | None
    created_at: datetime

    class Config:
        from_attributes = True

# ============== Helper Functions ==============
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============== Routes ==============
@router.get("/profile/{church_id}", response_model=ChurchProfileResponse)
def get_church_profile(church_id: int, db: Session = None):
    """Get church profile (read-only)"""
    if db is None:
        db = SessionLocal()
    
    church = db.query(Church).filter(Church.id == church_id).first()
    if not church:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Church not found")
    
    return church

@router.post("/profile/{church_id}/request-edit", response_model=dict)
def request_edit(church_id: int, request: EditRequestCreate, db: Session = None):
    """Request edit to church profile"""
    if db is None:
        db = SessionLocal()
    
    # Verify church exists
    church = db.query(Church).filter(Church.id == church_id).first()
    if not church:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Church not found")
    
    # Check if pending request already exists for this field
    existing = db.query(EditRequest).filter(
        EditRequest.church_id == church_id,
        EditRequest.field_name == request.field_name,
        EditRequest.status == "pending"
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pending request already exists for this field"
        )
    
    # Create edit request
    new_request = EditRequest(
        church_id=church_id,
        field_name=request.field_name,
        new_value=request.new_value,
        reason=request.reason,
        status="pending",
        requested_at=datetime.utcnow()
    )
    
    db.add(new_request)
    db.commit()
    db.refresh(new_request)
    
    return {
        "message": "Edit request submitted",
        "request_id": new_request.id
    }

@router.get("/profile/{church_id}/edit-requests", response_model=dict)
def get_edit_requests(church_id: int, status_filter: str | None = None, db: Session = None):
    """Get edit requests for church"""
    if db is None:
        db = SessionLocal()
    
    # Verify church exists
    church = db.query(Church).filter(Church.id == church_id).first()
    if not church:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Church not found")
    
    query = db.query(EditRequest).filter(EditRequest.church_id == church_id)
    
    if status_filter:
        query = query.filter(EditRequest.status == status_filter)
    
    requests = query.all()
    
    return {
        "total": len(requests),
        "requests": requests
    }

@router.get("/profile/{church_id}/edit-requests/{request_id}", response_model=EditRequestResponse)
def get_edit_request(church_id: int, request_id: int, db: Session = None):
    """Get specific edit request"""
    if db is None:
        db = SessionLocal()
    
    edit_request = db.query(EditRequest).filter(
        EditRequest.id == request_id,
        EditRequest.church_id == church_id
    ).first()
    
    if not edit_request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Edit request not found")
    
    return edit_request

@router.post("/profile/{church_id}/edit-requests/{request_id}/approve", response_model=dict)
def approve_edit_request(church_id: int, request_id: int, db: Session = None):
    """Approve edit request (admin only)"""
    if db is None:
        db = SessionLocal()
    
    edit_request = db.query(EditRequest).filter(
        EditRequest.id == request_id,
        EditRequest.church_id == church_id
    ).first()
    
    if not edit_request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Edit request not found")
    
    if edit_request.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve request with status: {edit_request.status}"
        )
    
    # Update church profile field
    church = db.query(Church).filter(Church.id == church_id).first()
    if hasattr(church, edit_request.field_name):
        setattr(church, edit_request.field_name, edit_request.new_value)
    
    # Update request status
    edit_request.status = "approved"
    edit_request.responded_at = datetime.utcnow()
    
    db.commit()
    
    return {
        "message": "Edit request approved",
        "field": edit_request.field_name
    }

@router.post("/profile/{church_id}/edit-requests/{request_id}/reject", response_model=dict)
def reject_edit_request(church_id: int, request_id: int, reason: str | None = None, db: Session = None):
    """Reject edit request (admin only)"""
    if db is None:
        db = SessionLocal()
    
    edit_request = db.query(EditRequest).filter(
        EditRequest.id == request_id,
        EditRequest.church_id == church_id
    ).first()
    
    if not edit_request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Edit request not found")
    
    if edit_request.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject request with status: {edit_request.status}"
        )
    
    # Update request status
    edit_request.status = "rejected"
    edit_request.responded_at = datetime.utcnow()
    
    db.commit()
    
    return {
        "message": "Edit request rejected",
        "field": edit_request.field_name
    }
