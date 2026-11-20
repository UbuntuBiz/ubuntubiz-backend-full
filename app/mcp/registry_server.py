import hashlib
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.database.models import Credential, Supplier


class RegistryMCPServer:
    """
    Model Context Protocol (MCP) tool provider for Verified Credentials and Off-Chain Audit Anchors.
    Strictly uses verifiable supplier credentials and off-chain audit hashes.
    """

    @classmethod
    def verify_credential(
        cls,
        db: Session,
        supplier_id: str,
        credential_type: str
    ) -> Dict[str, Any]:
        cred = db.query(Credential).filter(
            Credential.supplier_id == supplier_id,
            Credential.credential_type == credential_type,
            Credential.is_revoked.is_(False)
        ).first()

        if not cred:
            return {
                "supplier_id": supplier_id,
                "credential_type": credential_type,
                "verified": False,
                "reason": "No valid credential found on registry"
            }

        is_expired = False
        if cred.valid_until and cred.valid_until < datetime.now(timezone.utc):
            is_expired = True

        return {
            "supplier_id": supplier_id,
            "credential_type": credential_type,
            "verified": not is_expired,
            "issuer": cred.issuer,
            "valid_until": cred.valid_until.isoformat() if cred.valid_until else None,
            "is_expired": is_expired
        }

    @classmethod
    def propose_anchor(
        cls,
        data_payload: str,
        purpose: str
    ) -> Dict[str, Any]:
        """
        Creates a deterministic SHA-256 fingerprint of application state
        for audit trail referencing without fabricating unsupported smart contract logic.
        """
        digest = hashlib.sha256(data_payload.encode("utf-8")).hexdigest()
        return {
            "purpose": purpose,
            "sha256_hash": f"0x{digest}",
            "anchored_at": datetime.now(timezone.utc).isoformat()
        }
