import logging
import asyncio
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Post, Product, Group
from app.services.whatsapp import send_text, send_image
from app.config import APP_BASE_URL, DEFAULT_POST_HOURS

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone="UTC")


async def publish_pending_posts():
    db: Session = SessionLocal()
    try:
        now = datetime.utcnow()
        pending = (
            db.query(Post)
            .filter(Post.status == "pending", Post.scheduled_at <= now)
            .limit(20)
            .all()
        )

        for post in pending:
            product = post.product
            group = post.group

            if not group.active or product.status != "active":
                post.status = "failed"
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
                    try:
                        await send_image(group.whatsapp_id, product.media_url, caption)
                    except Exception:
                        logger.warning(f"Imagem falhou para {group.name}, a tentar só texto...")
                        await send_text(group.whatsapp_id, caption)
                else:
                    await send_text(group.whatsapp_id, caption)

                logger.info(f"Post {post.id} enviado para {group.name}")
                post.status = "sent"
                post.sent_at = datetime.utcnow()
            except Exception as e:
                post.status = "failed"
                logger.error(f"Falha no post {post.id} grupo {group.name}: {e}")

            db.commit()
            await asyncio.sleep(60)

    finally:
        db.close()


def schedule_product(db: Session, product_id: int, group_ids: list[int]):
    now = datetime.utcnow()

    scheduled = None
    for h in DEFAULT_POST_HOURS:
        slot = now.replace(hour=h, minute=0, second=0, microsecond=0)
        if slot > now:
            scheduled = slot
            break

    if not scheduled:
        tomorrow = now + timedelta(days=1)
        scheduled = tomorrow.replace(
            hour=DEFAULT_POST_HOURS[0], minute=0, second=0, microsecond=0
        )

    for group_id in group_ids:
        post = Post(
            product_id=product_id,
            group_id=group_id,
            scheduled_at=scheduled,
            status="pending",
        )
        db.add(post)

    db.commit()
    logger.info(f"Produto {product_id} agendado para {len(group_ids)} grupos às {scheduled}")


def start_scheduler():
    scheduler.add_job(
        publish_pending_posts,
        trigger="interval",
        minutes=5,
        id="publisher",
        replace_existing=True,
        next_run_time=datetime.utcnow(),
    )
    scheduler.start()
    logger.info("Scheduler iniciado.")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
