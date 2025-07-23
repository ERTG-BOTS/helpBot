import logging
from typing import Sequence

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from infrastructure.database.models import Question, User
from infrastructure.database.repo.requests import RequestsRepo
from tgbot.config import load_config
from tgbot.filters.topic import IsTopicMessage
from tgbot.handlers.group.cmds import end_q_cmd
from tgbot.keyboards.user.main import (
    QuestionQualityDuty,
    finish_question_kb,
)
from tgbot.misc import dicts
from tgbot.misc.helpers import check_premium_emoji
from tgbot.services.logger import setup_logging
from tgbot.services.scheduler import (
    restart_inactivity_timer,
    start_inactivity_timer,
    run_delete_timer,
)

topic_router = Router()

config = load_config(".env")

setup_logging()
logger = logging.getLogger(__name__)


@topic_router.message(IsTopicMessage())
async def handle_q_message(message: Message, repo: RequestsRepo, user: User):
    question: Question = await repo.questions.get_question(
        topic_id=message.message_thread_id
    )

    if message.text == "✅️ Закрыть вопрос":
        await end_q_cmd(message, repo, user)
        return

    if question is not None and question.Status != "closed":
        if not question.TopicDutyFullname:
            await repo.questions.update_question_duty(
                token=question.Token, topic_duty=user.FIO
            )
            await repo.questions.update_question_status(
                token=question.Token, status="in_progress"
            )

            duty_topics_today = await repo.questions.get_questions_count_today(
                duty_fullname=user.FIO
            )
            duty_topics_month = await repo.questions.get_questions_count_last_month(
                duty_fullname=user.FIO
            )

            employee: User = await repo.users.get_user(
                fullname=question.EmployeeFullname
            )

            # Запускаем таймер неактивности для нового вопроса
            if config.tg_bot.activity_status:
                start_inactivity_timer(question.Token, message.bot, repo)

            await message.bot.edit_forum_topic(
                chat_id=config.tg_bot.forum_id,
                message_thread_id=question.TopicId,
                icon_custom_emoji_id=dicts.topicEmojis["in_progress"],
            )
            await message.answer(
                f"""<b>👮‍♂️ Вопрос в работе</b>

На вопрос отвечает <b>{user.FIO}</b> {'(<a href="https://t.me/' + user.Username + '">лс</a>)' if (user.Username != "Не указан" or user.Username != "Скрыто/не определено") else ""}

<blockquote expandable><b>⚒️ Решено:</b> за день {duty_topics_today} / за месяц {duty_topics_month}</blockquote>""",
                disable_web_page_preview=True,
            )

            await message.bot.send_message(
                chat_id=employee.ChatId,
                text=f"""<b>👮‍♂️ Вопрос в работе</b>

Старший <b>{user.FIO}</b> взял вопрос в работу""",
                reply_markup=finish_question_kb(),
            )
            await message.bot.copy_message(
                from_chat_id=config.tg_bot.forum_id,
                message_id=message.message_id,
                chat_id=employee.ChatId,
            )

            logger.info(
                f"[Вопрос] - [В работе] Пользователь {message.from_user.username} ({message.from_user.id}): Вопрос {question.Token} взят в работу"
            )
        else:
            if question.TopicDutyFullname == user.FIO:
                # Перезапускаем таймер неактивности при сообщении от дежурного
                if config.tg_bot.activity_status:
                    restart_inactivity_timer(question.Token, message.bot, repo)

                await message.bot.copy_message(
                    from_chat_id=config.tg_bot.forum_id,
                    message_id=message.message_id,
                    chat_id=question.EmployeeChatId,
                )

                # Уведомление о премиум эмодзи
                have_premium_emoji, emoji_ids = await check_premium_emoji(message)
                if have_premium_emoji and emoji_ids:
                    emoji_sticker_list = await message.bot.get_custom_emoji_stickers(
                        emoji_ids
                    )

                    sticker_info = []
                    for emoji_sticker in emoji_sticker_list:
                        sticker_info.append(f"{emoji_sticker.emoji}")

                    stickers_text = "".join(sticker_info)

                    emoji_message = await message.reply(f"""<b>💎 Премиум эмодзи</b>

Сообщение содержит премиум эмодзи, собеседник увидит бесплатные аналоги: {stickers_text}

<i>Предупреждение удалится через 30 секунд</i>""")
                    await run_delete_timer(
                        bot=message.bot,
                        chat_id=int(config.tg_bot.forum_id),
                        message_ids=[emoji_message.message_id],
                        seconds=30,
                    )

                logger.info(
                    f"[Вопрос] - [Общение] Токен: {question.Token} | Старший: {question.TopicDutyFullname} | Сообщение: {message.text}"
                )
            else:
                await message.reply("""<b>⚠️ Предупреждение</b>

Это не твой чат!

<i>Твое сообщение не отобразится пользователю</i>""")
                logger.warning(
                    f"[Вопрос] - [Общение] Токен: {question.Token} | Старший: {question.TopicDutyFullname} | Сообщение: {message.text}. Чат принадлежит другому старшему"
                )
    elif question.Status == "closed":
        await message.reply("""<b>⚠️ Предупреждение</b>

Текущий вопрос уже закрыт!

<i>Твое сообщение не отобразится пользователю</i>""")
        logger.warning(
            f"[Вопрос] - [Общение] Токен: {question.Token} | Старший: {question.TopicDutyFullname} | Сообщение: {message.text}. Чат уже закрыт"
        )
    else:
        await message.answer("""<b>⚠️ Ошибка</b>

Не удалось найти текущую тему в базе, закрываю""")
        await message.bot.close_forum_topic(
            chat_id=config.tg_bot.forum_id,
            message_thread_id=message.message_thread_id,
        )
        logger.error(
            f"[Вопрос] - [Общение] Не удалось найти вопрос в базе с TopicId = {message.message_thread_id}. Закрыли тему"
        )


