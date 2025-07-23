import logging
from typing import Sequence

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from infrastructure.database.models import Question, User
from infrastructure.database.repo.requests import RequestsRepo
from tgbot.config import load_config
from tgbot.keyboards.user.main import (
    MainMenu,
    QuestionQualitySpecialist,
    ReturnQuestion,
    back_kb,
    finish_question_kb,
    question_confirm_kb,
    questions_list_kb,
    reopened_question_kb,
    user_kb,
)
from tgbot.misc import dicts
from tgbot.services.logger import setup_logging

employee_return_q = Router()

config = load_config(".env")

setup_logging()
logger = logging.getLogger(__name__)


@employee_return_q.callback_query(QuestionQualitySpecialist.filter(F.return_question))
async def return_finished_q(
    callback: CallbackQuery,
    callback_data: QuestionQualitySpecialist,
    state: FSMContext,
    repo: RequestsRepo,
    user: User,
):
    """
    Возврат вопроса специалистом по клику на клавиатуру после закрытия вопроса.
    """
    await callback.answer()
    await state.clear()
    active_dialogs = await repo.questions.get_active_questions()
    question: Question = await repo.questions.get_question(token=callback_data.token)
    duty: User = await repo.users.get_user(fullname=question.TopicDutyFullname)

    if question.Status == "closed" and user.FIO not in [
        d.EmployeeFullname for d in active_dialogs
    ]:
        await repo.questions.update_question_status(token=question.Token, status="open")

        await callback.bot.edit_forum_topic(
            chat_id=config.tg_bot.forum_id,
            message_thread_id=question.TopicId,
            name=user.FIO,
            icon_custom_emoji_id=dicts.topicEmojis["open"],
        )
        await callback.bot.reopen_forum_topic(
            chat_id=config.tg_bot.forum_id, message_thread_id=question.TopicId
        )

        await callback.message.answer(
            """<b>🔓 Вопрос переоткрыт</b>

Можешь писать сообщения, они будут переданы старшему""",
            reply_markup=finish_question_kb(),
        )
        await callback.bot.send_message(
            chat_id=config.tg_bot.forum_id,
            message_thread_id=question.TopicId,
            text=f"""<b>🔓 Вопрос переоткрыт</b>

Специалист <b>{user.FIO}</b> переоткрыл вопрос после его закрытия

<b>👮‍♂️ Ответственный:</b> {duty.FIO} {'(<a href="https://t.me/' + duty.Username + '">лс</a>)' if (duty.Username != "Не указан" or duty.Username != "Скрыто/не определено") else ""}

<b>❓ Изначальный вопрос:</b>
<blockquote expandable><i>{question.QuestionText}</i></blockquote>""",
            reply_markup=reopened_question_kb(),
            disable_web_page_preview=True,
        )
        logger.info(
            f"[Вопрос] - [Переоткрытие] Пользователь {callback.from_user.username} ({callback.from_user.id}): Вопрос {question.Token} переоткрыт специалистом"
        )
    elif user.FIO in [d.EmployeeFullname for d in active_dialogs]:
        await callback.answer("У тебя есть другой открытый вопрос", show_alert=True)
        logger.info(
            f"[Вопрос] - [Переоткрытие] Пользователь {callback.from_user.username} ({callback.from_user.id}): Неудачная попытка переоткрытия, у специалиста есть другой открытй вопрос"
        )
    elif question.Status != "closed":
        await callback.answer("Этот вопрос не закрыт", show_alert=True)
        logger.error(
            f"[Вопрос] - [Переоткрытие] Пользователь {callback.from_user.username} ({callback.from_user.id}): Неудачная попытка переоткрытия, диалог {question.Token} не закрыт"
        )


@employee_return_q.callback_query(MainMenu.filter(F.menu == "return"))
async def q_list(
    callback: CallbackQuery, state: FSMContext, repo: RequestsRepo, user: User
):
    """
    Меню "🔄 Возврат вопроса". Отображает последние 5 закрытых вопросов за последние 24 часа для возврата в работу со стороны специалиста.
    """
    questions: Sequence[Question] = await repo.questions.get_last_questions_by_chat_id(
        employee_chat_id=callback.from_user.id, limit=5
    )

    state_data = await state.get_data()
    if not questions:
        await callback.message.edit_text(
            """<b>🔄 Возврат вопроса</b>

📝 У тебя нет закрытых вопросов за последние 24 часа""",
            reply_markup=back_kb(),
        )
        logging.warning(
            f"{'[Админ]' if state_data.get('role') or user.Role == 10 else '[Юзер]'} {callback.from_user.username} ({callback.from_user.id}): Открыто меню возврата чата, доступных вопросов нет"
        )
        return

    await callback.message.edit_text(
        """<b>🔄 Возврат вопроса</b>

📋 Выбери вопрос из списка доступных

<i>Отображаются вопросы, закрытые за последние 24 часа</i>""",
        reply_markup=questions_list_kb(questions),
    )
    logging.info(
        f"{'[Админ]' if state_data.get('role') or user.Role == 10 else '[Юзер]'} {callback.from_user.username} ({callback.from_user.id}): Открыто меню возврата чата"
    )


