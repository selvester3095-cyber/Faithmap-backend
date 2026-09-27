from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional

router = APIRouter(prefix="/api/church", tags=["church-profile"])

# ============ Models ============
class ChurchProfileResponse(BaseModel):
    id: int
    name: str
    denomination: str
    area: str
    city: str
    phone: str
    email: str
    website: Optional[str]
    address: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class EditRequestMessage(BaseModel):
    message: str

class EditRequestResponse(BaseModel):
    message: str
    admin_notified: bool
    request_id: int

# ============ Routes ============

@router.get("/profile", response_model=ChurchProfileResponse)
def get_church_profile(
    church_id: int = Depends(get_current_church),
    db: Session = Depends()
):
    """
    Get church profile (Read-only for church users)
    Shows: Name, Denomination, Area, City, Phone, Email, Website
    """
    from main import Church

    church = db.query(Church).filter(Church.id == church_id).first()

    if not church:
        raise HTTPException(status_code=404, detail="Church not found")

    return church


@router.post("/profile/request-edit")
def request_profile_edit(
    request: EditRequestMessage,
    church_id: int = Depends(get_current_church),
    db: Session = Depends()
):
    """
    Send edit request to admin
    Church can request to edit their profile details
    """
    from main import Church, EditRequest

    church = db.query(Church).filter(Church.id == church_id).first()
    if not church:
        raise HTTPException(status_code=404, detail="Church not found")

    if not request.message or len(request.message.strip()) == 0:
        raise HTTPException(status_code=400, detail="Message is required")

    # Create edit request
    edit_request = EditRequest(
        church_id=church_id,
        message=request.message,
        status="pending",
        created_at=datetime.utcnow()
    )

    db.add(edit_request)
    db.commit()
    db.refresh(edit_request)

    return EditRequestResponse(
        message="Edit request sent to admin successfully",
        admin_notified=True,
        request_id=edit_request.id
    )


@router.get("/profile/edit-requests")
def get_edit_requests(
    church_id: int = Depends(get_current_church),
    db: Session = Depends()
):
    """
    Get all edit requests for a church
    """
    from main import EditRequest

    requests = db.query(EditRequest).filter(
        EditRequest.church_id == church_id
    ).order_by(EditRequest.created_at.desc()).all()

    return {
        "church_id": church_id,
        "total_requests": len(requests),
        "requests": requests
    }


# ============ Admin-Only Routes (for future) ============

@router.put("/admin/profile/{church_id}")
def admin_update_church_profile(
    church_id: int,
    updates: dict,
    admin_id: int = Depends(get_current_admin),
    db: Session = Depends()
):
    """
    Admin can update church profile
    """
    from main import Church

    church = db.query(Church).filter(Church.id == church_id).first()
    if not church:
        raise HTTPException(status_code=404, detail="Church not found")

    # Allowed fields for admin to update
    allowed_fields = ['name', 'denomination', 'area', 'city', 'phone', 'email', 'website', 'address', 'latitude', 'longitude']

    for field, value in updates.items():
        if field in allowed_fields:
            setattr(church, field, value)

    church.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(church)

    return {
        "message": "Church profile updated successfully",
        "church": church
    }


@router.put("/admin/edit-requests/{request_id}")
def approve_edit_request(
    request_id: int,
    action: str,  # 'approve' or 'reject'
    response_message: Optional[str] = None,
    admin_id: int = Depends(get_current_admin),
    db: Session = Depends()
):
    """
    Admin approves or rejects edit requests
    """
    from main import EditRequest

    if action not in ['approve', 'reject']:
        raise HTTPException(status_code=400, detail="Action must be 'approve' or 'reject'")

    edit_request = db.query(EditRequest).filter(EditRequest.id == request_id).first()
    if not edit_request:
        raise HTTPException(status_code=404, detail="Edit request not found")

    edit_request.status = action
    edit_request.response_message = response_message
    edit_request.processed_at = datetime.utcnow()

    db.commit()

    return {
        "message": f"Edit request {action}ed successfully",
        "request_id": request_id,
        "status": action
    }


# ============ Helper Functions ============
def get_current_church(token: str):
    """Verify JWT token and return church_id"""
    from church_auth import get_current_church as auth_get_current_church
    return auth_get_current_church(token)

def get_current_admin(token: str):
    """Verify JWT token and return admin_id"""
    # TODO: Implement admin auth
    pass