@topic_router.callback_query(QuestionQualityDuty.filter(F.return_question))
async def return_q_duty(
    callback: CallbackQuery,
    callback_data: QuestionQualityDuty,
    user: User,
    repo: RequestsRepo,
):
    await callback.answer()
    question: Question = await repo.questions.get_question(token=callback_data.token)
    employee: User = await repo.users.get_user(user_id=question.EmployeeChatId)
    available_to_return_questions: Sequence[
        Question
    ] = await repo.questions.get_available_to_return_questions()
    active_dialogs = await repo.questions.get_active_questions()

    if (
        question.Status == "closed"
        and employee.FIO not in [d.EmployeeFullname for d in active_dialogs]
        and question.Token in [d.Token for d in available_to_return_questions]
        and question.TopicDutyFullname == user.FIO
    ):
        await repo.questions.update_question_status(token=question.Token, status="open")

        await callback.bot.edit_forum_topic(
            chat_id=config.tg_bot.forum_id,
            message_thread_id=question.TopicId,
            name=employee.FIO,
            icon_custom_emoji_id=dicts.topicEmojis["in_progress"],
        )
        await callback.bot.reopen_forum_topic(
            chat_id=config.tg_bot.forum_id, message_thread_id=question.TopicId
        )

        await callback.message.answer("""<b>🔓 Вопрос переоткрыт</b>

Можешь писать сообщения, они будут переданы пользователю""")
        await callback.bot.send_message(
            chat_id=question.EmployeeChatId,
            text=f"""<b>🔓 Вопрос переоткрыт</b>

Старший <b>{employee.FIO}</b> переоткрыл вопрос:
<blockquote expandable><i>{question.QuestionText}</i></blockquote>""",
            reply_markup=finish_question_kb(),
        )
        logger.info(
            f"[Вопрос] - [Переоткрытие] Пользователь {callback.from_user.username} ({callback.from_user.id}): Вопрос {question.Token} переоткрыт старшим"
        )
    elif question.TopicDutyFullname != user.FIO:
        await callback.answer("Это не твой чат!", show_alert=True)
        logger.warning(
            f"[Вопрос] - [Переоткрытие] Пользователь {callback.from_user.username} ({callback.from_user.id}): Неудачная попытка переоткрытия, вопрос {question.Token} принадлежит другому старшему"
        )
    elif employee.FIO in [d.EmployeeFullname for d in active_dialogs]:
        await callback.answer(
            "У пользователя есть другой открытый вопрос", show_alert=True
        )
        logger.error(
            f"[Вопрос] - [Переоткрытие] Пользователь {callback.from_user.username} ({callback.from_user.id}): Неудачная попытка переоткрытия, у пользователя {question.EmployeeFullname} есть другой открытый вопрос"
        )
    elif question.Token not in [d.Token for d in available_to_return_questions]:
        await callback.answer(
            "Вопрос не переоткрыть. Прошло более 24 часов", show_alert=True
        )
        logger.error(
            f"[Вопрос] - [Переоткрытие] Пользователь {callback.from_user.username} ({callback.from_user.id}): Неудачная попытка переоткрытия, диалог {question.Token} был закрыт более 24 часов назад"
        )
    elif question.Status != "closed":
        await callback.answer("Этот вопрос не закрыт", show_alert=True)
        logger.error(
            f"[Вопрос] - [Переоткрытие] Пользователь {callback.from_user.username} ({callback.from_user.id}): Неудачная попытка переоткрытия, диалог {question.Token} не закрыт"
        )
