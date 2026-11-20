from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.agents.base import BaseAgent
from app.database.models import User
from app.core.security import verify_pin


class PolicyAgent(BaseAgent):
    name = "policy"
    system_prompt = (
        "You are the Policy and Approval Agent for UbuntuBiz. You enforce role permissions, "
        "check approval requirements, prevent unauthorized financial actions, and require "
        "PIN confirmation for high-value operations (> R500.00)."
    )
    allowed_tools = ["undo_event"]

    HIGH_VALUE_THRESHOLD_CENTS = 50000  # R500.00 in cents

    @classmethod
    def check_operation_policy(
        cls,
        db: Session,
        business_id: str,
        user_id: str,
        action: str,
        amount_cents: int = 0,
        provided_pin: Optional[str] = None
    ) -> Dict[str, Any]:
        user = db.query(User).filter(User.id == user_id, User.business_id == business_id).first()
        if not user:
            return {"allowed": False, "reason": "User not found"}

        if action in {"confirm_sale", "submit_group_request", "undo_event"} and user.role != "owner":
            return {
                "allowed": False,
                "reason": "Only a business owner may approve this operation."
            }

        # High-value operations require owner PIN confirmation
        if amount_cents >= cls.HIGH_VALUE_THRESHOLD_CENTS:
            if not provided_pin:
                return {
                    "allowed": False,
                    "requires_pin": True,
                    "reason": f"High-value operation (R{amount_cents/100:.2f} >= R500.00) requires owner PIN confirmation."
                }
            if not user.pin_hash or not verify_pin(provided_pin, user.pin_hash):
                return {
                    "allowed": False,
                    "requires_pin": True,
                    "reason": "Invalid PIN provided. Operation rejected."
                }

        return {"allowed": True, "reason": "Policy checks passed"}
