from sqlalchemy import BIGINT
from sqlalchemy import Unicode
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TableNameMixin


class Buffer(Base, TableNameMixin):
    """
    Класс, представляющий сущность буфера в БД.

    Attributes:
        Id (Mapped[int]): Уникальный идентификатор строки.
        DataName (Mapped[int]): Название датасета.
        Data (Mapped[int]): Датасет.

    Methods:
        __repr__(): Returns a string representation of the User object.

    Inherited Attributes:
        Inherits from Base and TableNameMixin classes, which provide additional attributes and functionality.

    Inherited Methods:
        Inherits methods from Base and TableNameMixin classes, which provide additional functionality.

    """
    __tablename__ = 'BufferForBot'

    Id: Mapped[int] = mapped_column(BIGINT, primary_key=True)
    DataName: Mapped[str] = mapped_column(Unicode, nullable=False)
    Data: Mapped[str] = mapped_column(Unicode, nullable=False)

    def __repr__(self):
        return f"<Buffer {self.Id} {self.DataName} {self.Data}>"