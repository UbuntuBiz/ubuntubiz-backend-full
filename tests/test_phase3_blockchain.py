import pytest
from unittest.mock import MagicMock
from hexbytes import HexBytes
from app.blockchain.contract import ContractABIManager, REQUIRED_FUNCTIONS, REQUIRED_EVENTS
from app.blockchain.provider import BlockchainProvider, provider
from app.blockchain.transaction_verifier import TransactionVerifier
from app.database.models import BlockchainTransaction, BlockchainEvent
from tests.test_phase2_inventory_and_sales import register_spaza_shop


def test_authentic_abi_validation():
    # 1. Default authentic ABI should load and validate with zero errors
    abi = ContractABIManager.load_abi()
    assert len(abi) >= 10
    assert ContractABIManager.validate_abi(abi) is True

    # 2. Tampered ABI missing required functions must be rejected
    tampered_abi = [item for item in abi if item.get("name") != "recordSale"]
    with pytest.raises(ValueError, match="Missing required functions"):
        ContractABIManager.validate_abi(tampered_abi)

    # 3. Tampered ABI missing required events must be rejected
    tampered_events = [item for item in abi if item.get("name") != "SaleRecorded"]
    with pytest.raises(ValueError, match="Missing required events"):
        ContractABIManager.validate_abi(tampered_events)


def test_network_verification_and_wrong_chain_rejection():
    bp = BlockchainProvider(rpc_url="https://api.avax-test.network/ext/bc/C/rpc", chain_id=43113)
    mock_w3 = MagicMock()
    mock_w3.eth.chain_id = 43113
    bp.set_w3(mock_w3)

    # Valid Fuji chain ID
    assert bp.verify_network() == 43113

    # Wrong chain ID (e.g. Ethereum mainnet 1) must be rejected
    mock_w3.eth.chain_id = 1
    with pytest.raises(ValueError, match="Wrong network detected"):
        bp.verify_network()


def test_blockchain_network_and_contract_endpoints(client):
    r_net = client.get("/api/blockchain/network")
    assert r_net.status_code == 200
    net_data = r_net.json()
    assert net_data["expected_chain_id"] == 43113
    assert net_data["contract_address"] == "0xE019a407a590C4348ea24c92Dc5Ac6C642e22f91"

    r_contract = client.get("/api/blockchain/contract")
    assert r_contract.status_code == 200
    contract_data = r_contract.json()
    assert "recordSale" in contract_data["abi_functions"]
    assert "joinBulkPool" in contract_data["abi_functions"]
    assert "SaleRecorded" in contract_data["abi_events"]


def test_verify_and_sync_transaction_success(client):
    token, biz_id = register_spaza_shop(client, "Sizwe Trading", "+27821000006")
    headers = {"Authorization": f"Bearer {token}"}

    tx_hash = "0x" + "a" * 64

    # Mock Web3 calls
    mock_w3 = MagicMock()
    mock_w3.eth.chain_id = 43113
    mock_w3.eth.get_transaction.return_value = {
        "hash": HexBytes(tx_hash),
        "to": provider.contract_address,
        "from": "0x1111111111111111111111111111111111111111",
        "value": 100000000000000000,  # 0.1 AVAX in wei
        "input": "0x",
    }
    mock_w3.eth.get_transaction_receipt.return_value = {
        "status": 1,
        "blockNumber": 1234567,
        "gasUsed": 50000,
        "logs": []
    }
    provider.set_w3(mock_w3)

    r_verify = client.post("/api/blockchain/verify-transaction", json={
        "transaction_hash": tx_hash
    }, headers=headers)
    assert r_verify.status_code == 200
    data = r_verify.json()
    assert data["transaction_hash"] == tx_hash
    assert data["status"] == "confirmed"
    assert data["block_number"] == 1234567
    assert data["value_wei"] == "100000000000000000"

    # Query transaction endpoint
    r_tx = client.get(f"/api/blockchain/transactions/{tx_hash}", headers=headers)
    assert r_tx.status_code == 200
    assert r_tx.json()["transaction_status"] == "confirmed"


def test_verify_transaction_wrong_contract_rejection(client):
    token, biz_id = register_spaza_shop(client, "Zola Spaza", "+27821000007")
    headers = {"Authorization": f"Bearer {token}"}

    tx_hash = "0x" + "b" * 64
    wrong_address = "0x000000000000000000000000000000000000dead"

    mock_w3 = MagicMock()
    mock_w3.eth.chain_id = 43113
    mock_w3.eth.get_transaction.return_value = {
        "hash": HexBytes(tx_hash),
        "to": wrong_address,
        "value": 0,
        "input": "0x",
    }
    mock_w3.eth.get_transaction_receipt.return_value = {
        "status": 1,
        "blockNumber": 1234568,
        "gasUsed": 21000,
        "logs": []
    }
    provider.set_w3(mock_w3)

    r_verify = client.post("/api/blockchain/verify-transaction", json={
        "transaction_hash": tx_hash
    }, headers=headers)
    assert r_verify.status_code == 400
    assert "does not match UbuntuBiz contract" in r_verify.json()["detail"]
