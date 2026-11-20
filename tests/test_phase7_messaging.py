import hashlib
import hmac
import json

from app.api import webhooks
from app.database.models import Message
from tests.conftest import TestingSessionLocal
from tests.test_phase2_inventory_and_sales import register_spaza_shop


def test_whatsapp_webhook_verification_and_signed_message_deduplication(client, monkeypatch):
    monkeypatch.setattr(webhooks.settings, "WHATSAPP_VERIFY_TOKEN", "test-verify-token")
    monkeypatch.setattr(webhooks.settings, "WHATSAPP_APP_SECRET", "test-app-secret")
    register_spaza_shop(client, "Webhook Shop", "+27821000026")

    verification = client.get("/api/webhooks/whatsapp", params={
        "hub.mode": "subscribe",
        "hub.verify_token": "test-verify-token",
        "hub.challenge": "local-challenge"
    })
    assert verification.status_code == 200
    assert verification.text == "local-challenge"

    body = json.dumps({
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "id": "test-message-1",
                        "from": "27821000026",
                        "type": "text",
                        "text": {"body": "Check my stock"}
                    }]
                }
            }]
        }]
    }, separators=(",", ":")).encode("utf-8")
    signature = "sha256=" + hmac.new(
        b"test-app-secret",
        body,
        hashlib.sha256
    ).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": signature
    }

    first = client.post("/api/webhooks/whatsapp", content=body, headers=headers)
    second = client.post("/api/webhooks/whatsapp", content=body, headers=headers)
    assert first.status_code == 202
    assert first.json()["stored"] == 1
    assert second.status_code == 202
    assert second.json()["stored"] == 0

    db = TestingSessionLocal()
    try:
        assert db.query(Message).filter(
            Message.channel == "whatsapp",
            Message.external_msg_id == "test-message-1"
        ).count() == 1
    finally:
        db.close()


def test_whatsapp_webhook_rejects_bad_signature(client, monkeypatch):
    monkeypatch.setattr(webhooks.settings, "WHATSAPP_APP_SECRET", "test-app-secret")
    response = client.post(
        "/api/webhooks/whatsapp",
        content=b'{"entry":[]}',
        headers={"X-Hub-Signature-256": "sha256=invalid"}
    )
    assert response.status_code == 401
