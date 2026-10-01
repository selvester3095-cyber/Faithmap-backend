from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
import jwt
from datetime import datetime, timedelta
from database import SessionLocal, get_db
from models import Church

router = APIRouter(prefix="/api/church", tags=["church-auth"])

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Settings
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

# ============== Models ==============
class ChurchRegisterRequest(BaseModel):
    church_name: str
    email: EmailStr
    password: str
    phone: str | None = None
    location: str | None = None

class ChurchLoginRequest(BaseModel):
    email: EmailStr
    password: str

class ChurchChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

class ChurchResponse(BaseModel):
    id: int
    church_name: str
    email: str
    phone: str | None
    location: str | None

    class Config:
        from_attributes = True

# ============== Helper Functions ==============
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# ============== Routes ==============
@router.post("/auth/register", response_model=dict)
def register_church(request: ChurchRegisterRequest, db: Session = Depends(get_db)):
    """Register a new church"""
    # Check if church already exists
    existing_church = db.query(Church).filter(Church.email == request.email).first()
    if existing_church:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Church already registered")
    
    # Hash password
    hashed_password = hash_password(request.password)
    
    # Create new church
    new_church = Church(
        church_name=request.church_name,
        email=request.email,
        password_hash=hashed_password,
        phone=request.phone,
        location=request.location
    )
    
    db.add(new_church)
    db.commit()
    db.refresh(new_church)
    
    # Generate token
    access_token = create_access_token(data={"sub": str(new_church.id)})
    
    return {
        "message": "Church registered successfully",
        "access_token": access_token,
        "token_type": "bearer",
        "church_id": new_church.id
    }

@router.post("/auth/login", response_model=dict)
def login_church(request: ChurchLoginRequest, db: Session = Depends(get_db)):
    """Login a church"""
    # Find church by email
    church = db.query(Church).filter(Church.email == request.email).first()
    if not church or not verify_password(request.password, church.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    
    # Generate token
    access_token = create_access_token(data={"sub": str(church.id)})
    
    return {
        "message": "Login successful",
        "access_token": access_token,
        "token_type": "bearer",
        "church_id": church.id
    }

@router.post("/auth/change-password", response_model=dict)
def change_password(church_id: int, request: ChurchChangePasswordRequest, db: Session = Depends(get_db)):
    """Change church password"""
    # Find church
    church = db.query(Church).filter(Church.id == church_id).first()
    if not church:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Church not found")
    
    # Verify old password
    if not verify_password(request.old_password, church.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Old password is incorrect")
    
    # Update password
    church.password_hash = hash_password(request.new_password)
    db.commit()
    
    return {"message": "Password changed successfully"}
