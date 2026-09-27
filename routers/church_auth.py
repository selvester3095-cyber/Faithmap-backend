from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from datetime import timedelta
from passlib.context import CryptContext
import jwt
import os

router = APIRouter(prefix="/api/church", tags=["church-auth"])

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"

# ============ Models ============
class ChurchLoginRequest(BaseModel):
    email: str
    password: str

class ChurchRegisterRequest(BaseModel):
    name: str
    email: EmailStr
    phone: str
    password: str
    denomination: str
    area: str
    city: str

class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str

class ChurchLoginResponse(BaseModel):
    token: str
    church_id: int
    church_name: str
    message: str

# ============ Routes ============

@router.post("/auth/register", response_model=dict)
def register_church(request: ChurchRegisterRequest, db: Session = Depends()):
    """
    Register a new church
    """
    from main import Church, Base, engine

    # Check if email already exists
    existing = db.query(Church).filter(Church.email == request.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Hash password
    hashed_password = pwd_context.hash(request.password)

    # Create church
    church = Church(
        name=request.name,
        email=request.email,
        phone=request.phone,
        password_hash=hashed_password,
        denomination=request.denomination,
        area=request.area,
        city=request.city,
        is_active=True
    )

    db.add(church)
    db.commit()
    db.refresh(church)

    # Generate token
    token = create_access_token(data={"church_id": church.id, "email": church.email})

    return {
        "token": token,
        "church_id": church.id,
        "church_name": church.name,
        "message": "Church registered successfully! Please change your password on first login."
    }


@router.post("/auth/login", response_model=ChurchLoginResponse)
def login_church(request: ChurchLoginRequest, db: Session = Depends()):
    """
    Church login with email and password
    """
    from main import Church

    # Find church
    church = db.query(Church).filter(Church.email == request.email).first()
    if not church:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Verify password
    if not pwd_context.verify(request.password, church.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Generate token
    token = create_access_token(data={"church_id": church.id, "email": church.email})

    return ChurchLoginResponse(
        token=token,
        church_id=church.id,
        church_name=church.name,
        message="Login successful"
    )


@router.post("/auth/change-password")
def change_password(request: PasswordChangeRequest, church_id: int = Depends(get_current_church)):
    """
    Change church password
    """
    from main import Church

    if request.new_password != request.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords don't match")

    if len(request.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    church = db.query(Church).filter(Church.id == church_id).first()
    if not church:
        raise HTTPException(status_code=404, detail="Church not found")

    # Verify current password
    if not pwd_context.verify(request.current_password, church.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    # Update password
    church.password_hash = pwd_context.hash(request.new_password)
    db.commit()

    return {"message": "Password changed successfully"}


# ============ Helper Functions ============

def create_access_token(data: dict, expires_delta: timedelta = timedelta(days=7)):
    """Create JWT token"""
    to_encode = data.copy()
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_current_church(token: str):
    """Verify JWT token and return church_id"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        church_id: int = payload.get("church_id")
        if church_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return church_id
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
