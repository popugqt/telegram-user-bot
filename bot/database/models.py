from sqlalchemy.orm import Mapped, mapped_column

from bot.database.database import Base


class User(Base):
	__tablename__ = "users"

	id: Mapped[int] = mapped_column(primary_key=True)
	workspace_id: Mapped[int]


__all__ = ["User"]
