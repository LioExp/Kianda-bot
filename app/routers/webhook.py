import logging

from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session

from app.config import ADMIN_PHONE
from app.database import get_db
from app.bot.handler import handle_message
from app.models import Group
from app.services.admin import handle_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook", tags=["webhook"])

UNKNOWN_GROUP_OWNER = "244000000000"
UNNAMED_GROUP = "Grupo sem nome"


@router.post("/green")
async def green_webhook(request: Request, db: Session = Depends(get_db)):
    try:
        body = await request.json()
    except Exception:
        return {"status": "invalid_request"}

    webhook_type = body.get("typeWebhook")
    logger.info(f"WEBHOOK: {webhook_type}")

    if webhook_type != "incomingMessageReceived":
        return {"status": "ignored"}

    sender_data = body.get("senderData", {})
    chat_id = sender_data.get("chatId", "")
    sender = sender_data.get("sender", "")
    phone = sender.replace("@c.us", "")

    logger.info(f"SENDER: {sender} | PHONE: {phone} | CHAT: {chat_id}")

    if "@g.us" in chat_id:
        await _handle_group_message(db, sender_data, chat_id)
        return {"status": "group_ignored"}

    message_data = body.get("messageData", {})
    msg_type = message_data.get("typeMessage", "")
    text = ""
    media_url = None

    if msg_type == "textMessage":
        text = message_data.get("textMessageData", {}).get("textMessage", "")
    elif msg_type in ("imageMessage", "videoMessage"):
        file_data = message_data.get("fileMessageData", {})
        media_url = file_data.get("downloadUrl")
        text = file_data.get("caption", "")
    else:
        logger.info(f"TYPE_IGNORED: {msg_type}")
        return {"status": "type_ignored"}

    logger.info(f"TEXT: {text} | MEDIA: {media_url}")

    if not phone or (not text and not media_url):
        return {"status": "empty_ignored"}

    if phone == ADMIN_PHONE and text.lower().startswith("admin:"):
        await handle_admin(db, text, chat_id)
        return {"status": "admin_command"}

    logger.info(f"A processar mensagem de {phone}")
    await handle_message(db=db, phone=phone, text=text, chat_id=chat_id, media_url=media_url)
    return {"status": "ok"}


async def _handle_group_message(db: Session, sender_data: dict, chat_id: str):
    existing = db.query(Group).filter(Group.whatsapp_id == chat_id).first()
    if not existing:
        group_name = (
            sender_data.get("chatName")
            or sender_data.get("senderName")
            or UNNAMED_GROUP
        )
        db.add(Group(
            whatsapp_id=chat_id,
            name=group_name,
            owner_phone=UNKNOWN_GROUP_OWNER,
            active=False,
        ))
        db.commit()
    else:
        group_name = sender_data.get("chatName") or sender_data.get("senderName")
        if group_name and existing.name in (existing.whatsapp_id, UNNAMED_GROUP):
            existing.name = group_name
            db.commit()
