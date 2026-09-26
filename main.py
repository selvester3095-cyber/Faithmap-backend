from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from pydantic import BaseModel
from datetime import datetime, timedelta
import os
import secrets
import jwt
from math import radians, cos, sin, asin, sqrt

# ============================================================================
# ENVIRONMENT VARIABLES
# ============================================================================
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/faithmap")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "faithmap-secret-key-production-2026-selvester-bangalore-church-12345678")
JWT_ALGORITHM = "HS256"
OTP_EXPIRY_MINUTES = 5

# ============================================================================
# DATABASE SETUP
# ============================================================================
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ============================================================================
# DATABASE MODELS
# ============================================================================

class Church(Base):
    __tablename__ = "churches"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    denomination = Column(String)
    network_church = Column(String)
    area = Column(String)
    city = Column(String)
    full_address = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    phone = Column(String)
    email = Column(String)
    website = Column(String, nullable=True)
    pastor_name = Column(String)
    member_name = Column(String)
    member_phone = Column(String)
    admin_notes = Column(String, nullable=True)
    status = Column(String, default="submitted")  # submitted, reviewing, verified, rejected
    rejection_reason = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    verified_at = Column(DateTime, nullable=True)
    
    events = relationship("Event", back_populates="church")
    pastor = relationship("Pastor", uselist=False, back_populates="church")

class Pastor(Base):
    __tablename__ = "pastors"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    phone = Column(String)
    password_hash = Column(String)
    church_id = Column(Integer, ForeignKey("churches.id"))
    is_first_login = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    church = relationship("Church", back_populates="pastor")

class Event(Base):
    __tablename__ = "events"
    
    id = Column(Integer, primary_key=True, index=True)
    church_id = Column(Integer, ForeignKey("churches.id"))
    title = Column(String, index=True)
    description = Column(Text, nullable=True)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    venue = Column(String)
    has_refreshments = Column(String, default="no")  # yes, no, n/a
    notes = Column(String, nullable=True)
    is_published = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(String, nullable=True)
    
    church = relationship("Church", back_populates="events")
    interests = relationship("Interest", back_populates="event")

