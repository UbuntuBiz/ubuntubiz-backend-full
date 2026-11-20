from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.agents.base import BaseAgent


class InventoryAgent(BaseAgent):
    name = "inventory"
    system_prompt = (
        "You are the Inventory Agent for UbuntuBiz. Your duty is to monitor spaza shop stock, "
        "identify low-stock products, estimate days of stock remaining, and suggest reorders."
    )
    allowed_tools = ["get_stock", "list_low_stock", "adjust_stock"]

    @classmethod
    def execute(
        cls,
        db: Session,
        business_id: str,
        user_message: str,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        sanitized = cls.sanitize_untrusted_input(user_message).lower()

        if "low" in sanitized or "reorder" in sanitized or "restock" in sanitized:
            low_stock = cls.call_tool(
                db=db,
                tool_name="list_low_stock",
                args={},
                business_id=business_id,
                task_id=task_id
            )
            count = len(low_stock)
            if count == 0:
                resp = "All products are well-stocked above their reorder points."
            else:
                items_str = ", ".join([f"{it['product_name']} ({it['qty_on_hand']} {it['unit']}s left)" for it in low_stock])
                resp = f"You have {count} low-stock item(s) requiring restock: {items_str}."
            return {
                "agent": cls.name,
                "status": "completed",
                "low_stock_count": count,
                "items": low_stock,
                "response": resp
            }
        else:
            all_stock = cls.call_tool(
                db=db,
                tool_name="get_stock",
                args={},
                business_id=business_id,
                task_id=task_id
            )
            return {
                "agent": cls.name,
                "status": "completed",
                "total_products": len(all_stock),
                "items": all_stock,
                "response": f"Your catalog currently tracks {len(all_stock)} products."
            }
