import asyncio
from app.services.whatsapp import send_text, phone_to_chat_id


async def main():
    chat_id = phone_to_chat_id("244924641157")
    result = await send_text(chat_id, "KiandaBot está vivo! 🚀")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
