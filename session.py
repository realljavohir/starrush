"""
Userbot uchun SESSION_STRING olish (kompyuteringizda bir marta ishga tushiring).

    pip install telethon
    python session.py

Gift'lar shu akkauntning Stars balansidan yuboriladi, shuning uchun
alohida (asosiy bo'lmagan) akkaunt ishlatish tavsiya etiladi.
Chiqqan qatorni Render'da SESSION_STRING sifatida saqlang va hech kimga bermang —
u akkauntingizga to'liq kirish huquqini beradi.
"""
import asyncio
import os

from telethon import TelegramClient
from telethon.sessions import StringSession


async def main():
    api_id = int(os.environ.get("API_ID") or input("API_ID (my.telegram.org): ").strip())
    api_hash = os.environ.get("API_HASH") or input("API_HASH: ").strip()

    client = TelegramClient(StringSession(), api_id, api_hash)
    # Telefon raqam (+998...), Telegramdan kelgan kod va (bo'lsa) 2 bosqichli parol so'raladi
    await client.start()

    me = await client.get_me()
    print(f"\nUlandi: {me.first_name} (id {me.id})")
    print("\n===== SESSION_STRING (pastdagi qatorni to'liq nusxalang) =====\n")
    print(client.session.save())
    print("\n===============================================================")
    print("Bu qatorni faqat Render Environment'ga qo'ying. Hech kimga ko'rsatmang!")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
