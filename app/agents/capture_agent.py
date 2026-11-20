
import re
from typing import Dict, Any, Optional

from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.database.models import Approval, Product


class CaptureAgent(BaseAgent):
    name = "capture"

    system_prompt = (
        "You are the Capture Agent for UbuntuBiz. Your duty is to interpret natural-language "
        "sales and expenses from township spaza shop owners, match product names/aliases, "
        "calculate totals in ZAR, request owner confirmation before writing, and execute sales."
    )

    allowed_tools = ["match_product", "record_sale", "get_stock"]

    @classmethod
    def execute(
        cls,
        db: Session,
        business_id: str,
        user_message: str,
        actor: str = "owner",
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:

        sanitized = cls.sanitize_untrusted_input(user_message)

        # Parse quantity and product phrases
        pattern = r"(\d+)\s+([a-zA-Z\s]+?)(?:and|,|\.|$)"
        matches = re.findall(pattern, sanitized.lower())

        if not matches:
            # Fallback simple search
            pattern_simple = r"(\d+)\s*([a-zA-Z]+)"
            matches = re.findall(pattern_simple, sanitized.lower())

        if not matches:
            return {
                "agent": cls.name,
                "status": "clarification_needed",
                "response": (
                    "Could not identify items and quantities. "
                    "Example: 'I sold 2 bread and 1 coke'."
                )
            }

        matched_items = []
        total_cents = 0

        for qty_str, raw_product_text in matches:
            qty = int(qty_str)

            item_query = (
                raw_product_text
                .replace("sold", "")
                .replace("i", "")
                .strip()
            )

            if not item_query:
                continue

            match_res = cls.call_tool(
                db=db,
                tool_name="match_product",
                args={"text": item_query},
                business_id=business_id,
                task_id=task_id
            )

            if match_res.get("matched"):
                item_total = match_res["sell_price"] * qty
                total_cents += item_total

                matched_items.append({
                    "product_id": match_res["product_id"],
                    "product_name": match_res["product_name"],
                    "qty": qty,
                    "unit_price": match_res["sell_price"],
                    "line_total_zar": round(item_total / 100.0, 2)
                })

            else:
                return {
                    "agent": cls.name,
                    "status": "clarification_needed",
                    "response": (
                        f"I couldn't identify '{item_query}'. "
                        f"Did you mean "
                        f"{match_res.get('suggested_product') or 'another item'}?"
                    )
                }

        if not matched_items:
            return {
                "agent": cls.name,
                "status": "clarification_needed",
                "response": "No matching products found in your catalog."
            }

        # Calculate final sale total
        total_zar = round(total_cents / 100.0, 2)

        # Construct sale summary
        items_summary = ", ".join(
            f"{it['qty']}x {it['product_name']}"
            for it in matched_items
        )

        summary = (
            f"Sale Confirmation: {items_summary}. "
            f"Total: R{total_zar:.2f}"
        )

        # Create human-in-the-loop approval record
        approval = Approval(
            business_id=business_id,
            task_id=task_id,
            action="confirm_sale",
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
            "items": matched_items,
            "total_cents": total_cents,
            "total_zar": total_zar,
            "confirmation_message": (
                f"{summary}. Reply 'YES' to confirm "
                "or approve in the dashboard."
            )
        }
