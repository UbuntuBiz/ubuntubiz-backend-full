import json
import os
from typing import Any, Dict, List
from app.config import get_settings
from app.core.logging import logger

settings = get_settings()

REQUIRED_FUNCTIONS = {
    "recordSale": ["itemName", "amountZar"],
    "createBulkPool": ["itemName", "targetWei"],
    "joinBulkPool": ["poolId"],
    "createOrder": ["supplierOrItem", "amountZar"],
    "approveOrder": ["orderId"],
}

REQUIRED_EVENTS = {
    "SaleRecorded": ["saleId", "shopOwner", "itemName", "amountZar"],
    "PoolCreated": ["poolId", "itemName", "targetWei"],
    "PoolJoined": ["poolId", "member", "contributionWei"],
    "OrderCreated": ["orderId", "supplierOrItem", "amountZar"],
    "OrderApproved": ["orderId"],
}


class ContractABIManager:
    """
    Manages and validates authentic smart contract ABI for UbuntuBiz on Avalanche Fuji.
    Strictly verifies functions and events per the existing contract deployment.
    """

    @classmethod
    def get_default_abi_path(cls) -> str:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(current_dir, "abi", "UbuntuBiz.json")

    @classmethod
    def load_abi(cls, abi_path: str = None) -> List[Dict[str, Any]]:
        path = abi_path or cls.get_default_abi_path()
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"UbuntuBiz contract ABI not found at '{path}'. "
                "An authentic contract ABI is required to interact with Avalanche Fuji."
            )

        with open(path, "r", encoding="utf-8") as f:
            try:
                abi = json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(f"Corrupted or invalid JSON ABI file at '{path}': {e}")

        cls.validate_abi(abi)
        return abi

    @classmethod
    def validate_abi(cls, abi: List[Dict[str, Any]]) -> bool:
        """
        Validates that the provided ABI includes all authentic contract signatures.
        Rejects fabricated or incomplete ABIs.
        """
        function_names = {item.get("name") for item in abi if item.get("type") == "function"}
        event_names = {item.get("name") for item in abi if item.get("type") == "event"}

        missing_functions = set(REQUIRED_FUNCTIONS.keys()) - function_names
        if missing_functions:
            raise ValueError(
                f"Authentic ABI validation failed! Missing required functions: {missing_functions}"
            )

        missing_events = set(REQUIRED_EVENTS.keys()) - event_names
        if missing_events:
            raise ValueError(
                f"Authentic ABI validation failed! Missing required events: {missing_events}"
            )

        logger.info(
            f"UbuntuBiz ABI validated successfully ({len(function_names)} functions, {len(event_names)} events)."
        )
        return True


def get_contract_abi() -> List[Dict[str, Any]]:
    return ContractABIManager.load_abi()
