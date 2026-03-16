import logging
import httpx
from app.config import GREEN_API_URL, GREEN_API_INSTANCE_ID, GREEN_API_TOKEN

logger = logging.getLogger(__name__)

def _url(method: str) -> str:
    return f"{GREEN_API_URL}/waInstance{GREEN_API_INSTANCE_ID}/{method}/{GREEN_API_TOKEN}"

async def send_text(chat_id: str, message: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(_url("sendMessage"), json={
                "chatId": chat_id,
                "message": message,
            })
            r.raise_for_status()
            return r.json()
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem para {chat_id}: {e}")
        return {}

async def send_image(chat_id: str, image_url: str, caption: str = "") -> dict:
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(_url("sendFileByUrl"), json={
                "chatId": chat_id,
                "urlFile": image_url,
                "fileName": "produto.jpg",
                "caption": caption,
            })
            r.raise_for_status()
            return r.json()
    except Exception as e:
        logger.error(f"Erro ao enviar imagem para {chat_id}: {e}")
        return {}

def phone_to_chat_id(phone: str) -> str:
    phone = phone.strip().replace("+", "").replace(" ", "").replace("-", "")
    if not phone.startswith("244"):
        phone = "244" + phone
    return f"{phone}@c.us"