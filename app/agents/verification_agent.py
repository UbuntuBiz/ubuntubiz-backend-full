from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.agents.base import BaseAgent
from app.blockchain.transaction_verifier import TransactionVerifier


class VerificationAgent(BaseAgent):
    name = "verification"
    system_prompt = (
        "You are the Verification Agent for UbuntuBiz. You verify blockchain transaction references "
        "on Avalanche Fuji, check supplier credentials on the verified registry, and report discrepancies. "
        "You NEVER claim that a transaction or credential is verified without evidence."
    )
    allowed_tools = ["verify_credential", "propose_anchor", "receive_delivery"]

    @classmethod
    def verify_transaction_reference(
        cls,
        db: Session,
        business_id: str,
        tx_hash: str
    ) -> Dict[str, Any]:
        """
        Independently verifies transaction receipt on Avalanche Fuji C-Chain.
        """
        try:
            res = TransactionVerifier.verify_and_sync_transaction(
                db=db,
                tx_hash=tx_hash,
                business_id=business_id,
                actor="agent:verification"
            )
            return {
                "verified": res["status"] == "confirmed",
                "transaction_hash": res["transaction_hash"],
                "block_number": res["block_number"],
                "function_name": res["function_name"],
                "value_wei": res["value_wei"],
                "evidence": f"Confirmed on Avalanche Fuji at block {res['block_number']}"
            }
        except Exception as e:
            return {
                "verified": False,
                "transaction_hash": tx_hash,
                "reason": f"Verification failed ({type(e).__name__}).",
                "evidence": None
            }

    @classmethod
    def verify_supplier_credential(
        cls,
        db: Session,
        supplier_id: str,
        credential_type: str
    ) -> Dict[str, Any]:
        return cls.call_tool(
            db=db,
            tool_name="verify_credential",
            args={"supplier_id": supplier_id, "credential_type": credential_type},
            business_id=""
        )
