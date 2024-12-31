import logging

from models import create_tables
from bot import *
from handlers import *
from models import create_tables

logging.basicConfig(level=logging.INFO)

async def main():
    await create_tables()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(check_prices_periodically())
    asyncio.run(main())




