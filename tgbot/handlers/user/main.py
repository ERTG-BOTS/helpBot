import datetime
import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from infrastructure.database.models import Question, User
from infrastructure.database.repo.requests import RequestsRepo
from tgbot.config import load_config
from tgbot.keyboards.user.main import (
    CancelQuestion,
    MainMenu,
    back_kb,
    cancel_question_kb,
    user_kb,
)
from tgbot.misc import dicts
from tgbot.misc.helpers import disable_previous_buttons
from tgbot.misc.states import AskQuestion
from tgbot.services.logger import setup_logging
from tgbot.services.scheduler import remove_question_timer, start_inactivity_timer

user_router = Router()

config = load_config(".env")

setup_logging()
logger = logging.getLogger(__name__)


@user_router.message(CommandStart())
async def main_cmd(message: Message, state: FSMContext, stp_db):
    async with stp_db() as session:
        repo = RequestsRepo(session)
        user: User = await repo.users.get_user(user_id=message.from_user.id)

    state_data = await state.get_data()

    if user:
        await message.answer(
            f"""👋 Привет, <b>{user.FIO}</b>!

Я - бот-помощник

<i>Используй меню для управление ботом</i>""",
            reply_markup=user_kb(
                is_role_changed=True
                if state_data.get("role") or user.Role == 10
                else False
            ),
        )
        logging.info(
            f"{'[Админ]' if state_data.get('role') or user.Role == 10 else '[Юзер]'} {message.from_user.username} ({message.from_user.id}): Открыто юзер-меню"
        )
    else:
        await message.answer(f"""Привет, <b>@{message.from_user.username}</b>!
        
Не нашел тебя в списке зарегистрированных пользователей

Регистрация происходит через бота Графиков
Если возникли сложности с регистраций обратись к МиП

Если ты зарегистрировался недавно, напиши <b>/start</b>""")


@user_router.callback_query(MainMenu.filter(F.menu == "main"))
async def main_cb(callback: CallbackQuery, stp_db, state: FSMContext):
    async with stp_db() as session:
        repo = RequestsRepo(session)
        user: User = await repo.users.get_user(user_id=callback.from_user.id)

        employee_topics_today = await repo.questions.get_questions_count_today(
            employee_fullname=user.FIO
        )
        employee_topics_month = await repo.questions.get_questions_count_last_month(
            employee_fullname=user.FIO
        )

    state_data = await state.get_data()

    await callback.message.edit_text(
        f"""Привет, <b>{user.FIO}</b>!

Я - бот-вопросник

Используй меню, чтобы выбрать действие""",
        reply_markup=user_kb(
            is_role_changed=True if state_data.get("role") or user.Role == 10 else False
        ),
    )
    logging.info(
        f"{'[Админ]' if state_data.get('role') or user.Role == 10 else '[Юзер]'} {callback.from_user.username} ({callback.from_user.id}): Открыто юзер-меню"
    )


@user_router.callback_query(MainMenu.filter(F.menu == "ask"))
async def ask_question(callback: CallbackQuery, stp_db, state: FSMContext):
    async with stp_db() as session:
        repo = RequestsRepo(session)
        employee: User = await repo.users.get_user(user_id=callback.from_user.id)

    state_data = await state.get_data()

    msg = await callback.message.edit_text(
        """<b>🤔 Суть вопроса</b>

Отправь вопрос и вложения одним сообщением""",
        reply_markup=back_kb(),
    )

    await state.update_data(messages_with_buttons=[msg.message_id])
    await state.set_state(AskQuestion.question)
    logging.info(
        f"{'[Админ]' if state_data.get('role') or employee.Role == 10 else '[Юзер]'} {callback.from_user.username} ({callback.from_user.id}): Открыто меню нового вопроса"
    )


