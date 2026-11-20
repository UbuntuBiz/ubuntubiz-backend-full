from typing import Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.database.models import Approval, AgentTask, User
from app.services.sales_service import SalesService
from app.services.procurement_service import ProcurementService
from app.agents.policy_agent import PolicyAgent
from app.core.logging import logger


class ApprovalService:
    @classmethod
    def decide_approval(
        cls,
        db: Session,
        business_id: str,
        approval_id: str,
        decision: str,  # "approved" or "rejected"
        user_id: str,
        decided_via: str = "web",
        pin: Optional[str] = None
    ) -> Dict[str, Any]:
        approval = db.query(Approval).filter(
            Approval.id == approval_id,
            Approval.business_id == business_id
        ).first()

        if not approval:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval request not found")

        if approval.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Approval has already been decided as '{approval.status}'"
            )

        if decision not in ["approved", "rejected"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Decision must be 'approved' or 'rejected'")

        if decision == "rejected":
            approval.status = "rejected"
            approval.decided_via = decided_via
            approval.decided_at = datetime.now(timezone.utc)
            db.commit()
            return {"status": "rejected", "message": "Action was rejected by shop owner"}

        # If approved, execute corresponding business action
        task = approval.task
        action = approval.action

        execution_result = {}
        if action == "confirm_sale" and task and task.result_json:
            items_payload = [
                {"product_id": it["product_id"], "qty": it["qty"], "unit_price": it["unit_price"]}
                for it in task.result_json.get("items", [])
            ]
            total_cents = task.result_json.get("total_cents", 0)

            # Check PolicyAgent
            policy_check = PolicyAgent.check_operation_policy(
                db=db,
                business_id=business_id,
                user_id=user_id,
                action=action,
                amount_cents=total_cents,
                provided_pin=pin
            )
            if not policy_check["allowed"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=policy_check["reason"]
                )

            # Record Sale in PostgreSQL and deduct inventory via event ledger
            idempotency_key = f"approved_sale_{approval.id}"
            sale = SalesService.record_sale(
                db=db,
                business_id=business_id,
                items=items_payload,
                payment_type="cash",
                idempotency_key=idempotency_key,
                actor=f"approved_by:{user_id}",
                trace_id=task.id
            )
            execution_result = {
                "sale_id": sale.id,
                "total_zar": round(sale.total / 100.0, 2),
                "items_count": len(sale.items)
            }

        elif action == "submit_group_request" and task and task.result_json:
            round_id = task.result_json.get("round_id")
            if round_id:
                round_obj = ProcurementService.submit_group_request(
                    db=db,
                    business_id=business_id,
                    round_id=round_id,
                    actor=f"approved_by:{user_id}"
                )
                execution_result = {"round_id": round_obj.id, "round_status": round_obj.status}

        approval.status = "approved"
        approval.decided_via = decided_via
        approval.decided_at = datetime.now(timezone.utc)
        db.commit()

        return {
            "status": "approved",
            "action": action,
            "execution": execution_result,
            "message": "Approved and executed successfully"
        }
