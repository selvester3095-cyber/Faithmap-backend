from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, String, DateTime, Float, Text, Boolean, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Optional, List
import os
from dotenv import load_dotenv
import jwt
import bcrypt
from twilio.rest import Client
import random

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
JWT_SECRET = os.getenv("JWT_SECRET_KEY", "your-secret-key-default")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

app = FastAPI(title="FaithMap API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ DATABASE MODELS ============

class Pastor(Base):
    __tablename__ = "pastors"
    id = Column(String, primary_key=True)
    phone_number = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    full_name = Column(String)
    password_hash = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class OTPToken(Base):
    __tablename__ = "otp_tokens"
    id = Column(String, primary_key=True)
    phone_number = Column(String, index=True)
    otp_code = Column(String)
    expires_at = Column(DateTime)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Church(Base):
    __tablename__ = "churches"
    id = Column(String, primary_key=True)
    pastor_id = Column(String, index=True)
    church_name = Column(String)
    denomination = Column(String)
    phone_number = Column(String)
    email = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    address = Column(Text)
    status = Column(String, default="pending")
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Event(Base):
    __tablename__ = "events"
    id = Column(String, primary_key=True)
    church_id = Column(String, index=True)
    event_name = Column(String)
    event_type = Column(String)
    description = Column(Text, nullable=True)
    start_time = Column(DateTime)
    end_time = Column(DateTime, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    location_name = Column(String, nullable=True)
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)

class Review(Base):
    __tablename__ = "reviews"
    id = Column(String, primary_key=True)
    event_id = Column(String, index=True)
    church_id = Column(String, index=True)
    rating = Column(Float)
    title = Column(String)
    review_text = Column(Text)
    is_public = Column(Boolean, default=False)
    admin_approved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# ============ SCHEMAS (For validation) ============

class PastorRegister(BaseModel):
    phone_number: str
    email: str
    full_name: str

class OTPVerify(BaseModel):
    phone_number: str
    otp_code: str
    password: str

class ChurchRegister(BaseModel):
    church_name: str
    denomination: str
    phone_number: str
    email: str
    latitude: float
    longitude: float
    address: str

class EventCreate(BaseModel):
    event_name: str
    event_type: str
    description: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_name: Optional[str] = None

class ReviewCreate(BaseModel):
    event_id: str
    rating: float
    title: str
    review_text: str

# ============ HELPER FUNCTIONS ============

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), hash.encode())

def generate_otp() -> str:
    return str(random.randint(100000, 999999))

def create_jwt_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.utcnow() + timedelta(days=30)
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm="HS256")
    return encoded_jwt

def send_otp_sms(phone_number: str, otp_code: str):
    """Send OTP via Twilio (optional - requires credentials)"""
    try:
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        twilio_number = os.getenv("TWILIO_PHONE_NUMBER")
        
        if account_sid and auth_token:
            client = Client(account_sid, auth_token)
            client.messages.create(
                body=f"Your FaithMap OTP is {otp_code}. Valid for 10 minutes.",
                from_=twilio_number,
                to=phone_number
            )
    except:
        pass

# ============ ROUTES ============

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "FaithMap API"}

# ---- AUTHENTICATION ROUTES ----

@app.post("/api/v1/auth/register")
def register_pastor(request: PastorRegister, db: Session = Depends(get_db)):
    """Register pastor and send OTP"""
    existing = db.query(Pastor).filter(Pastor.phone_number == request.phone_number).first()
    if existing:
        raise HTTPException(status_code=400, detail="Phone already registered")
    
    otp_code = generate_otp()
    otp_expires = datetime.utcnow() + timedelta(minutes=10)
    
    otp_token = OTPToken(
        id=str(datetime.utcnow().timestamp()),
        phone_number=request.phone_number,
        otp_code=otp_code,
        expires_at=otp_expires
    )
    db.add(otp_token)
    db.commit()
    
    send_otp_sms(request.phone_number, otp_code)
    
    return {
        "message": "OTP sent to your phone",
        "phone_number": request.phone_number,
        "otp": otp_code if ENVIRONMENT == "development" else "***"
    }