@user_router.message(AskQuestion.question)
async def question_text(message: Message, stp_db, state: FSMContext):
    async with stp_db() as session:
        repo = RequestsRepo(session)
        employee: User = await repo.users.get_user(user_id=message.from_user.id)

    await state.update_data(question=message.text)
    await state.update_data(question_message_id=message.message_id)

    # Отключаем кнопки на предыдущих шагах
    await disable_previous_buttons(message, state)

    state_data = await state.get_data()

    employee_topics_today = await repo.questions.get_questions_count_today(
        employee_fullname=employee.FIO
    )
    employee_topics_month = await repo.questions.get_questions_count_last_month(
        employee_fullname=employee.FIO
    )

    # Выключаем все предыдущие кнопки
    await disable_previous_buttons(message, state)

    new_topic = await message.bot.create_forum_topic(
        chat_id=config.tg_bot.forum_id,
        name=employee.FIO,
        icon_custom_emoji_id=dicts.topicEmojis["open"],
    )  # Создание темы

    # Now add the question within the same session
    new_question = await repo.questions.add_question(
        employee_chat_id=message.chat.id,
        employee_fullname=employee.FIO,
        topic_id=new_topic.message_thread_id,
        start_time=datetime.datetime.now(),
        question_text=state_data.get("question"),
    )  # Добавление вопроса в БД

    # All database operations are now complete


    await message.answer(
        """<b>✅ Успешно</b>
    
Вопрос передан на рассмотрение, в скором времени тебе ответят""",
        reply_markup=cancel_question_kb(token=new_question.Token),
    )

    # Запускаем таймер неактивности для нового вопроса (только если статус "open")
    if new_question.Status == "open" and config.tg_bot.activity_status:
        start_inactivity_timer(new_question.Token, message.bot, stp_db)

    topic_info_msg = await message.bot.send_message(
        chat_id=config.tg_bot.forum_id,
        message_thread_id=new_topic.message_thread_id,
        text=f"""Вопрос задает <b>{employee.FIO}</b> {'(<a href="https://t.me/' + employee.Username + '">лс</a>)' if (employee.Username != "Не указан" or employee.Username != "Скрыто/не определено") else ""}

<blockquote expandable><b>👔 Должность:</b> {employee.Position}
<b>👑 РГ:</b> {employee.Boss}
    
<b>❓ Вопросов:</b> за день {employee_topics_today} / за месяц {employee_topics_month}</blockquote>""",
        disable_web_page_preview=True,
    )

    await message.bot.copy_message(
        chat_id=config.tg_bot.forum_id,
        message_thread_id=new_topic.message_thread_id,
        from_chat_id=message.chat.id,
        message_id=state_data.get("question_message_id"),
    )  # Копирование сообщения специалиста в тему

    await message.bot.pin_chat_message(
        chat_id=config.tg_bot.forum_id,
        message_id=topic_info_msg.message_id,
        disable_notification=True,
    )  # Пин информации о специалисте

    await state.clear()
    logging.info(
        f"{'[Админ]' if state_data.get('role') or employee.Role == 10 else '[Юзер]'} {message.from_user.username} ({message.from_user.id}): Создан новый вопрос {new_question.Token}"
    )


@user_router.callback_query(CancelQuestion.filter(F.action == "cancel"))
async def cancel_question(
    callback: CallbackQuery, callback_data: CancelQuestion, stp_db, state: FSMContext
):
    async with stp_db() as session:
        repo = RequestsRepo(session)
        question: Question = await repo.questions.get_question(
            token=callback_data.token
        )

    if (
        question
        and question.Status == "open"
        and not question.TopicDutyFullname
        and not question.EndTime
    ):
        await callback.bot.edit_forum_topic(
            chat_id=config.tg_bot.forum_id,
            message_thread_id=question.TopicId,
            icon_custom_emoji_id=dicts.topicEmojis["fired"],
        )
        await callback.bot.close_forum_topic(
            chat_id=config.tg_bot.forum_id, message_thread_id=question.TopicId
        )
        await remove_question_timer(bot=callback.bot, question=question, stp_db=stp_db)
        await callback.bot.send_message(
            chat_id=config.tg_bot.forum_id,
            message_thread_id=question.TopicId,
            text="""<b>🔥 Отмена вопроса</b>
        
Специалист отменил вопрос

<i>Вопрос будет удален через 30 секунд</i>""",
        )
        await callback.answer("Вопрос успешно удален")
        await main_cb(callback=callback, state=state, stp_db=stp_db)
    elif not question:
        await callback.answer("Не удалось найти отменяемый вопрос")
        await main_cb(callback=callback, state=state, stp_db=stp_db)
    else:
        await callback.answer("Вопрос не может быть отменен. Он уже в работе")