class EndUser(Base):
    __tablename__ = "end_users"
    
    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String, unique=True, index=True)
    otp = Column(String, nullable=True)
    otp_expires_at = Column(DateTime, nullable=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

class Interest(Base):
    __tablename__ = "interests"
    
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    phone_number = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    event = relationship("Event", back_populates="interests")

# Drop all tables and recreate (clean slate on startup)
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

# ============================================================================
# PYDANTIC SCHEMAS (Request/Response)
# ============================================================================

class SendOTPRequest(BaseModel):
    phone: str

class VerifyOTPRequest(BaseModel):
    phone: str
    otp: str

class EventBase(BaseModel):
    title: str
    description: str
    start_time: datetime
    end_time: datetime
    venue: str
    has_refreshments: str

class EventResponse(EventBase):
    id: int
    church_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class ChurchBase(BaseModel):
    name: str
    denomination: str
    area: str
    city: str
    latitude: float
    longitude: float

class ChurchDetailResponse(ChurchBase):
    id: int
    phone: str
    email: str
    website: str
    pastor_name: str
    
    class Config:
        from_attributes = True

class EventDetailWithChurch(EventBase):
    id: int
    church_id: int
    has_refreshments: str
    notes: str
    church: ChurchDetailResponse
    
    class Config:
        from_attributes = True

class InterestRequest(BaseModel):
    event_id: int
    phone_number: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    message: str

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def generate_otp():
    """Generate 6-digit OTP"""
    return str(secrets.randbelow(1000000)).zfill(6)

def create_access_token(phone: str):
    """Create JWT token for end user"""
    payload = {
        "phone": phone,
        "exp": datetime.utcnow() + timedelta(days=7)
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token

def verify_token(token: str) -> str:
    """Verify JWT token and return phone"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        phone: str = payload.get("phone")
        if phone is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return phone
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great circle distance between two points on earth (in km)"""
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * asin(sqrt(a))
    km = 6371 * c
    return km

# ============================================================================
# FASTAPI APP SETUP
# ============================================================================

app = FastAPI(title="FaithMap API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "FaithMap API"}

# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@app.post("/api/auth/send-otp")
def send_otp(request: SendOTPRequest, db: Session = Depends(get_db)):
    """Send OTP to phone number"""
    phone = request.phone
    
    if not phone or len(phone) < 10:
        raise HTTPException(status_code=400, detail="Invalid phone number")
    
    otp = generate_otp()
    otp_expires = datetime.utcnow() + timedelta(minutes=OTP_EXPIRY_MINUTES)
    
    user = db.query(EndUser).filter(EndUser.phone == phone).first()
    if user:
        user.otp = otp
        user.otp_expires_at = otp_expires
    else:
        user = EndUser(phone=phone, otp=otp, otp_expires_at=otp_expires)
        db.add(user)
    
    db.commit()
    
    # TODO: Send OTP via Twilio
    # from twilio.rest import Client
    # client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    # client.messages.create(to=phone, from_=TWILIO_PHONE, body=f"Your FaithMap OTP is: {otp}")
    
    return {
        "message": "OTP sent to your phone",
        "otp": otp  # Remove in production
    }

@app.post("/api/auth/verify-otp")
def verify_otp(request: VerifyOTPRequest, db: Session = Depends(get_db)):
    """Verify OTP and return JWT token"""
    phone = request.phone
    otp = request.otp
    
    user = db.query(EndUser).filter(EndUser.phone == phone).first()
    
    if not user:
        raise HTTPException(status_code=401, detail="Phone not registered")
    
    if not user.otp or user.otp != otp:
        raise HTTPException(status_code=401, detail="Invalid OTP")
    
    if datetime.utcnow() > user.otp_expires_at:
        raise HTTPException(status_code=401, detail="OTP expired")
    
    token = create_access_token(phone)
    user.is_verified = True
    user.last_login = datetime.utcnow()
    user.otp = None
    db.commit()
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "message": "Login successful"
    }

# ============================================================================
# EVENTS ENDPOINTS (Portal 1)
# ============================================================================

@app.get("/api/events")
def list_events(
    search: str = None,
    denomination: str = None,
    time_period: str = None,
    latitude: float = None,
    longitude: float = None,
    max_distance: float = 25,
    db: Session = Depends(get_db)
):
    """List events with filters"""
    now = datetime.utcnow()
    query = db.query(Event).join(Church).filter(
        Event.is_published == True,
        Event.start_time > now,
        Church.status == "verified",
        Event.deleted_at == None
    )
    
    if search:
        search_lower = search.lower()
        query = query.filter(
            (Event.title.ilike(f"%{search_lower}%")) |
            (Church.name.ilike(f"%{search_lower}%"))
        )
    
    if denomination:
        query = query.filter(Church.denomination == denomination)
    
    events = query.all()
    
    if latitude and longitude:
        filtered_events = []
        for event in events:
            dist = haversine_distance(latitude, longitude, event.church.latitude, event.church.longitude)
            if dist <= max_distance:
                filtered_events.append({
                    "id": event.id,
                    "title": event.title,
                    "start_time": event.start_time,
                    "end_time": event.end_time,
                    "venue": event.venue,
                    "has_refreshments": event.has_refreshments,
                    "church_id": event.church_id,
                    "church_name": event.church.name,
                    "area": event.church.area,
                    "distance_km": round(dist, 2)
                })
        return filtered_events
    
    return [
        {
            "id": event.id,
            "title": event.title,
            "start_time": event.start_time,
            "end_time": event.end_time,
            "venue": event.venue,
            "has_refreshments": event.has_refreshments,
            "church_id": event.church_id,
            "church_name": event.church.name,
            "area": event.church.area
        }
        for event in events
    ]

@app.get("/api/events/{event_id}")
def get_event_detail(event_id: int, db: Session = Depends(get_db)):
    """Get full event details + church info"""
    event = db.query(Event).filter(
        Event.id == event_id,
        Event.is_published == True,
        Event.deleted_at == None
    ).first()
    
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    return {
        "id": event.id,
        "title": event.title,
        "description": event.description,
        "start_time": event.start_time,
        "end_time": event.end_time,
        "venue": event.venue,
        "has_refreshments": event.has_refreshments,
        "notes": event.notes,
        "church": {
            "id": event.church.id,
            "name": event.church.name,
            "denomination": event.church.denomination,
            "area": event.church.area,
            "city": event.church.city,
            "full_address": event.church.full_address,
            "latitude": event.church.latitude,
            "longitude": event.church.longitude,
            "phone": event.church.phone,
            "email": event.church.email,
            "website": event.church.website,
            "pastor_name": event.church.pastor_name
        }
    }

@app.get("/api/churches/{church_id}")
def get_church_detail(church_id: int, db: Session = Depends(get_db)):
    """Get church details + all upcoming events"""
    church = db.query(Church).filter(
        Church.id == church_id,
        Church.status == "verified"
    ).first()
    
    if not church:
        raise HTTPException(status_code=404, detail="Church not found")
    
    now = datetime.utcnow()
    events = db.query(Event).filter(
        Event.church_id == church_id,
        Event.is_published == True,
        Event.start_time > now,
        Event.deleted_at == None
    ).order_by(Event.start_time).all()
    
    return {
        "id": church.id,
        "name": church.name,
        "denomination": church.denomination,
        "network_church": church.network_church,
        "area": church.area,
        "city": church.city,
        "full_address": church.full_address,
        "latitude": church.latitude,
        "longitude": church.longitude,
        "phone": church.phone,
        "email": church.email,
        "website": church.website,
        "pastor_name": church.pastor_name,
        "events": [
            {
                "id": event.id,
                "title": event.title,
                "description": event.description,
                "start_time": event.start_time,
                "end_time": event.end_time,
                "venue": event.venue,
                "has_refreshments": event.has_refreshments,
                "notes": event.notes
            }
            for event in events
        ]
    }

# ============================================================================
# INTERESTS ENDPOINT
# ============================================================================

@app.post("/api/interests")
def record_interest(request: InterestRequest, db: Session = Depends(get_db)):
    """Record user interest in an event"""
    event = db.query(Event).filter(Event.id == request.event_id).first()
    
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    existing = db.query(Interest).filter(
        Interest.event_id == request.event_id,
        Interest.phone_number == request.phone_number
    ).first()
    
    if existing:
        return {"message": "You already expressed interest in this event"}
    
    interest = Interest(event_id=request.event_id, phone_number=request.phone_number)
    db.add(interest)
    db.commit()
    
    # TODO: Send notification to pastor email
    # TODO: Send WhatsApp/SMS to pastor
    
    return {"message": "Interest recorded successfully", "event_id": request.event_id}

# ============================================================================
# RUN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
