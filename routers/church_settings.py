from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import SessionLocal
from models import ChurchSettings

router = APIRouter(prefix="/api/church", tags=["church-settings"])

# ============== Models ==============
class NotificationPreferences(BaseModel):
    email_on_interest: bool = True
    daily_digest: bool = False
    event_reminders: bool = True
    reminder_hours_before: int = 24

class NotificationPreferencesResponse(BaseModel):
    id: int
    church_id: int
    email_on_interest: bool
    daily_digest: bool
    event_reminders: bool
    reminder_hours_before: int

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
@router.get("/settings/{church_id}/notifications", response_model=NotificationPreferencesResponse)
def get_notification_settings(church_id: int, db: Session = None):
    """Get notification preferences for church"""
    if db is None:
        db = SessionLocal()
    
    settings = db.query(ChurchSettings).filter(ChurchSettings.church_id == church_id).first()
    
    if not settings:
        # Return default settings if not exists
        return {
            "id": 0,
            "church_id": church_id,
            "email_on_interest": True,
            "daily_digest": False,
            "event_reminders": True,
            "reminder_hours_before": 24
        }
    
    return settings

@router.put("/settings/{church_id}/notifications", response_model=dict)
def update_notification_settings(church_id: int, request: NotificationPreferences, db: Session = None):
    """Update notification preferences"""
    if db is None:
        db = SessionLocal()
    
    # Validate reminder hours
    if request.reminder_hours_before < 1 or request.reminder_hours_before > 720:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reminder hours must be between 1 and 720"
        )
    
    # Get or create settings
    settings = db.query(ChurchSettings).filter(ChurchSettings.church_id == church_id).first()
    
    if not settings:
        settings = ChurchSettings(
            church_id=church_id,
            email_on_interest=request.email_on_interest,
            daily_digest=request.daily_digest,
            event_reminders=request.event_reminders,
            reminder_hours_before=request.reminder_hours_before
        )
        db.add(settings)
    else:
        settings.email_on_interest = request.email_on_interest
        settings.daily_digest = request.daily_digest
        settings.event_reminders = request.event_reminders
        settings.reminder_hours_before = request.reminder_hours_before
    
    db.commit()
    db.refresh(settings)
    
    return {
        "message": "Notification settings updated successfully",
        "settings": {
            "email_on_interest": settings.email_on_interest,
            "daily_digest": settings.daily_digest,
            "event_reminders": settings.event_reminders,
            "reminder_hours_before": settings.reminder_hours_before
        }
    }

@router.post("/settings/{church_id}/notifications/reset", response_model=dict)
def reset_notification_settings(church_id: int, db: Session = None):
    """Reset notification settings to defaults"""
    if db is None:
        db = SessionLocal()
    
    settings = db.query(ChurchSettings).filter(ChurchSettings.church_id == church_id).first()
    
    if settings:
        settings.email_on_interest = True
        settings.daily_digest = False
        settings.event_reminders = True
        settings.reminder_hours_before = 24
        db.commit()
    
    return {
        "message": "Notification settings reset to defaults",
        "settings": {
            "email_on_interest": True,
            "daily_digest": False,
            "event_reminders": True,
            "reminder_hours_before": 24
        }
    }

@router.get("/settings/{church_id}/all", response_model=dict)
def get_all_settings(church_id: int, db: Session = None):
    """Get all church settings"""
    if db is None:
        db = SessionLocal()
    
    settings = db.query(ChurchSettings).filter(ChurchSettings.church_id == church_id).first()
    
    if not settings:
        settings = ChurchSettings(
            church_id=church_id,
            email_on_interest=True,
            daily_digest=False,
            event_reminders=True,
            reminder_hours_before=24
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)
    
    return {
        "church_id": settings.church_id,
        "notifications": {
            "email_on_interest": settings.email_on_interest,
            "daily_digest": settings.daily_digest,
            "event_reminders": settings.event_reminders,
            "reminder_hours_before": settings.reminder_hours_before
        }
    }
