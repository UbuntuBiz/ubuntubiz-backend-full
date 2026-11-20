from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.database.models.core import Business, User, AuditLog
from app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    PinLoginRequest,
    TokenResponse,
    RefreshTokenRequest,
    UserResponse,
)
from app.core.security import (
    hash_password,
    verify_password,
    hash_pin,
    verify_pin,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.api.deps import get_current_user_and_tenant

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(req: UserRegisterRequest, db: Session = Depends(get_db)):
    """
    Register a new spaza shop owner and create their business profile.
    """
    # Check if phone already registered
    existing_user = db.query(User).filter(User.phone == req.phone).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this phone number is already registered"
        )
    
    # Check if business phone exists
    existing_biz = db.query(Business).filter(Business.owner_phone == req.phone).first()
    if existing_biz:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A business with this owner phone is already registered"
        )
    
    # Create Business
    new_biz = Business(
        name=req.business_name,
        area=req.area,
        owner_phone=req.phone,
        language=req.language,
        status="active"
    )
    db.add(new_biz)
    db.flush()

    # Create Owner User
    pwd_hash = hash_password(req.password)
    pin_h = hash_pin(req.pin) if req.pin else None

    new_user = User(
        business_id=new_biz.id,
        phone=req.phone,
        role="owner",
        password_hash=pwd_hash,
        pin_hash=pin_h
    )
    db.add(new_user)
    db.flush()

    # Create initial audit log
    audit = AuditLog(
        business_id=new_biz.id,
        actor=new_user.id,
        resource="auth",
        purpose="Owner registered spaza shop profile"
    )
    db.add(audit)
    db.commit()

    # Issue tokens
    access_token = create_access_token(
        subject=new_user.id,
        business_id=new_biz.id,
        role=new_user.role
    )
    refresh_token = create_refresh_token(
        subject=new_user.id,
        business_id=new_biz.id
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        business_id=new_biz.id,
        user_id=new_user.id,
        role=new_user.role,
        business_name=new_biz.name
    )


@router.post("/login", response_model=TokenResponse)
def login(req: UserLoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate shop owner or employee using phone and password.
    """
    user = db.query(User).filter(User.phone == req.phone).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect phone number or password"
        )
    
    business = db.query(Business).filter(Business.id == user.business_id).first()
    if not business or business.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Business account is inactive or suspended"
        )

    access_token = create_access_token(
        subject=user.id,
        business_id=user.business_id,
        role=user.role
    )
    refresh_token = create_refresh_token(
        subject=user.id,
        business_id=user.business_id
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        business_id=user.business_id,
        user_id=user.id,
        role=user.role,
        business_name=business.name
    )


@router.post("/login/pin", response_model=TokenResponse)
def login_with_pin(req: PinLoginRequest, db: Session = Depends(get_db)):
    """
    Fast PIN-based login for POS counter terminals and informal spaza operators.
    """
    user = db.query(User).filter(User.phone == req.phone).first()
    if not user or not user.pin_hash or not verify_pin(req.pin, user.pin_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid phone number or PIN"
        )
    
    business = db.query(Business).filter(Business.id == user.business_id).first()
    if not business or business.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Business account is inactive or suspended"
        )

    access_token = create_access_token(
        subject=user.id,
        business_id=user.business_id,
        role=user.role
    )
    refresh_token = create_refresh_token(
        subject=user.id,
        business_id=user.business_id
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        business_id=user.business_id,
        user_id=user.id,
        role=user.role,
        business_name=business.name
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(req: RefreshTokenRequest, db: Session = Depends(get_db)):
    """
    Exchange a valid refresh token for a fresh access token.
    """
    try:
        payload = decode_token(req.refresh_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is not a refresh token"
        )
    
    user_id = payload.get("sub")
    business_id = payload.get("business_id")

    user = db.query(User).filter(User.id == user_id, User.business_id == business_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business or business.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Business is inactive")

    new_access_token = create_access_token(
        subject=user.id,
        business_id=user.business_id,
        role=user.role
    )
    new_refresh_token = create_refresh_token(
        subject=user.id,
        business_id=user.business_id
    )

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        business_id=user.business_id,
        user_id=user.id,
        role=user.role,
        business_name=business.name
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(current_user: User = Depends(get_current_user_and_tenant)):
    """
    Log out the current user and invalidate session context.
    """
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user_and_tenant)):
    """
    Get profile information of the currently authenticated user.
    """
    return current_user
