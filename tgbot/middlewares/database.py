import logging
from typing import Any, Awaitable, Callable, Dict, Union

from aiogram import BaseMiddleware, Bot
from aiogram.types import CallbackQuery, Message

from infrastructure.database.models import User
from infrastructure.database.repo.requests import RequestsRepo
from tgbot.config import Config
from tgbot.services.logger import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


class DatabaseMiddleware(BaseMiddleware):
    def __init__(self, config: Config, bot: Bot, session_pool) -> None:
        self.session_pool = session_pool
        self.bot = bot
        self.config = config

    async def __call__(
        self,
        handler: Callable[
            [Union[Message, CallbackQuery], Dict[str, Any]], Awaitable[Any]
        ],
        event: Union[Message, CallbackQuery],
        data: Dict[str, Any],
    ) -> Any:
        async with self.session_pool() as session:
            repo: RequestsRepo = RequestsRepo(session)

            user: User = await repo.users.get_user(user_id=event.from_user.id)

            message_thread_id = None
            is_bot = False

            if isinstance(event, Message):
                # Обычное текстовое сообщение
                message_thread_id = event.message_thread_id
                is_bot = event.from_user.is_bot
            elif isinstance(event, CallbackQuery) and event.message:
                # CallbackQuery - проверяем оригинальное сообщение
                message_thread_id = getattr(event.message, "message_thread_id", None)
                is_bot = event.from_user.is_bot

            # Проверка на существования пользователя
            if not user and message_thread_id and not is_bot:
                await self.bot.ban_chat_member(
                    chat_id=self.config.tg_bot.forum_id, user_id=event.from_user.id
                )
                await self.bot.send_message(
                    chat_id=self.config.tg_bot.forum_id,
                    text=f"""<b>Блокировка</b>

Пользователь с id {event.from_user.id} не найден в базе""",
                )
                return

            # Проверка роли пользователя для доступа к группе
            if (
                user
                and user.Role is not 10
                and message_thread_id
                and not is_bot
            ):
                await self.bot.ban_chat_member(
                    chat_id=self.config.tg_bot.forum_id, user_id=event.from_user.id
                )
                await self.bot.send_message(
                    chat_id=self.config.tg_bot.forum_id,
                    text=f"""<b>Блокировка</b>

Пользователь имеет роль {user.Role}, для доступа нужна роль 10""",
                )
                return

            data["session"] = session
            data["repo"] = repo
            data["user"] = user

            result = await handler(event, data)
        return result