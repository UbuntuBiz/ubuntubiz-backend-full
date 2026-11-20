from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.database.models.core import User, Business
from app.core.security import decode_token
from app.core.tenant import tenant_context, set_session_tenant

security_scheme = HTTPBearer(auto_error=False)


def get_current_user_and_tenant(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Extracts authenticated user, verifies JWT, and guarantees tenant context is set.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    try:
        payload = decode_token(token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token_type = payload.get("type")
    if token_type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type, expected access token",
        )
    
    user_id = payload.get("sub")
    business_id = payload.get("business_id")
    role = payload.get("role")
    
    if not user_id or not business_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token claims",
        )
    
    set_session_tenant(db, business_id)
    user = db.query(User).filter(User.id == user_id, User.business_id == business_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with token not found",
        )
    if payload.get("token_version", 0) != user.token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has been revoked",
        )

    business = db.query(Business).filter(Business.id == business_id).first()
    if not business or business.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Business account is inactive or suspended",
        )

    return user
