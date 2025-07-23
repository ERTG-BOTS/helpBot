import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import DefaultKeyBuilder, RedisStorage
from aiogram.types import BotCommand

from infrastructure.database.setup import create_engine, create_session_pool
from tgbot.config import Config, load_config
from tgbot.handlers import routers_list
from tgbot.middlewares.config import ConfigMiddleware
from tgbot.middlewares.database import DatabaseMiddleware
from tgbot.services import broadcaster
from tgbot.services.logger import setup_logging
from tgbot.services.scheduler import remove_old_topics, scheduler

logger = logging.getLogger(__name__)

bot_config = load_config(".env")


async def on_startup(bot: Bot, admin_ids: list[int]):
    await broadcaster.broadcast(bot, admin_ids, "Bot started")


def register_global_middlewares(
    dp: Dispatcher, config: Config, bot: Bot, session_pool=None
):
    """
    Register global middlewares for the given dispatcher.
    Global middlewares here are the ones that are applied to all the handlers (you specify the type of update)

    :param dp: The dispatcher instance.
    :type dp: Dispatcher
    :param config: The configuration object from the loaded configuration.
    :param session_pool: Optional session pool object for the database using SQLAlchemy.
    :return: None
    """
    middleware_types = [
        ConfigMiddleware(config),
        DatabaseMiddleware(config=config, bot=bot, session_pool=session_pool),
    ]

    for middleware_type in middleware_types:
        dp.message.outer_middleware(middleware_type)
        dp.callback_query.outer_middleware(middleware_type)


def get_storage(config):
    """
    Return storage based on the provided configuration.

    Args:
        config (Config): The configuration object.

    Returns:
        Storage: The storage object based on the configuration.

    """
    if config.tg_bot.use_redis:
        return RedisStorage.from_url(
            config.redis.dsn(),
            key_builder=DefaultKeyBuilder(with_bot_id=True, with_destiny=True),
        )
    else:
        return MemoryStorage()


async def main():
    setup_logging()

    config = load_config(".env")
    storage = get_storage(config)

    bot = Bot(
        token=config.tg_bot.token, default=DefaultBotProperties(parse_mode="HTML")
    )
    await bot.set_my_commands(
        commands=[
            BotCommand(command="start", description="Главное меню"),
            BotCommand(
                command="release", description="Освободить вопрос (для старших)"
            ),
            BotCommand(command="end", description="Закрыть вопрос"),
        ]
    )
    dp = Dispatcher(storage=storage)

    # Create engines for different databases
    stp_db_engine = create_engine(config.db, db_name=config.db.main_db)

    stp_db = create_session_pool(stp_db_engine)

    # Store session pools in dispatcher
    dp["stp_db"] = stp_db

    dp.include_routers(*routers_list)

    register_global_middlewares(dp, bot_config, bot, stp_db)

    scheduler.add_job(remove_old_topics, "interval", hours=12, args=[bot, stp_db])
    scheduler.start()

    # await on_startup(bot, config.tg_bot.admin_ids)
    try:
        await dp.start_polling(bot)
    finally:
        await stp_db_engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.error("Bot was interrupted by the user!")