@app.post("/api/v1/auth/verify-otp")
def verify_otp(request: OTPVerify, db: Session = Depends(get_db)):
    """Verify OTP and create pastor account"""
    otp_token = db.query(OTPToken).filter(
        OTPToken.phone_number == request.phone_number,
        OTPToken.otp_code == request.otp_code
    ).first()
    
    if not otp_token or otp_token.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    
    pastor = db.query(Pastor).filter(Pastor.phone_number == request.phone_number).first()
    if not pastor:
        pastor = Pastor(
            id=str(datetime.utcnow().timestamp()),
            phone_number=request.phone_number,
            email="",
            full_name="",
            password_hash=hash_password(request.password)
        )
        db.add(pastor)
    
    otp_token.is_verified = True
    db.commit()
    
    token = create_jwt_token({"pastor_id": pastor.id})
    return {"token": token, "pastor_id": pastor.id, "message": "OTP verified"}

@app.post("/api/v1/auth/login")
def login(phone_number: str, password: str, db: Session = Depends(get_db)):
    """Login with phone and password"""
    pastor = db.query(Pastor).filter(Pastor.phone_number == phone_number).first()
    
    if not pastor or not verify_password(password, pastor.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_jwt_token({"pastor_id": pastor.id})
    return {"token": token, "pastor_id": pastor.id}

# ---- CHURCH ROUTES ----

@app.post("/api/v1/churches/register")
def register_church(request: ChurchRegister, token: str, db: Session = Depends(get_db)):
    """Register a church"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        pastor_id = payload.get("pastor_id")
    except:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    church = Church(
        id=str(datetime.utcnow().timestamp()),
        pastor_id=pastor_id,
        church_name=request.church_name,
        denomination=request.denomination,
        phone_number=request.phone_number,
        email=request.email,
        latitude=request.latitude,
        longitude=request.longitude,
        address=request.address,
        status="pending"
    )
    db.add(church)
    db.commit()
    
    return {"id": church.id, "status": "pending", "message": "Church registered, awaiting admin verification"}

@app.get("/api/v1/churches")
def get_churches(db: Session = Depends(get_db)):
    """Get all verified churches"""
    churches = db.query(Church).filter(Church.status == "verified").all()
    return churches

@app.get("/api/v1/churches/{church_id}")
def get_church(church_id: str, db: Session = Depends(get_db)):
    """Get single church details"""
    church = db.query(Church).filter(Church.id == church_id).first()
    if not church:
        raise HTTPException(status_code=404, detail="Church not found")
    return church

# ---- EVENT ROUTES ----

@app.post("/api/v1/churches/{church_id}/events")
def create_event(church_id: str, request: EventCreate, token: str, db: Session = Depends(get_db)):
    """Create event for a church"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        pastor_id = payload.get("pastor_id")
    except:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    church = db.query(Church).filter(Church.id == church_id).first()
    if not church or church.pastor_id != pastor_id:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    event = Event(
        id=str(datetime.utcnow().timestamp()),
        church_id=church_id,
        event_name=request.event_name,
        event_type=request.event_type,
        description=request.description,
        start_time=request.start_time,
        end_time=request.end_time,
        latitude=request.latitude,
        longitude=request.longitude,
        location_name=request.location_name
    )
    db.add(event)
    db.commit()
    
    return {"id": event.id, "message": "Event created"}

@app.get("/api/v1/churches/{church_id}/events")
def get_church_events(church_id: str, db: Session = Depends(get_db)):
    """Get all events for a church"""
    events = db.query(Event).filter(Event.church_id == church_id).all()
    return events

@app.get("/api/v1/search/churches")
def search_churches(
    denomination: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    distance_km: Optional[float] = 10,
    db: Session = Depends(get_db)
):
    """Search churches with filters"""
    query = db.query(Church).filter(Church.status == "verified")
    
    if denomination:
        query = query.filter(Church.denomination == denomination)
    
    churches = query.all()
    
    if latitude and longitude:
        from math import radians, cos, sin, asin, sqrt
        
        def haversine(lat1, lon1, lat2, lon2):
            lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
            dlon = lon2 - lon1
            dlat = lat2 - lat1
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * asin(sqrt(a))
            km = 6371 * c
            return km
        
        nearby = []
        for church in churches:
            if church.latitude and church.longitude:
                dist = haversine(latitude, longitude, church.latitude, church.longitude)
                if dist <= distance_km:
                    nearby.append({"church": church, "distance": dist})
        
        nearby.sort(key=lambda x: x["distance"])
        return [item["church"] for item in nearby]
    
    return churches

# ---- REVIEW ROUTES ----

@app.post("/api/v1/events/{event_id}/reviews")
def create_review(event_id: str, request: ReviewCreate, db: Session = Depends(get_db)):
    """Create a review (only visible to admin initially)"""
    review = Review(
        id=str(datetime.utcnow().timestamp()),
        event_id=event_id,
        church_id=request.event_id,
        rating=request.rating,
        title=request.title,
        review_text=request.review_text,
        is_public=False,
        admin_approved=False
    )
    db.add(review)
    db.commit()
    
    return {"id": review.id, "message": "Review submitted, pending admin approval"}

@app.get("/api/v1/admin/reviews")
def get_pending_reviews(token: str, db: Session = Depends(get_db)):
    """Get all pending reviews (admin only)"""
    reviews = db.query(Review).filter(Review.admin_approved == False).all()
    return reviews

@app.put("/api/v1/admin/reviews/{review_id}/approve")
def approve_review(review_id: str, token: str, db: Session = Depends(get_db)):
    """Approve a review (admin only)"""
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    
    review.admin_approved = True
    review.is_public = True
    db.commit()
    
    return {"message": "Review approved"}

# ---- ADMIN ROUTES ----

@app.get("/api/v1/admin/churches/pending")
def get_pending_churches(token: str, db: Session = Depends(get_db)):
    """Get churches waiting for verification (admin only)"""
    churches = db.query(Church).filter(Church.status == "pending").all()
    return churches

@app.put("/api/v1/admin/churches/{church_id}/verify")
def verify_church(church_id: str, token: str, db: Session = Depends(get_db)):
    """Verify a church (admin only)"""
    church = db.query(Church).filter(Church.id == church_id).first()
    if not church:
        raise HTTPException(status_code=404, detail="Church not found")
    
    church.status = "verified"
    church.verified_at = datetime.utcnow()
    db.commit()
    
    return {"message": "Church verified"}

@app.delete("/api/v1/admin/churches/{church_id}")
def delete_church(church_id: str, token: str, db: Session = Depends(get_db)):
    """Delete a church (admin only)"""
    church = db.query(Church).filter(Church.id == church_id).first()
    if not church:
        raise HTTPException(status_code=404, detail="Church not found")
    
    db.delete(church)
    db.commit()
    
    return {"message": "Church deleted"}

@app.get("/api/v1/admin/stats")
def get_stats(token: str, db: Session = Depends(get_db)):
    """Get dashboard statistics (admin only)"""
    total_churches = db.query(Church).count()
    verified_churches = db.query(Church).filter(Church.status == "verified").count()
    pending_churches = db.query(Church).filter(Church.status == "pending").count()
    total_events = db.query(Event).count()
    pending_reviews = db.query(Review).filter(Review.admin_approved == False).count()
    
    return {
        "total_churches": total_churches,
        "verified_churches": verified_churches,
        "pending_churches": pending_churches,
        "total_events": total_events,
        "pending_reviews": pending_reviews
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
