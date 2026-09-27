from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

router = APIRouter(prefix="/api/church", tags=["church-settings"])

# ============ Models ============
class NotificationPreferences(BaseModel):
    email_on_interest: bool = True
    daily_digest: bool = True
    event_reminders: bool = False
    reminder_hours_before: int = 24

class NotificationResponse(BaseModel):
    email_on_interest: bool
    daily_digest: bool
    event_reminders: bool
    reminder_hours_before: int
    message: str

# ============ Routes ============

@router.get("/settings/notifications", response_model=NotificationResponse)
def get_notification_settings(
    church_id: int = Depends(get_current_church),
    db: Session = Depends()
):
    """
    Get notification preferences for a church
    """
    from main import Church, ChurchSettings

    church = db.query(Church).filter(Church.id == church_id).first()
    if not church:
        raise HTTPException(status_code=404, detail="Church not found")

    # Get or create settings
    settings = db.query(ChurchSettings).filter(
        ChurchSettings.church_id == church_id
    ).first()

    if not settings:
        # Create default settings
        settings = ChurchSettings(
            church_id=church_id,
            email_on_interest=True,
            daily_digest=True,
            event_reminders=False,
            reminder_hours_before=24
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)

    return NotificationResponse(
        email_on_interest=settings.email_on_interest,
        daily_digest=settings.daily_digest,
        event_reminders=settings.event_reminders,
        reminder_hours_before=settings.reminder_hours_before,
        message="Notification preferences retrieved"
    )


@router.put("/settings/notifications")
def update_notification_settings(
    preferences: NotificationPreferences,
    church_id: int = Depends(get_current_church),
    db: Session = Depends()
):
    """
    Update notification preferences
    """
    from main import Church, ChurchSettings

    church = db.query(Church).filter(Church.id == church_id).first()
    if not church:
        raise HTTPException(status_code=404, detail="Church not found")

    # Get or create settings
    settings = db.query(ChurchSettings).filter(
        ChurchSettings.church_id == church_id
    ).first()

    if not settings:
        settings = ChurchSettings(church_id=church_id)

    # Update preferences
    settings.email_on_interest = preferences.email_on_interest
    settings.daily_digest = preferences.daily_digest
    settings.event_reminders = preferences.event_reminders
    settings.reminder_hours_before = preferences.reminder_hours_before

    db.add(settings)
    db.commit()
    db.refresh(settings)

    return {
        "message": "Notification preferences updated successfully",
        "preferences": {
            "email_on_interest": settings.email_on_interest,
            "daily_digest": settings.daily_digest,
            "event_reminders": settings.event_reminders,
            "reminder_hours_before": settings.reminder_hours_before
        }
    }


@router.get("/settings/summary")
def get_all_settings(
    church_id: int = Depends(get_current_church),
    db: Session = Depends()
):
    """
    Get all settings for a church
    """
    from main import Church, ChurchSettings

    church = db.query(Church).filter(Church.id == church_id).first()
    if not church:
        raise HTTPException(status_code=404, detail="Church not found")

    settings = db.query(ChurchSettings).filter(
        ChurchSettings.church_id == church_id
    ).first()

    if not settings:
        settings = ChurchSettings(church_id=church_id)
        db.add(settings)
        db.commit()
        db.refresh(settings)

    return {
        "church_id": church_id,
        "church_name": church.name,
        "notifications": {
            "email_on_interest": settings.email_on_interest,
            "daily_digest": settings.daily_digest,
            "event_reminders": settings.event_reminders,
            "reminder_hours_before": settings.reminder_hours_before
        }
    }


# ============ Helper Functions ============
def get_current_church(token: str):
    """Verify JWT token and return church_id"""
    from church_auth import get_current_church as auth_get_current_church
    return auth_get_current_church(token)
