import re
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.agents.base import BaseAgent
from app.agents.capture_agent import CaptureAgent
from app.agents.inventory_agent import InventoryAgent
from app.agents.analytics_agent import AnalyticsAgent
from app.agents.procurement_agent import ProcurementAgent
from app.agents.verification_agent import VerificationAgent
from app.core.logging import logger


class OrchestratorAgent(BaseAgent):
    name = "orchestrator"
    system_prompt = (
        "You are the Orchestrator Agent for UbuntuBiz. You determine the user's intent, "
        "delegate to specialized agents (Capture, Inventory, Analytics, Procurement, Verification), "
        "and return concise, friendly responses tailored to South African spaza shop owners. "
        "You NEVER directly access the database or blockchain."
    )
    allowed_tools = []

    @classmethod
    def determine_intent(cls, message: str) -> str:
        text = message.lower()

        # 1. Blockchain Verification Intent
        if "0x" in text or "verify tx" in text or "transaction" in text:
            return "verification"

        # 2. Performance / Analytics Intent (questions about metrics, profit, summary, yesterday)
        if any(w in text for w in ["profit", "summary", "how did", "performance", "yesterday", "margin", "alert", "brief", "report"]):
            return "analytics"

        # 3. Procurement / Group Buying Intent
        if any(w in text for w in ["group", "bulk", "pool", "supplier", "quotation", "bids"]):
            return "procurement"

        # 4. Inventory / Stock Inquiry Intent
        if any(w in text for w in ["stock", "inventory", "reorder", "remaining", "how many", "on hand"]):
            return "inventory"

        # 5. Sale / Expense Capture Intent (active recording)
        if any(w in text for w in ["sold", "sale", "bought", "customer bought", "paid"]):
            return "capture"

        # Default to capture if numbers are present, otherwise analytics
        if re.search(r"\d+", text):
            return "capture"

        return "analytics"

    @classmethod
    def route_and_execute(
        cls,
        db: Session,
        business_id: str,
        user_message: str,
        user_id: str = "owner"
    ) -> Dict[str, Any]:
        """
        Coordinates multi-agent task execution:
        1. Classifies intent.
        2. Logs parent task in agent_tasks.
        3. Delegates to specialized agent.
        4. Logs results and returns response.
        """
        intent = cls.determine_intent(user_message)
        logger.info(f"Orchestrator routed intent '{intent}' for business {business_id}")

        parent_task = cls.record_task_start(
            db=db,
            business_id=business_id,
            intent=intent,
            input_data={"message": user_message, "user_id": user_id}
        )

        try:
            if intent == "capture":
                res = CaptureAgent.execute(
                    db=db,
                    business_id=business_id,
                    user_message=user_message,
                    actor=user_id,
                    task_id=parent_task.id
                )
            elif intent == "inventory":
                res = InventoryAgent.execute(
                    db=db,
                    business_id=business_id,
                    user_message=user_message,
                    task_id=parent_task.id
                )
            elif intent == "procurement":
                res = ProcurementAgent.execute(
                    db=db,
                    business_id=business_id,
                    user_message=user_message,
                    task_id=parent_task.id
                )
            elif intent == "verification":
                # Extract 0x hash if present
                tx_match = re.search(r"0x[a-fA-F0-9]{64}", user_message)
                tx_hash = tx_match.group(0) if tx_match else ""
                res = VerificationAgent.verify_transaction_reference(
                    db=db,
                    business_id=business_id,
                    tx_hash=tx_hash
                )
            else:  # analytics
                res = AnalyticsAgent.execute(
                    db=db,
                    business_id=business_id,
                    user_message=user_message,
                    task_id=parent_task.id
                )

            cls.record_task_finish(db=db, task=parent_task, result_data=res, status="completed")
            return {
                "task_id": parent_task.id,
                "intent": intent,
                "result": res
            }
        except Exception as e:
            error_data = {"error": str(e)}
            cls.record_task_finish(db=db, task=parent_task, result_data=error_data, status="failed")
            logger.error(f"Error executing agent task {parent_task.id}: {e}", exc_info=True)
            return {
                "task_id": parent_task.id,
                "intent": intent,
                "error": str(e),
                "response": "An error occurred while processing your request. Please try again."
            }
