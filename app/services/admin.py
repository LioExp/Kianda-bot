import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.config import ADMIN_PHONE
from app.models import Vendor, Group, Product, Post
from app.services.whatsapp import send_text, get_group_name

logger = logging.getLogger(__name__)


async def handle_admin(db: Session, text: str, chat_id: str):
    cmd = text.lower().replace("admin:", "").strip()

    if cmd == "listar grupos":
        await _list_groups(db, chat_id)
    elif cmd.startswith("activar grupo "):
        await _activate_group(db, chat_id, cmd)
    elif cmd.startswith("desactivar grupo "):
        await _deactivate_group(db, chat_id, cmd)
    elif cmd.startswith("definir dono "):
        await _set_group_owner(db, chat_id, cmd)
    elif cmd.startswith("corrigir grupo "):
        await _fix_group_name(db, chat_id, cmd)
    elif cmd.startswith("renomear grupo "):
        await _rename_group(db, chat_id, cmd)
    elif cmd.startswith("postar agora "):
        await _post_now(db, chat_id, cmd)
    elif cmd.startswith("renovar "):
        await _renew_subscription(db, chat_id, cmd)
    elif cmd == "listar vendedores":
        await _list_vendors(db, chat_id)
    else:
        await _show_admin_help(chat_id)


async def _list_groups(db: Session, chat_id: str):
    grupos = db.query(Group).all()
    if not grupos:
        await send_text(chat_id, "Nenhum grupo registado.")
        return
    lines = ["📋 *Grupos registados:*\n"]
    for g in grupos:
        estado = "✅" if g.active else "❌"
        lines.append(f"{estado} *{g.name}*\n   ID: `{g.whatsapp_id}`")
    await send_text(chat_id, "\n".join(lines))


async def _activate_group(db: Session, chat_id: str, cmd: str):
    gid = cmd.replace("activar grupo ", "").strip()
    group = db.query(Group).filter(Group.whatsapp_id == gid).first()
    if not group:
        await send_text(chat_id, f"Grupo não encontrado: {gid}")
        return
    group.active = True
    db.commit()
    await send_text(chat_id, f"✅ Grupo *{group.name}* activado.")


async def _deactivate_group(db: Session, chat_id: str, cmd: str):
    gid = cmd.replace("desactivar grupo ", "").strip()
    group = db.query(Group).filter(Group.whatsapp_id == gid).first()
    if not group:
        await send_text(chat_id, f"Grupo não encontrado: {gid}")
        return
    group.active = False
    db.commit()
    await send_text(chat_id, f"❌ Grupo *{group.name}* desactivado.")


async def _set_group_owner(db: Session, chat_id: str, cmd: str):
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


async def _fix_group_name(db: Session, chat_id: str, cmd: str):
    gid = cmd.replace("corrigir grupo ", "").strip()
    group = db.query(Group).filter(Group.whatsapp_id == gid).first()
    if not group:
        await send_text(chat_id, "Grupo não encontrado.")
        return
    novo_nome = await get_group_name(gid)
    group.name = novo_nome
    db.commit()
    await send_text(chat_id, f"✅ Grupo corrigido para: *{novo_nome}*")


async def _rename_group(db: Session, chat_id: str, cmd: str):
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


async def _post_now(db: Session, chat_id: str, cmd: str):
    short_code = cmd.replace("postar agora ", "").strip()
    product = db.query(Product).filter(Product.short_code == short_code).first()
    if not product:
        await send_text(chat_id, f"Produto *{short_code}* não encontrado.")
        return
    grupos = db.query(Group).filter(Group.active == True).all()
    if not grupos:
        await send_text(chat_id, "Nenhum grupo activo.")
        return
    for g in grupos:
        post = Post(
            product_id=product.id,
            group_id=g.id,
            scheduled_at=datetime.utcnow(),
            status="pending",
        )
        db.add(post)
    db.commit()
    await send_text(chat_id, f"✅ Produto *{short_code}* vai ser publicado em até 5 minutos nos {len(grupos)} grupos activos.")


async def _renew_subscription(db: Session, chat_id: str, cmd: str):
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


async def _list_vendors(db: Session, chat_id: str):
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


async def _show_admin_help(chat_id: str):
    await send_text(chat_id, (
        "❓ *Comandos admin disponíveis:*\n\n"
        "• admin: listar grupos\n"
        "• admin: activar grupo {id}\n"
        "• admin: desactivar grupo {id}\n"
        "• admin: definir dono {id} {telefone}\n"
        "• admin: corrigir grupo {id}\n"
        "• admin: renomear grupo {id} {novo nome}\n"
        "• admin: postar agora {codigo}\n"
        "• admin: listar vendedores\n"
        "• admin: renovar {telefone} {dias}"
    ))
