import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Post, Product, Group
from app.services.whatsapp import send_text, send_image
from app.config import APP_BASE_URL

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone="UTC")


async def publish_pending_posts():
    """Publica posts pendentes respeitando o limite de 5 por grupo por dia."""
    db: Session = SessionLocal()
    try:
        now = datetime.utcnow()
        hoje = now.replace(hour=0, minute=0, second=0, microsecond=0)

        pending = (
            db.query(Post)
            .filter(Post.status == "pending", Post.scheduled_at <= now)
            .limit(20)
            .all()
        )

        posts_hoje_por_grupo = {}
        for post in pending:
            group_id = post.group_id
            if group_id not in posts_hoje_por_grupo:
                count = (
                    db.query(Post)
                    .filter(
                        Post.group_id == group_id,
                        Post.status == "sent",
                        Post.sent_at >= hoje,
                    )
                    .count()
                )
                posts_hoje_por_grupo[group_id] = count

        for post in pending:
            product = post.product
            group = post.group
            group_id = post.group_id

            if not group.active or product.status != "active":
                post.status = "failed"
                db.commit()
                continue

            if posts_hoje_por_grupo.get(group_id, 0) >= 5:
                logger.info(f"Limite diário atingido para grupo {group.name} — post {post.id} adiado")
                post.scheduled_at = post.scheduled_at + timedelta(days=1)
                db.commit()
                continue

            tracking_url = f"{APP_BASE_URL}/p/{product.short_code}"
            caption = (
                f"🛍 *{product.name}*\n\n"
                f"{product.description}\n\n"
                f"💰 *{int(product.price):,} Kz*\n\n"
                f"👆 Para comprar clica no link:\n{tracking_url}"
            )

            try:
                if product.media_url:
                    await send_image(group.whatsapp_id, product.media_url, caption)
                else:
                    await send_text(group.whatsapp_id, caption)

                post.status = "sent"
                post.sent_at = datetime.utcnow()
                posts_hoje_por_grupo[group_id] = posts_hoje_por_grupo.get(group_id, 0) + 1
                logger.info(f"Post {post.id} enviado para {group.name}")
            except Exception as e:
                post.status = "failed"
                logger.error(f"Falha no post {post.id}: {e}")

            db.commit()
    finally:
        db.close()


async def cleanup_inactive_products():
    """Avisa vendedores sobre produtos sem vendas há 30 dias."""
    db: Session = SessionLocal()
    try:
        from app.models import Vendor, Sale
        cutoff = datetime.utcnow() - timedelta(days=30)

        vendors = db.query(Vendor).filter(Vendor.state == "active").all()

        for vendor in vendors:
            produtos_inativos = (
                db.query(Product)
                .filter(
                    Product.vendor_id == vendor.id,
                    Product.status == "active",
                    Product.created_at <= cutoff,
                )
                .all()
            )

            sem_vendas = []
            for p in produtos_inativos:
                venda_recente = (
                    db.query(Sale)
                    .filter(
                        Sale.product_id == p.id,
                        Sale.confirmed_at >= cutoff,
                    )
                    .first()
                )
                if not venda_recente:
                    sem_vendas.append(p)

            if not sem_vendas:
                continue

            chat_id = f"{vendor.phone}@c.us"
            lines = [
                f"🔔 *Olá {vendor.name}!*\n\n"
                f"Os seguintes produtos estão activos há mais de 30 dias sem vendas:\n"
            ]
            for p in sem_vendas[:10]:
                lines.append(f"• *{p.name}* — {int(p.price):,} Kz  |  código: `{p.short_code}`")

            lines.append(
                "\nPara apagar um produto envia:\n"
                "*apagar produto*\n\n"
                "Para manter tudo como está, ignora esta mensagem."
            )
            await send_text(chat_id, "\n".join(lines))
            logger.info(f"Aviso de limpeza enviado para {vendor.name}")

    finally:
        db.close()


def schedule_product(db: Session, product_id: int, group_ids: list[int]):
    """Agenda um produto para ser publicado 3 vezes em cada grupo."""
    intervals = [
        timedelta(hours=1),
        timedelta(hours=24),
        timedelta(hours=72),
    ]
    now = datetime.utcnow()

    for group_id in group_ids:
        for interval in intervals:
            post = Post(
                product_id=product_id,
                group_id=group_id,
                scheduled_at=now + interval,
                status="pending",
            )
            db.add(post)

    db.commit()


def start_scheduler():
    scheduler.add_job(
        publish_pending_posts,
        trigger="interval",
        minutes=5,
        id="publisher",
        replace_existing=True,
        next_run_time=datetime.utcnow(),
    )
    scheduler.add_job(
        cleanup_inactive_products,
        trigger="interval",
        days=30,
        id="cleanup",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler iniciado.")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()