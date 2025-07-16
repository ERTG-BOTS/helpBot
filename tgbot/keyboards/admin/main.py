from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


class AdminMenu(CallbackData, prefix="admin_menu"):
    menu: str


class ChangeRole(CallbackData, prefix="role"):
    role: str


# Основная клавиатура для команды /start
def admin_kb() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text="📥 Файл вопросов",
                callback_data=AdminMenu(menu="dialog_download").pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="👶🏻 Стать вопрошающим", callback_data=ChangeRole(role="spec").pack()
            ),
        ]
    ]

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=buttons,
    )
    return keyboard
