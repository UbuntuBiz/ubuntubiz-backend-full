from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from web3 import Web3
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from app.database.models import (
    BlockchainTransaction,
    BlockchainEvent,
    AuditLog,
)
from app.blockchain.provider import provider
from app.core.logging import logger


class TransactionVerifier:
    """
    Verifies user-signed transactions on Avalanche Fuji C-Chain.
    The backend NEVER holds private keys. Users sign via Core Wallet or MetaMask,
    and this module independently validates the receipt, status, parameters, and events.
    """

    @classmethod
    def verify_and_sync_transaction(
        cls,
        db: Session,
        tx_hash: str,
        business_id: Optional[str] = None,
        actor: str = "system"
    ) -> Dict[str, Any]:
        w3 = provider.w3
        contract = provider.get_contract()

        # Enforce Fuji Chain ID 43113
        provider.verify_network()

        # Format hash
        clean_hash = tx_hash.strip()
        if not clean_hash.startswith("0x"):
            clean_hash = f"0x{clean_hash}"

        # Check if already processed in database
        existing_tx = db.query(BlockchainTransaction).filter(
            BlockchainTransaction.transaction_hash == clean_hash
        ).first()
        if existing_tx and existing_tx.transaction_status == "confirmed":
            return {
                "transaction_hash": existing_tx.transaction_hash,
                "block_number": existing_tx.block_number,
                "status": existing_tx.transaction_status,
                "function_name": existing_tx.function_name,
                "value_wei": existing_tx.value_wei,
                "already_processed": True,
                "contract_address": existing_tx.contract_address,
            }

        # Retrieve Transaction & Receipt
        try:
            tx = w3.eth.get_transaction(clean_hash)
            receipt = w3.eth.get_transaction_receipt(clean_hash)
        except Exception as e:
            logger.warning(f"Could not retrieve transaction {clean_hash} from Fuji: {e}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Transaction '{clean_hash}' not found or still pending on Avalanche Fuji"
            )

        if not tx or not receipt:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Transaction receipt is pending"
            )

        # Verify Target Contract
        to_address = Web3.to_checksum_address(tx["to"]) if tx.get("to") else None
        if to_address != provider.contract_address:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Transaction target '{to_address}' does not match UbuntuBiz contract '{provider.contract_address}'"
            )

        # Check Transaction Status (1 = success, 0 = reverted)
        tx_status = "confirmed" if receipt.get("status") == 1 else "failed"
        block_number = receipt.get("blockNumber")
        gas_used = receipt.get("gasUsed")
        value_wei = str(tx.get("value", 0))

        # Decode Function Call
        function_name = None
        decoded_args = {}
        try:
            func_obj, func_args = contract.decode_function_input(tx["input"])
            function_name = func_obj.fn_name
            decoded_args = {k: str(v) if isinstance(v, (int, bytes)) else v for k, v in func_args.items()}
        except Exception as e:
            logger.warning(f"Could not decode function input for {clean_hash}: {e}")

        # Decode Logs/Events
        decoded_events = []
        if tx_status == "confirmed":
            decoded_events = cls._decode_receipt_events(contract, receipt)

        # Record or update transaction in PostgreSQL
        if not existing_tx:
            bc_tx = BlockchainTransaction(
                transaction_hash=clean_hash,
                block_number=block_number,
                transaction_status=tx_status,
                contract_address=provider.contract_address,
                related_business_id=business_id,
                function_name=function_name,
                value_wei=value_wei,
                gas_used=gas_used,
                confirmed_at=datetime.now(timezone.utc) if tx_status == "confirmed" else None
            )
            db.add(bc_tx)
        else:
            existing_tx.transaction_status = tx_status
            existing_tx.block_number = block_number
            existing_tx.gas_used = gas_used
            existing_tx.function_name = function_name
            existing_tx.value_wei = value_wei
            existing_tx.confirmed_at = datetime.now(timezone.utc) if tx_status == "confirmed" else None

        # Synchronize Decoded Events with Idempotency Protection
        for evt in decoded_events:
            cls._save_blockchain_event(db, evt, clean_hash, block_number, business_id)

        # Audit
        if business_id:
            audit = AuditLog(
                business_id=business_id,
                actor=actor,
                resource="blockchain_transactions",
                purpose=f"Verified Fuji tx {clean_hash} ({function_name}) - status: {tx_status}"
            )
            db.add(audit)

        db.commit()

        return {
            "transaction_hash": clean_hash,
            "block_number": block_number,
            "status": tx_status,
            "function_name": function_name,
            "decoded_args": decoded_args,
            "value_wei": value_wei,
            "events_count": len(decoded_events),
            "events": decoded_events,
            "contract_address": provider.contract_address,
        }

    @classmethod
    def _decode_receipt_events(cls, contract, receipt) -> List[Dict[str, Any]]:
        decoded_events = []
        event_parsers = [
            contract.events.SaleRecorded(),
            contract.events.PoolCreated(),
            contract.events.PoolJoined(),
            contract.events.OrderCreated(),
            contract.events.OrderApproved(),
        ]
        for parser in event_parsers:
            try:
                processed = parser.process_receipt(receipt)
                for entry in processed:
                    evt_name = entry["event"]
                    raw_args = dict(entry["args"])
                    # Convert BigNumbers/addresses to string for JSON serialization
                    serializable_args = {
                        k: str(v) if isinstance(v, (int, bytes)) else v
                        for k, v in raw_args.items()
                    }
                    
                    event_id = str(
                        raw_args.get("saleId") or
                        raw_args.get("poolId") or
                        raw_args.get("orderId") or
                        f"{entry['transactionHash'].hex()}_{entry['logIndex']}"
                    )

                    decoded_events.append({
                        "name": evt_name,
                        "event_id": event_id,
                        "args": serializable_args,
                        "log_index": entry.get("logIndex", 0)
                    })
            except Exception as e:
                logger.debug(f"Error parsing event: {e}")

        return decoded_events

    @classmethod
    def _save_blockchain_event(
        cls,
        db: Session,
        event_dict: Dict[str, Any],
        tx_hash: str,
        block_number: int,
        business_id: Optional[str] = None
    ) -> Optional[BlockchainEvent]:
        # Idempotency check using unique constraint (contract_address, event_name, event_id)
        existing = db.query(BlockchainEvent).filter(
            BlockchainEvent.contract_address == provider.contract_address,
            BlockchainEvent.event_name == event_dict["name"],
            BlockchainEvent.event_id == event_dict["event_id"]
        ).first()

        if existing:
            return existing

        new_event = BlockchainEvent(
            event_name=event_dict["name"],
            event_id=event_dict["event_id"],
            transaction_hash=tx_hash,
            block_number=block_number,
            contract_address=provider.contract_address,
            payload_json=event_dict["args"],
            related_business_id=business_id
        )
        db.add(new_event)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            return None
        return new_event
