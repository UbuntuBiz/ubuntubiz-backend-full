from typing import Optional
from web3 import Web3
from web3.contract import Contract
from app.config import get_settings
from app.blockchain.contract import get_contract_abi
from app.core.logging import logger

settings = get_settings()

_web3_instance: Optional[Web3] = None


class BlockchainProvider:
    """
    Manages connection to Avalanche Fuji C-Chain and contract instances.
    Enforces Chain ID 43113 validation before accepting transactions.
    """

    def __init__(self, rpc_url: Optional[str] = None, chain_id: Optional[int] = None):
        self.rpc_url = rpc_url or settings.AVAX_FUJI_RPC_URL
        self.expected_chain_id = chain_id or settings.AVAX_FUJI_CHAIN_ID
        self.contract_address = Web3.to_checksum_address(settings.UBUNTUBIZ_CONTRACT_ADDRESS)
        self._w3: Optional[Web3] = None
        self._contract: Optional[Contract] = None

    @property
    def w3(self) -> Web3:
        if self._w3 is None:
            self._w3 = Web3(Web3.HTTPProvider(self.rpc_url, request_kwargs={"timeout": 15}))
        return self._w3

    def set_w3(self, custom_w3: Web3) -> None:
        """Allow injecting a custom or mock Web3 instance for testing."""
        self._w3 = custom_w3
        self._contract = None

    def verify_network(self) -> int:
        """
        Verify connected node matches Avalanche Fuji C-Chain (Chain ID 43113).
        Raises ValueError if chain ID does not match.
        """
        try:
            current_chain_id = self.w3.eth.chain_id
        except Exception as e:
            logger.error(
                f"Failed to query Avalanche Fuji chain ID ({type(e).__name__})"
            )
            raise ConnectionError("Cannot reach the configured Avalanche Fuji RPC") from e

        if current_chain_id != self.expected_chain_id:
            msg = (
                f"Wrong network detected! Expected Avalanche Fuji (Chain ID {self.expected_chain_id}), "
                f"but connected to Chain ID {current_chain_id}."
            )
            logger.error(msg)
            raise ValueError(msg)

        logger.info(f"Verified connected network: Avalanche Fuji C-Chain (Chain ID {current_chain_id}).")
        return current_chain_id

    def get_contract(self) -> Contract:
        if self._contract is None:
            abi = get_contract_abi()
            self._contract = self.w3.eth.contract(address=self.contract_address, abi=abi)
        return self._contract

    def is_connected(self) -> bool:
        try:
            return self.w3.is_connected()
        except Exception:
            return False

    def get_network_info(self) -> dict:
        connected = self.is_connected()
        chain_id = None
        block_number = None
        if connected:
            try:
                chain_id = self.w3.eth.chain_id
                block_number = self.w3.eth.block_number
            except Exception as e:
                logger.warning(
                    f"Error fetching blockchain network details ({type(e).__name__})"
                )

        return {
            "network": "Avalanche Fuji C-Chain",
            "rpc_url": "[redacted]",
            "expected_chain_id": self.expected_chain_id,
            "connected_chain_id": chain_id,
            "is_connected": connected,
            "contract_address": self.contract_address,
            "latest_block": block_number,
        }


# Global singleton provider
provider = BlockchainProvider()
