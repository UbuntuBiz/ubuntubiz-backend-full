from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.database.models import (
    BlockchainTransaction,
    BlockchainEvent,
    User,
)
from app.schemas.blockchain import (
    VerifyTransactionRequest,
    BlockchainNetworkResponse,
    BlockchainContractResponse,
    BlockchainTransactionResponse,
    BlockchainEventResponse,
    SyncBlockchainRequest,
    SyncBlockchainResponse,
)
from app.blockchain.provider import provider
from app.blockchain.contract import get_contract_abi, REQUIRED_FUNCTIONS, REQUIRED_EVENTS
from app.blockchain.transaction_verifier import TransactionVerifier
from app.blockchain.synchroniser import BlockchainSynchroniser
from app.api.deps import get_current_user_and_tenant

router = APIRouter(prefix="/blockchain", tags=["Blockchain Integration (Avalanche Fuji)"])


@router.get("/network", response_model=BlockchainNetworkResponse)
def get_network_status():
    """
    Check connection status to Avalanche Fuji C-Chain and verify Chain ID 43113.
    """
    return provider.get_network_info()


@router.get("/contract", response_model=BlockchainContractResponse)
def get_contract_info():
    """
    Retrieve contract deployment details and authentic ABI interface capabilities.
    """
    return BlockchainContractResponse(
        contract_address=provider.contract_address,
        chain_id=provider.expected_chain_id,
        network="Avalanche Fuji C-Chain",
        abi_functions=list(REQUIRED_FUNCTIONS.keys()),
        abi_events=list(REQUIRED_EVENTS.keys()),
    )


@router.post("/verify-transaction")
def verify_transaction(
    req: VerifyTransactionRequest,
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    Verify and synchronize an on-chain transaction signed by the user's wallet (e.g. Core Wallet).
    Validates execution status on Avalanche Fuji, decodes parameters, and records events.
    """
    result = TransactionVerifier.verify_and_sync_transaction(
        db=db,
        tx_hash=req.transaction_hash,
        business_id=current_user.business_id,
        actor=current_user.id
    )
    return result


@router.post("/sync", response_model=SyncBlockchainResponse)
def sync_blockchain_events(
    req: SyncBlockchainRequest = SyncBlockchainRequest(),
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    Synchronize past contract events from Fuji into PostgreSQL.
    """
    res = BlockchainSynchroniser.sync_events(
        db=db,
        from_block=req.from_block,
        to_block=req.to_block
    )
    return SyncBlockchainResponse(**res)


@router.get("/transactions", response_model=List[BlockchainTransactionResponse])
def list_transactions(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    List verified blockchain transactions.
    """
    txs = db.query(BlockchainTransaction).order_by(
        BlockchainTransaction.created_at.desc()
    ).offset(offset).limit(limit).all()
    return txs


@router.get("/transactions/{tx_hash}", response_model=BlockchainTransactionResponse)
def get_transaction(
    tx_hash: str,
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    clean_hash = tx_hash.strip()
    if not clean_hash.startswith("0x"):
        clean_hash = f"0x{clean_hash}"

    tx = db.query(BlockchainTransaction).filter(
        BlockchainTransaction.transaction_hash == clean_hash
    ).first()
    if not tx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction '{tx_hash}' not found in database records"
        )
    return tx


@router.get("/sales", response_model=List[BlockchainEventResponse])
def get_blockchain_sales(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    Retrieve on-chain 'SaleRecorded' events synchronized from Avalanche Fuji.
    """
    events = db.query(BlockchainEvent).filter(
        BlockchainEvent.event_name == "SaleRecorded"
    ).order_by(BlockchainEvent.created_at.desc()).offset(offset).limit(limit).all()
    return events


@router.get("/pools", response_model=List[BlockchainEventResponse])
def get_blockchain_pools(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    Retrieve on-chain 'PoolCreated' and 'PoolJoined' events.
    """
    events = db.query(BlockchainEvent).filter(
        BlockchainEvent.event_name.in_(["PoolCreated", "PoolJoined"])
    ).order_by(BlockchainEvent.created_at.desc()).offset(offset).limit(limit).all()
    return events


@router.get("/orders", response_model=List[BlockchainEventResponse])
def get_blockchain_orders(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    """
    Retrieve on-chain 'OrderCreated' and 'OrderApproved' events.
    """
    events = db.query(BlockchainEvent).filter(
        BlockchainEvent.event_name.in_(["OrderCreated", "OrderApproved"])
    ).order_by(BlockchainEvent.created_at.desc()).offset(offset).limit(limit).all()
    return events
