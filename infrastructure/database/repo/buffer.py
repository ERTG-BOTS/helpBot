from sqlalchemy import select

from infrastructure.database.models.buffer import Buffer
from infrastructure.database.repo.base import BaseRepo


class BufferRepo(BaseRepo):
    async def is_user_working_today(self, fio: str, division: str) -> bool:
        """
        Проверка работает ли пользователь сегодня
        """

        query = select(Buffer.Data).where(Buffer.DataName == f"Working{division}")

        result = await self.session.execute(query)
        buffer_data = result.scalar_one_or_none()

        return fio in buffer_data