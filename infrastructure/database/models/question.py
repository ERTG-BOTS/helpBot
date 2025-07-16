import datetime
from typing import Optional
from datetime import date

from sqlalchemy import BIGINT, String, Boolean, Integer, Date, DateTime
from sqlalchemy import Unicode
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TableNameMixin


class Question(Base, TableNameMixin):
    """
    Класс, представляющий сущность вопросов.

    Attributes:
        Token (Mapped[str]): Уникальный идентификатор токена (первичный ключ).
        TopicId (Mapped[int]): ID топика.
        TopicDutyFullname (Mapped[str]): ФИО ответственного за вопрос.
        EmployeeFullname (Mapped[str]): ФИО сотрудника.
        EmployeeChatId (Mapped[int]): Chat ID сотрудника.
        QuestionText (Mapped[str]): Текст вопроса.
        StartTime (Mapped[Optional[date]]): Время начала вопроса.
        EndTime (Mapped[Optional[date]]): Время окончания вопроса.

    Methods:
        __repr__(): Returns a string representation of the Question object.

    Inherited Attributes:
        Inherits from Base and TableNameMixin classes, which provide additional attributes and functionality.

    Inherited Methods:
        Inherits methods from Base and TableNameMixin classes, which provide additional functionality.
    """
    __tablename__ = 'BotHelpQuestions'

    Token: Mapped[str] = mapped_column(String(255), primary_key=True)
    TopicId: Mapped[int] = mapped_column(Integer, nullable=False)
    TopicDutyFullname: Mapped[str] = mapped_column(Unicode)
    EmployeeFullname: Mapped[str] = mapped_column(Unicode, nullable=False)
    EmployeeChatId: Mapped[int] = mapped_column(BIGINT, nullable=False)
    QuestionText: Mapped[str] = mapped_column(Unicode, nullable=False)
    StartTime: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    EndTime: Mapped[Optional[datetime]] = mapped_column(DateTime)
    Status: Mapped[Optional[str]] = mapped_column(Unicode, nullable=True)

    def __repr__(self):
        return f"<Question {self.Token} {self.TopicId} {self.TopicDutyFullname} {self.EmployeeFullname} {self.EmployeeChatId} {self.QuestionText} {self.StartTime} {self.EndTime} {self.Status}>"