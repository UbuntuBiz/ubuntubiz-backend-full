from typing import Dict, Any, Optional
from datetime import date
from sqlalchemy.orm import Session
from app.agents.base import BaseAgent


class AnalyticsAgent(BaseAgent):
    name = "analytics"
    system_prompt = (
        "You are the Analytics Agent for UbuntuBiz. You answer performance questions, "
        "explain daily/weekly revenue and gross profit, and identify cash variances. "
        "You must narrate verified numbers from MCP tools and never invent financial figures."
    )
    allowed_tools = ["get_metric", "get_sales_summary", "list_alerts", "get_stock"]

    @classmethod
    def execute(
        cls,
        db: Session,
        business_id: str,
        user_message: str,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        sanitized = cls.sanitize_untrusted_input(user_message).lower()

        if "alert" in sanitized:
            alerts = cls.call_tool(
                db=db,
                tool_name="list_alerts",
                args={"status_filter": "active"},
                business_id=business_id,
                task_id=task_id
            )
            return {
                "agent": cls.name,
                "status": "completed",
                "alerts": alerts,
                "response": f"You have {len(alerts)} active operational alert(s)."
            }

        # Otherwise sales and profit summary
        summary = cls.call_tool(
            db=db,
            tool_name="get_sales_summary",
            args={},
            business_id=business_id,
            task_id=task_id
        )

        sales_zar = summary["total_revenue_zar"]
        expenses_zar = round(summary["total_expenses_cents"] / 100.0, 2)
        net_zar = round(summary["net_cash_flow_cents"] / 100.0, 2)
        count = summary["total_sales_count"]

        response_text = (
            f"Here is your business performance summary: You recorded {count} sales totaling "
            f"R{sales_zar:.2f}. Total operating expenses were R{expenses_zar:.2f}, yielding a net "
            f"cash flow of R{net_zar:.2f}."
        )

        return {
            "agent": cls.name,
            "status": "completed",
            "summary": summary,
            "response": response_text
        }