@employee_return_q.callback_query(ReturnQuestion.filter(F.action == "show"))
async def q_info(
    callback: CallbackQuery,
    callback_data: ReturnQuestion,
    state: FSMContext,
    user: User,
    repo: RequestsRepo,
):
    """Меню описания выбранного специалистом вопроса для возврата в работу"""
    question: Question = await repo.questions.get_question(token=callback_data.token)

    if not question:
        await callback.message.edit_text("❌ Вопрос не найден", reply_markup=user_kb())
        return

    state_data = await state.get_data()
    start_date_str = question.StartTime.strftime("%d.%m.%Y %H:%M")
    end_date_str = (
        question.EndTime.strftime("%d.%m.%Y %H:%M")
        if question.EndTime
        else "Не указано"
    )
    question_text = (
        question.QuestionText[:200] + "..."
        if len(question.QuestionText) > 200
        else question.QuestionText
    )

    await callback.message.edit_text(
        f"""<b>🔄 Возврат вопроса</b>

❓ <b>Вопрос:</b>
<blockquote expandable>{question_text}</blockquote>

🚀 <b>Дата создания:</b> {start_date_str}
🔒 <b>Дата закрытия:</b> {end_date_str}

Хочешь вернуть этот вопрос?""",
        reply_markup=question_confirm_kb(question.Token),
        disable_web_page_preview=True,
    )
    logging.warning(
        f"{'[Админ]' if state_data.get('role') or user.Role == 10 else '[Юзер]'} {callback.from_user.username} ({callback.from_user.id}): Открыто описание вопроса {question.Token} для возврата"
    )


@employee_return_q.callback_query(ReturnQuestion.filter(F.action == "confirm"))
async def return_q_confirm(
    callback: CallbackQuery,
    callback_data: ReturnQuestion,
    state: FSMContext,
    user: User,
    repo: RequestsRepo,
):
    """Возврат выбранного специалистом вопроса в работу"""
    await callback.answer()
    await state.clear()
    question = await repo.questions.get_question(token=callback_data.token)

    if not question:
        await callback.message.edit_text("❌ Вопрос не найден", reply_markup=user_kb())
        return

    duty: User = await repo.users.get_user(fullname=question.TopicDutyFullname)
    active_dialogs = await repo.questions.get_active_questions()

    if question.Status == "closed" and user.FIO not in [
        d.EmployeeFullname for d in active_dialogs
    ]:
        # 1. Обновляем статус вопроса на "open"
        await repo.questions.update_question_status(token=question.Token, status="open")

        # 2. Обновляем название и иконку темы
        await callback.bot.edit_forum_topic(
            chat_id=config.tg_bot.forum_id,
            message_thread_id=question.TopicId,
            name=user.FIO,
            icon_custom_emoji_id=dicts.topicEmojis["in_progress"],
        )

        # 3. Переоткрываем тему
        await callback.bot.reopen_forum_topic(
            chat_id=config.tg_bot.forum_id, message_thread_id=question.TopicId
        )

        # 4. Отправляем подтверждающее сообщение специалисту
        await callback.message.answer(
            """<b>🔓 Вопрос переоткрыт</b>

Можешь писать сообщения, они будут переданы старшему""",
            reply_markup=finish_question_kb(),
        )

        # 5. Отправляем уведомление дежурному в тему
        await callback.bot.send_message(
            chat_id=config.tg_bot.forum_id,
            message_thread_id=question.TopicId,
            text=f"""<b>🔓 Вопрос переоткрыт</b>

<b>{user.FIO}</b> переоткрыл вопрос из истории вопросов

<b>👮‍♂️ Ответственный:</b> {duty.FIO} {'(<a href="https://t.me/' + duty.Username + '">лс</a>)' if (duty.Username != "Не указан" or duty.Username != "Скрыто/не определено") else ""}

<b>❓ Изначальный вопрос:</b>
<blockquote expandable><i>{question.QuestionText}</i></blockquote>""",
            reply_markup=reopened_question_kb(),
            disable_web_page_preview=True,
        )
    elif user.FIO in [d.EmployeeFullname for d in active_dialogs]:
        # Проверка на наличие открытых вопросов у специалиста
        await callback.answer("У тебя есть другой открытый вопрос", show_alert=True)
        logger.error(
            f"[Вопрос] - [Переоткрытие] Пользователь {callback.from_user.username} ({callback.from_user.id}): Неудачная попытка переоткрытия, у {question.EmployeeFullname} есть другой открытый вопрос"
        )
    elif question.Status != "closed":
        # Проверка на закрытость вопроса
        await callback.answer("Этот вопрос не закрыт", show_alert=True)
        logger.error(
            f"[Вопрос] - [Переоткрытие] Пользователь {callback.from_user.username} ({callback.from_user.id}): Неудачная попытка переоткрытия, вопрос {question.Token} не закрыт"
        )
    else:
        await callback.answer("Не удалось переоткрыть вопрос", show_alert=True)
        logger.error(
            f"[Вопрос] - [Переоткрытие] Пользователь {callback.from_user.username} ({callback.from_user.id}): Неудачная попытка переоткрытия вопроса {question.Token}"
        )
