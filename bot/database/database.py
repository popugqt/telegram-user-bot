import logging
from typing import TypeVar

from sqlalchemy import create_engine, select
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from bot.settings import BASE_DIR


DATABASE_URL = f"sqlite:///{BASE_DIR / 'database.db'}"

logger = logging.getLogger(__name__)
engine = create_engine(
	DATABASE_URL,
	connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(
	bind=engine,
	expire_on_commit=False,
)


class Base(DeclarativeBase):
	pass


T = TypeVar("T", bound=Base)


class Database:
	def __init__(self) -> None:
		self.session: Session = SessionLocal()

	def __enter__(self) -> "Database":
		return self

	def __exit__(self, *args) -> None:
		self.close()

	def add(self, obj: Base) -> None:
		self.session.add(obj)
		self.session.commit()
		self.session.refresh(obj)

	def delete(self, obj: Base) -> None:
		self.session.delete(obj)
		self.session.commit()

	def get(self, model: type[T], object_id: int) -> T | None:
		return self.session.get(model, object_id)

	def all(self, model: type[T]) -> list[T]:
		return list(self.session.scalars(select(model)).all())

	def first(self, model: type[T], **filters) -> T | None:
		query = select(model)

		for field, value in filters.items():
			query = query.where(getattr(model, field) == value)

		return self.session.scalars(query).first()

	def close(self) -> None:
		self.session.close()


def create_tables() -> None:
	from bot.database import models  # noqa: F401

	Base.metadata.create_all(engine)


__all__ = ["Base", "Database", "SessionLocal", "engine", "create_tables"]
