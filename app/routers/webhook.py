import logging
from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.bot.handler import handle_message
from app.models import Group, Vendor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook", tags=["webhook"])

ADMIN_PHONE = "244924641157"


@router.post("/green")
async def green_webhook(request: Request, db: Session = Depends(get_db)):
    try:
        body = await request.json()
    except Exception:
        return {"status": "invalid_request"}

    webhook_type = body.get("typeWebhook")

    if webhook_type != "incomingMessageReceived":
        return {"status": "ignored"}

    sender_data = body.get("senderData", {})
    chat_id = sender_data.get("chatId", "")

    if "@g.us" in chat_id:
        existing = db.query(Group).filter(Group.whatsapp_id == chat_id).first()
        if not existing:
            group_name = (
                sender_data.get("chatName") or
                sender_data.get("senderName") or
                "Grupo sem nome"
            )
            db.add(Group(
                whatsapp_id=chat_id,
                name=group_name,
                owner_phone="244000000000",
                active=False,
            ))
            db.commit()
        else:
            group_name = sender_data.get("chatName") or sender_data.get("senderName")
            if group_name and existing.name in (existing.whatsapp_id, "Grupo sem nome"):
                existing.name = group_name
                db.commit()
        return {"status": "group_ignored"}

    message_data = body.get("messageData", {})
    sender = sender_data.get("sender", "")
    phone = sender.replace("@c.us", "")

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
        return {"status": "type_ignored"}

    if not phone or (not text and not media_url):
        return {"status": "empty_ignored"}

    if phone == ADMIN_PHONE and text.lower().startswith("admin:"):
        await handle_admin(db, text, chat_id)
        return {"status": "admin_command"}

    await handle_message(db=db, phone=phone, text=text, chat_id=chat_id, media_url=media_url)
    return {"status": "ok"}


async def handle_admin(db: Session, text: str, chat_id: str):
    from app.services.whatsapp import send_text
    from datetime import datetime, timedelta

    cmd = text.lower().replace("admin:", "").strip()

    if cmd == "listar grupos":
        grupos = db.query(Group).all()
        if not grupos:
            await send_text(chat_id, "Nenhum grupo registado.")
            return
        lines = ["📋 *Grupos registados:*\n"]
        for g in grupos:
            estado = "✅" if g.active else "❌"
            lines.append(f"{estado} *{g.name}*\n   ID: `{g.whatsapp_id}`")
        await send_text(chat_id, "\n".join(lines))
        return

    if cmd.startswith("activar grupo "):
        gid = cmd.replace("activar grupo ", "").strip()
        group = db.query(Group).filter(Group.whatsapp_id == gid).first()
        if not group:
            await send_text(chat_id, f"Grupo não encontrado: {gid}")
            return
        group.active = True
        db.commit()
        await send_text(chat_id, f"✅ Grupo *{group.name}* activado.")
        return

    if cmd.startswith("desactivar grupo "):
        gid = cmd.replace("desactivar grupo ", "").strip()
        group = db.query(Group).filter(Group.whatsapp_id == gid).first()
        if not group:
            await send_text(chat_id, f"Grupo não encontrado: {gid}")
            return
        group.active = False
        db.commit()
        await send_text(chat_id, f"❌ Grupo *{group.name}* desactivado.")
        return

    if cmd.startswith("definir dono "):
        parts = cmd.replace("definir dono ", "").split()
        if len(parts) < 2:
            await send_text(chat_id, "Usa: admin: definir dono {id_grupo} {telefone}")
            return
        gid, owner = parts[0], parts[1]
        group = db.query(Group).filter(Group.whatsapp_id == gid).first()
        if not group:
            await send_text(chat_id, "Grupo não encontrado.")
            return
        group.owner_phone = owner
        db.commit()
        await send_text(chat_id, f"✅ Dono do grupo *{group.name}* definido: {owner}")
        return

    if cmd.startswith("corrigir grupo "):
        gid = cmd.replace("corrigir grupo ", "").strip()
        group = db.query(Group).filter(Group.whatsapp_id == gid).first()
        if not group:
            await send_text(chat_id, "Grupo não encontrado.")
            return
        from app.services.whatsapp import get_group_name
        novo_nome = await get_group_name(gid)
        group.name = novo_nome
        db.commit()
        await send_text(chat_id, f"✅ Grupo corrigido para: *{novo_nome}*")
        return

    if cmd.startswith("renomear grupo "):
        parts = cmd.replace("renomear grupo ", "").split(" ", 1)
        if len(parts) < 2:
            await send_text(chat_id, "Usa: admin: renomear grupo {id} {novo nome}")
            return
        gid, novo_nome = parts[0], parts[1]
        group = db.query(Group).filter(Group.whatsapp_id == gid).first()
        if not group:
            await send_text(chat_id, "Grupo não encontrado.")
            return
        group.name = novo_nome
        db.commit()
        await send_text(chat_id, f"✅ Grupo renomeado para *{novo_nome}*.")
        return

    if cmd.startswith("renovar "):
        parts = cmd.replace("renovar ", "").split()
        if len(parts) < 2:
            await send_text(chat_id, "Usa: admin: renovar {telefone} {dias}\nEx: admin: renovar 244923456789 30")
            return
        phone_target = parts[0]
        dias = int(parts[1])
        v = db.query(Vendor).filter(Vendor.phone == phone_target).first()
        if not v:
            await send_text(chat_id, f"Vendedor {phone_target} não encontrado.")
            return
        v.subscription_end = datetime.utcnow() + timedelta(days=dias)
        db.commit()
        await send_text(chat_id, f"✅ Subscrição de *{v.name}* renovada por {dias} dias.")
        return

    if cmd == "listar vendedores":
        vendors = db.query(Vendor).all()
        if not vendors:
            await send_text(chat_id, "Nenhum vendedor registado.")
            return
        lines = ["👥 *Vendedores registados:*\n"]
        for v in vendors:
            expiry = v.subscription_end.strftime("%d/%m/%Y") if v.subscription_end else "sem data"
            estado = "✅" if v.subscription_end and v.subscription_end > datetime.utcnow() else "⚠️ expirado"
            lines.append(f"{estado} *{v.name}* — {v.phone}\n   Expira: {expiry}")
        await send_text(chat_id, "\n".join(lines))
        return

    await send_text(chat_id, (
        "❓ *Comandos admin disponíveis:*\n\n"
        "• admin: listar grupos\n"
        "• admin: activar grupo {id}\n"
        "• admin: desactivar grupo {id}\n"
        "• admin: definir dono {id} {telefone}\n"
        "• admin: corrigir grupo {id}\n"
        "• admin: renomear grupo {id} {novo nome}\n"
        "• admin: listar vendedores\n"
        "• admin: renovar {telefone} {dias}"
    ))