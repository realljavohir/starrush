from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID = 21208592          # sahifadagi App api_id
API_HASH = "ba0052bfc78739be2b71d61c0ac61d08"           # sahifadagi App api_hash, qo'shtirnoq ichida

with TelegramClient(StringSession(), API_ID, API_HASH) as c:
    print(c.session.save())
