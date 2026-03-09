import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import MenuButtonWebApp, WebAppInfo

import config
from config import BOT_TOKEN
from database import init_db
from handlers import start, triggers, diary, profile, tasks, stop_mode, shop
from scheduler import setup_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не задан в .env файле!")
        sys.exit(1)

    logger.info("Инициализация базы данных...")
    await init_db()
    logger.info("База данных готова.")

    # Load points configuration from database
    await config.load_points_from_db()
    logger.info("Конфигурация очков загружена.")

    # Load menu settings from database
    await config.load_menu_from_db()
    logger.info("Настройки меню загружены.")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Register routers
    dp.include_router(start.router)
    dp.include_router(triggers.router)
    dp.include_router(diary.router)
    dp.include_router(profile.router)
    dp.include_router(tasks.router)
    dp.include_router(stop_mode.router)
    dp.include_router(shop.router)

    # Fetch and cache bot username
    me = await bot.get_me()
    config.BOT_USERNAME = me.username
    logger.info(f"Бот: @{me.username}")

    # Set Mini App menu button (appears in chat input bar — most reliable Mini App launcher)
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="🎮 Приложение",
                web_app=WebAppInfo(url="https://vadbag.su/app")
            )
        )
        logger.info("Mini App menu button configured successfully")
    except Exception as e:
        logger.warning(f"Menu button setup failed (non-critical): {e}")

    # Delete webhook if any (for local polling)
    await bot.delete_webhook(drop_pending_updates=True)

    # Start scheduler
    scheduler = setup_scheduler(bot)
    scheduler.start()
    logger.info("Scheduler запущен (diary 20:00, triggers 13:00, checkins 10/15/18, weekly Sunday 19:00)")

    logger.info("Бот запущен! Нажми Ctrl+C для остановки.")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown()
        await bot.session.close()
        logger.info("Бот остановлен.")


if __name__ == "__main__":
    asyncio.run(main())
