import hashlib
import hmac
import json
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.connection import get_db
from app.database.models import Business, Message, User
from app.core.tenant import set_session_tenant

router = APIRouter(prefix="/webhooks", tags=["Messaging Webhooks"])
settings = get_settings()


@router.get("/whatsapp", response_class=PlainTextResponse)
def verify_whatsapp_webhook(
    mode: str | None = Query(None, alias="hub.mode"),
    token: str | None = Query(None, alias="hub.verify_token"),
    challenge: str | None = Query(None, alias="hub.challenge")
):
    if not settings.WHATSAPP_VERIFY_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WhatsApp webhook verification is not configured"
        )
    if (
        mode != "subscribe"
        or not token
        or not hmac.compare_digest(token, settings.WHATSAPP_VERIFY_TOKEN)
        or challenge is None
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Webhook verification failed")
    return challenge


def _text_messages(payload: dict[str, Any]) -> list[dict[str, str]]:
    messages = []
    entries = payload.get("entry", [])
    if not isinstance(entries, list):
        return messages
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("changes", []), list):
            continue
        for change in entry.get("changes", []):
            if not isinstance(change, dict):
                continue
            value = change.get("value")
            if not isinstance(value, dict) or not isinstance(value.get("messages", []), list):
                continue
            for message in value.get("messages", []):
                if not isinstance(message, dict):
                    continue
                text = message.get("text")
                if not isinstance(text, dict):
                    continue
                message_id = message.get("id")
                sender = message.get("from")
                body = text.get("body")
                if (
                    message.get("type") == "text"
                    and isinstance(message_id, str)
                    and 1 <= len(message_id) <= 128
                    and isinstance(sender, str)
                    and sender.isdigit()
                    and 8 <= len(sender) <= 16
                    and isinstance(body, str)
                    and body.strip()
                    and len(body) <= 4096
                ):
                    messages.append({
                        "external_msg_id": message_id,
                        "sender": sender,
                        "content": body
                    })
    return messages


@router.post("/whatsapp", status_code=status.HTTP_202_ACCEPTED)
async def receive_whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    if not settings.WHATSAPP_APP_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WhatsApp webhook signature validation is not configured"
        )

    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > 1_000_000:
                raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Webhook payload is too large")
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid content length") from exc

    body = await request.body()
    if len(body) > 1_000_000:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Webhook payload is too large"
        )
    supplied_signature = request.headers.get("x-hub-signature-256", "")
    expected_signature = "sha256=" + hmac.new(
        settings.WHATSAPP_APP_SECRET.encode("utf-8"),
        body,
        hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(supplied_signature, expected_signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature")

    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook payload")

    stored = 0
    for message in _text_messages(payload):
        sender = re.sub(r"\D", "", message["sender"])
        normalized_phone = func.replace(
            func.replace(func.replace(User.phone, "+", ""), " ", ""),
            "-",
            ""
        )
        matching_users = db.query(User).join(Business).filter(
            normalized_phone == sender,
            Business.status == "active"
        ).limit(2).all()
        if len(matching_users) != 1:
            continue

        set_session_tenant(db, matching_users[0].business_id)
        existing = db.query(Message.id).filter(
            Message.channel == "whatsapp",
            Message.external_msg_id == message["external_msg_id"]
        ).first()
        if existing:
            continue

        db.add(Message(
            business_id=matching_users[0].business_id,
            channel="whatsapp",
            external_msg_id=message["external_msg_id"],
            direction="inbound",
            type="text",
            content=message["content"]
        ))
        stored += 1

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Webhook message conflicts with an existing message"
        )

    return {"status": "accepted", "stored": stored}
