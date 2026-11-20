from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.database.models import Approval, User
from app.schemas.ai import ApprovalResponse, ApprovalDecisionRequest
from app.services.approval_service import ApprovalService
from app.api.deps import get_current_user_and_tenant

router = APIRouter(prefix="/approvals", tags=["Human-in-the-Loop Approvals"])


@router.get("", response_model=List[ApprovalResponse])
def list_approvals(
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    List approval requests requiring shop owner review.
    """
    query = db.query(Approval).filter(Approval.business_id == current_user.business_id)
    if status_filter:
        query = query.filter(Approval.status == status_filter)
    return query.order_by(Approval.created_at.desc()).all()


@router.get("/{approval_id}", response_model=ApprovalResponse)
def get_approval(
    approval_id: str,
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    approval = db.query(Approval).filter(
        Approval.id == approval_id,
        Approval.business_id == current_user.business_id
    ).first()
    if not approval:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval request not found")
    return approval


@router.post("/{approval_id}/decide")
def decide_approval(
    approval_id: str,
    req: ApprovalDecisionRequest,
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    Approve or reject a pending agent action. If approved, executes underlying business transaction.
    """
    return ApprovalService.decide_approval(
        db=db,
        business_id=current_user.business_id,
        approval_id=approval_id,
        decision=req.decision,
        user_id=current_user.id,
        decided_via=req.decided_via,
        pin=req.pin
    )
