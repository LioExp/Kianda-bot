import asyncio
from app.services.whatsapp import send_text, phone_to_chat_id

async def main():
    # Muda para o teu próprio número para testar
    chat_id = phone_to_chat_id("244924641157")  # <- o teu número aqui
    result = await send_text(chat_id, "KiandaBot está vivo! 🚀")
    print(result)

asyncio.run(main())