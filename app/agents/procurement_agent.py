from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.agents.base import BaseAgent
from app.database.models import Approval


class ProcurementAgent(BaseAgent):
    name = "procurement"
    system_prompt = (
        "You are the Procurement Agent for UbuntuBiz. You identify collaborative bulk buying "
        "opportunities, draft group purchasing requests, compare supplier quotations, and "
        "request owner approval before publishing. You NEVER transfer funds or sign transactions."
    )
    allowed_tools = ["draft_group_request", "get_bid_status", "compare_bids", "submit_group_request", "list_low_stock"]

    @classmethod
    def execute(
        cls,
        db: Session,
        business_id: str,
        user_message: str,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        sanitized = cls.sanitize_untrusted_input(user_message).lower()

        # Check for bid comparison
        if "compare" in sanitized or "bids" in sanitized or "quotes" in sanitized:
            # Look up active rounds
            return {
                "agent": cls.name,
                "status": "completed",
                "response": "To compare bids, provide a round ID or request group buying drafting."
            }

        # Check low stock and propose group round
        low_stock = cls.call_tool(
            db=db,
            tool_name="list_low_stock",
            args={},
            business_id=business_id,
            task_id=task_id
        )

        if not low_stock:
            return {
                "agent": cls.name,
                "status": "completed",
                "response": "All products currently have sufficient stock. No group purchasing needed right now."
            }

        target_item = low_stock[0]
        item_name = target_item["product_name"]
        suggested_qty = target_item["reorder_point"] * 5
        estimated_cost_cents = target_item["sell_price"] * suggested_qty

        # Draft group request via MCP tool
        draft_res = cls.call_tool(
            db=db,
            tool_name="draft_group_request",
            args={
                "item_name": item_name,
                "target_quantity": suggested_qty,
                "target_cents": estimated_cost_cents
            },
            business_id=business_id,
            task_id=task_id
        )

        round_id = draft_res["round_id"]
        est_zar = round(estimated_cost_cents / 100.0, 2)
        summary = (
            f"Group Bulk Buying Proposal: Drafted round #{round_id} for {suggested_qty}x {item_name} "
            f"(Target: R{est_zar:.2f}) to unlock wholesale supplier pricing."
        )

        # Create human-in-the-loop approval record
        approval = Approval(
            business_id=business_id,
            task_id=task_id,
            action="submit_group_request",
            summary=summary,
            status="pending"
        )
        db.add(approval)
        db.commit()
        db.refresh(approval)

        return {
            "agent": cls.name,
            "status": "awaiting_owner_approval",
            "approval_id": approval.id,
            "round_id": round_id,
            "item_name": item_name,
            "suggested_quantity": suggested_qty,
            "estimated_target_zar": est_zar,
            "response": f"{summary}. Approve to publish this round to neighboring township spazas."
        }
