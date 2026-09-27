from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

# ============== Church Model ==============
class Church(Base):
    __tablename__ = "churches"
    
    id = Column(Integer, primary_key=True, index=True)
    church_name = Column(String(255), nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    location = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    image_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)
    
    # Relationships
    events = relationship("Event", back_populates="church", cascade="all, delete-orphan")
    settings = relationship("ChurchSettings", back_populates="church", cascade="all, delete-orphan")
    edit_requests = relationship("EditRequest", back_populates="church", cascade="all, delete-orphan")

# ============== Event Model ==============
class Event(Base):
    __tablename__ = "events"
    
    id = Column(Integer, primary_key=True, index=True)
    church_id = Column(Integer, ForeignKey("churches.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False, index=True)
    description = Column(String(500), nullable=True)  # Max 100 characters enforced in API
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False)
    location = Column(String(500), nullable=True)
    category = Column(String(100), nullable=True)
    is_published = Column(Boolean, default=False, nullable=False, index=True)
    interested_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)
    
    # Relationships
    church = relationship("Church", back_populates="events")

# ============== ChurchSettings Model ==============
class ChurchSettings(Base):
    __tablename__ = "church_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    church_id = Column(Integer, ForeignKey("churches.id"), unique=True, nullable=False, index=True)
    email_on_interest = Column(Boolean, default=True, nullable=False)
    daily_digest = Column(Boolean, default=False, nullable=False)
    event_reminders = Column(Boolean, default=True, nullable=False)
    reminder_hours_before = Column(Integer, default=24, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)
    
    # Relationships
    church = relationship("Church", back_populates="settings")

# ============== EditRequest Model ==============
class EditRequest(Base):
    __tablename__ = "edit_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    church_id = Column(Integer, ForeignKey("churches.id"), nullable=False, index=True)
    field_name = Column(String(100), nullable=False)  # e.g., 'church_name', 'location', etc.
    new_value = Column(Text, nullable=False)  # The requested new value
    reason = Column(Text, nullable=True)  # Why the church is requesting this change
    status = Column(String(20), default="pending", nullable=False, index=True)  # pending, approved, rejected
    requested_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    responded_at = Column(DateTime, nullable=True)  # When admin approved/rejected
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)
    
    # Relationships
    church = relationship("Church", back_populates="edit_requests")
