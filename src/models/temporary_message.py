from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base
from models.enums import TemporaryMessageStatus


class TemporaryMessage(Base):
    __tablename__ = "temporary_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    message_id: Mapped[int] = mapped_column(Integer)
    delete_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[TemporaryMessageStatus] = mapped_column(
        Enum(TemporaryMessageStatus), default=TemporaryMessageStatus.PENDING, index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def delete_after(self) -> datetime:
        return self.delete_at

    @delete_after.setter
    def delete_after(self, value: datetime) -> None:
        self.delete_at = value
