from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.database.models.core import Business, User, AuditLog
from app.schemas.auth import BusinessResponse, BusinessCreate, BusinessUpdate
from app.api.deps import get_current_user_and_tenant
from app.core.permissions import Role, require_roles

router = APIRouter(prefix="/business", tags=["Business Management"])


@router.post("", response_model=BusinessResponse, status_code=status.HTTP_201_CREATED)
def create_business(
    req: BusinessCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_and_tenant)
):
    """
    Register an additional branch or business unit (Owner only).
    """
    if current_user.role != Role.OWNER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only business owners can create new business entities"
        )
    
    new_biz = Business(
        name=req.name,
        area=req.area,
        owner_phone=req.owner_phone,
        language=req.language,
        status="active"
    )
    db.add(new_biz)
    db.commit()
    db.refresh(new_biz)
    return new_biz


@router.get("", response_model=BusinessResponse)
def get_current_business(
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    Retrieve profile details of the authenticated business.
    Tenant isolation guarantees Shop A never sees Shop B.
    """
    biz = db.query(Business).filter(Business.id == current_user.business_id).first()
    if not biz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    return biz


@router.patch("", response_model=BusinessResponse)
def update_business(
    req: BusinessUpdate,
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    Update business settings (Owner / Manager only).
    """
    if current_user.role not in [Role.OWNER.value, Role.MANAGER.value]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    biz = db.query(Business).filter(Business.id == current_user.business_id).first()
    if not biz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")

    if req.name is not None:
        biz.name = req.name
    if req.area is not None:
        biz.area = req.area
    if req.language is not None:
        biz.language = req.language
    if req.status is not None and current_user.role == Role.OWNER.value:
        biz.status = req.status

    audit = AuditLog(
        business_id=biz.id,
        actor=current_user.id,
        resource="businesses",
        purpose="Updated business profile details"
    )
    db.add(audit)
    db.commit()
    db.refresh(biz)
    return biz
