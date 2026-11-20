from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, ConfigDict


class VerifyTransactionRequest(BaseModel):
    transaction_hash: str = Field(..., min_length=64, max_length=66, description="Avalanche Fuji 0x transaction hash")


class BlockchainNetworkResponse(BaseModel):
    network: str
    rpc_url: str
    expected_chain_id: int
    connected_chain_id: Optional[int]
    is_connected: bool
    contract_address: str
    latest_block: Optional[int]


class BlockchainContractResponse(BaseModel):
    contract_address: str
    chain_id: int
    network: str
    abi_functions: List[str]
    abi_events: List[str]


class BlockchainTransactionResponse(BaseModel):
    id: str
    transaction_hash: str
    block_number: Optional[int]
    transaction_status: str
    contract_address: str
    related_business_id: Optional[str]
    function_name: Optional[str]
    value_wei: str
    gas_used: Optional[int]
    created_at: datetime
    confirmed_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class BlockchainEventResponse(BaseModel):
    id: str
    event_name: str
    event_id: str
    transaction_hash: str
    block_number: int
    contract_address: str
    payload_json: Dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SyncBlockchainRequest(BaseModel):
    from_block: Optional[int] = None
    to_block: Optional[int] = None


class SyncBlockchainResponse(BaseModel):
    synced_from: int
    synced_to: int
    events_found: int
    checkpoint: int
