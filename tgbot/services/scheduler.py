import datetime
import logging

import pytz
from aiogram import Bot
from aiogram.types import ReplyKeyboardRemove
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import Sequence

from infrastructure.database.models import Question
from infrastructure.database.repo.requests import RequestsRepo
from tgbot.config import load_config
from tgbot.keyboards.user.main import closed_dialog_kb
from tgbot.misc import dicts
from tgbot.services.logger import setup_logging

scheduler = AsyncIOScheduler(timezone=pytz.utc)
config = load_config(".env")

setup_logging()
logger = logging.getLogger(__name__)


async def delete_messages(bot: Bot, chat_id: int, message_ids: list[int]):
    """Удаляет список сообщений."""
    try:
        for message_id in message_ids:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        print(f"Ошибка при удалении сообщений: {e}")


async def run_delete_timer(
    bot: Bot, chat_id: int, message_ids: list[int], seconds: int = 60
):
    """Delete messages after timer. Default - 60 seconds."""
    try:
        scheduler.add_job(
            delete_messages,
            "date",
            run_date=datetime.datetime.now(tz=pytz.utc)
            + datetime.timedelta(seconds=seconds),
            args=[bot, chat_id, message_ids],
        )
    except Exception as e:
        print(f"Ошибка при планировании удаления сообщений: {e}")


async def remove_question_timer(bot: Bot, question: Question, repo: RequestsRepo):
    warning_job_id = f"remove_{question.Token}"
    scheduler.add_job(
        remove_question,
        "date",
        run_date=datetime.datetime.now(tz=pytz.utc) + datetime.timedelta(seconds=30),
        args=[bot, question, repo],
        id=warning_job_id,
    )


async def remove_question(bot: Bot, question: Question, repo: RequestsRepo):
    await repo.questions.delete_question(token=question.Token)

    await bot.delete_forum_topic(
        chat_id=config.tg_bot.forum_id, message_thread_id=question.TopicId
    )


async def remove_old_topics(bot: Bot, repo: RequestsRepo):
    old_questions: Sequence[Question] = await repo.questions.get_old_questions()

    for question in old_questions:
        await bot.delete_forum_topic(
            chat_id=config.tg_bot.forum_id, message_thread_id=question.TopicId
        )

    result = await repo.questions.delete_question(dialogs=old_questions)
    logger.info(
        f"[Старые топики] Успешно удалено {result['deleted_count']} из {result['total_count']} старых вопросов"
    )
    if result["errors"]:
        logger.info(
            f"[Старые топики] Произошла ошибка при удалении части вопросов: {result['errors']}"
        )


async def send_inactivity_warning(bot: Bot, question_token: str, repo: RequestsRepo):
    """Отправляет предупреждение о неактивности через 5 минут."""
    try:
        question: Question = await repo.questions.get_question(token=question_token)

        if question and question.Status in ["open", "in_progress"]:
            # Отправляем предупреждение в топик
            await bot.send_message(
                chat_id=config.tg_bot.forum_id,
                message_thread_id=question.TopicId,
                text="⚠️ <b>Внимание!</b>\n\nЧат будет автоматически закрыт через 5 минут при отсутствии активности",
            )

            # Отправляем предупреждение пользователю
            await bot.send_message(
                chat_id=question.EmployeeChatId,
                text="⚠️ <b>Внимание!</b>\n\nТвой вопрос будет автоматически закрыт через 5 минут при отсутствии активности",
            )

    except Exception as e:
        logger.error(
            f"[Таймер неактивности] Ошибка при отправке предупреждения для вопроса {question_token}: {e}"
        )


async def auto_close_question(bot: Bot, question_token: str, repo: RequestsRepo):
    """Автоматически закрывает вопрос через 10 минут неактивности."""
    try:
        question: Question = await repo.questions.get_question(token=question_token)

        if question and question.Status in ["open", "in_progress"]:
            # Закрываем вопрос
            await repo.questions.update_question_status(
                token=question_token, status="closed"
            )
            await repo.questions.update_question_end(
                token=question_token, end_time=datetime.datetime.now()
            )

            # Обновляем топик
            await bot.edit_forum_topic(
                chat_id=config.tg_bot.forum_id,
                message_thread_id=question.TopicId,
                name=question.Token,
                icon_custom_emoji_id=dicts.topicEmojis["closed"],
            )
            await bot.close_forum_topic(
                chat_id=config.tg_bot.forum_id, message_thread_id=question.TopicId
            )

            # Уведомляем о закрытии
            await bot.send_message(
                chat_id=config.tg_bot.forum_id,
                message_thread_id=question.TopicId,
                text="🔒 <b>Вопрос автоматически закрыт</b>\n\nВопрос был закрыт из-за отсутствия активности в течение 10 минут",
                reply_markup=closed_dialog_kb(token=question_token, role="duty"),
            )

            await bot.send_message(
                chat_id=question.EmployeeChatId,
                text="🔒 <b>Вопрос автоматически закрыт</b>",
                reply_markup=ReplyKeyboardRemove(),
            )
            await bot.send_message(
                chat_id=question.EmployeeChatId,
                text="Твой вопрос был закрыт из-за отсутствия активности в течение 10 минут",
                reply_markup=closed_dialog_kb(token=question_token, role="employee"),
            )

    except Exception as e:
        logger.error(
            f"[Таймер неактивности] Ошибка при автоматическом закрытии вопроса {question_token}: {e}"
        )


def start_inactivity_timer(question_token: str, bot: Bot, repo: RequestsRepo):
    """Запускает таймер неактивности для вопроса."""
    try:
        # Удаляем существующие задачи для этого вопроса
        stop_inactivity_timer(question_token)

        # Запускаем таймер предупреждения (5 минут)
        warning_job_id = f"warning_{question_token}"
        scheduler.add_job(
            send_inactivity_warning,
            "date",
            run_date=datetime.datetime.now(tz=pytz.utc)
            + datetime.timedelta(minutes=config.tg_bot.activity_warn_minutes),
            args=[bot, question_token, repo],
            id=warning_job_id,
        )

        # Запускаем таймер автозакрытия (10 минут)
        close_job_id = f"close_{question_token}"
        scheduler.add_job(
            auto_close_question,
            "date",
            run_date=datetime.datetime.now(tz=pytz.utc)
            + datetime.timedelta(minutes=config.tg_bot.activity_close_minutes),
            args=[bot, question_token, repo],
            id=close_job_id,
        )

    except Exception as e:
        logger.error(
            f"[Таймер неактивности] Ошибка при запуске таймера для вопроса {question_token}: {e}"
        )


def stop_inactivity_timer(question_token: str):
    """Останавливает таймер неактивности для вопроса."""
    try:
        warning_job_id = f"warning_{question_token}"
        close_job_id = f"close_{question_token}"

        # Удаляем задачи если они существуют
        if scheduler.get_job(warning_job_id):
            scheduler.remove_job(warning_job_id)

        if scheduler.get_job(close_job_id):
            scheduler.remove_job(close_job_id)

    except Exception as e:
        logger.error(
            f"[Таймер неактивности] Ошибка при остановке таймера для вопроса {question_token}: {e}"
        )


def restart_inactivity_timer(question_token: str, bot: Bot, repo: RequestsRepo):
    """Перезапускает таймер неактивности для вопроса."""
    stop_inactivity_timer(question_token)
    start_inactivity_timer(question_token, bot, repo)
