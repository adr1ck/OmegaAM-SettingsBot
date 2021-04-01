from telethon import TelegramClient
from telethon.sessions import StringSession
import asyncpg
from os import getenv

api_id = int(getenv('API_ID'))
api_hash = getenv('API_HASH')
bot_token = getenv('BOT_TOKEN')
db_uri = getenv('DB_URI')
chat_id = int(getenv('CHAT_ID'))

pool: asyncpg.pool.Pool
bot = TelegramClient(StringSession(), api_id, api_hash)
bot.start(bot_token=bot_token)


async def create_pool():
    global pool
    pool = await asyncpg.create_pool(db_uri, max_size=5, min_size=5)

bot.loop.run_until_complete(create_pool())
