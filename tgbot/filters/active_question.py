import logging

from aiogram.filters import BaseFilter
from aiogram.types import Message
from sqlalchemy import Sequence

from infrastructure.database.models import Question
from infrastructure.database.repo.requests import RequestsRepo
from tgbot.services.logger import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


class ActiveQuestion(BaseFilter):
    async def __call__(
        self, obj: Message, repo: RequestsRepo, **kwargs
    ) -> dict[str, str] | bool:
        current_dialogs: Sequence[
            Question
        ] = await repo.questions.get_active_questions()

        for dialog in current_dialogs:
            if dialog.EmployeeChatId == obj.from_user.id:
                active_dialog_token = dialog.Token
                return {"active_dialog_token": active_dialog_token}

        return False


class ActiveQuestionWithCommand(BaseFilter):
    def __init__(self, command: str = None):
        self.command = command

    async def __call__(
        self, obj: Message, repo: RequestsRepo, **kwargs
    ) -> None | bool | dict[str, str]:
        if self.command:
            if not obj.text or not obj.text.startswith(f"/{self.command}"):
                return False

            current_dialogs: Sequence[
                Question
            ] = await repo.questions.get_active_questions()

            for dialog in current_dialogs:
                if dialog.EmployeeChatId == obj.from_user.id:
                    return {"active_dialog_token": dialog.Token}

            return False


class ActiveQuestionWithReplyCommand(BaseFilter):
    def __init__(self, command: str = None):
        self.command = command

    async def __call__(
        self, obj: Message, repo: RequestsRepo, **kwargs
    ) -> None | bool | dict[str, str]:
        if self.command:
            if not obj.text or not obj.text.startswith(f"/{self.command}"):
                return False

            current_dialogs: Sequence[
                Question
            ] = await repo.questions.get_active_questions()

            for dialog in current_dialogs:
                if dialog.EmployeeChatId == obj.from_user.id:
                    return {"active_dialog_token": dialog.Token}

            return False
