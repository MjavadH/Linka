from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base
from models.enums import BroadcastResultStatus, BroadcastStatus, BroadcastTargetType


class BroadcastJob(Base):
    __tablename__ = "broadcast_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[BroadcastStatus] = mapped_column(Enum(BroadcastStatus), default=BroadcastStatus.DRAFT, index=True)
    target_type: Mapped[BroadcastTargetType] = mapped_column(Enum(BroadcastTargetType), index=True)
    payload: Mapped[dict[str, str | int | bool | None]] = mapped_column(JSONB)
    admin_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    total_recipients: Mapped[int] = mapped_column(Integer, default=0)
    delivered_count: Mapped[int] = mapped_column(Integer, default=0)
    blocked_count: Mapped[int] = mapped_column(Integer, default=0)
    delivery_error_count: Mapped[int] = mapped_column(Integer, default=0)
    other_failure_count: Mapped[int] = mapped_column(Integer, default=0)
    progress_message_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    progress_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    results = relationship("BroadcastResult", back_populates="job", cascade="all, delete-orphan")

    @property
    def failed_count(self) -> int:
        return self.blocked_count + self.delivery_error_count + self.other_failure_count


class BroadcastResult(Base):
    __tablename__ = "broadcast_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("broadcast_jobs.id", ondelete="CASCADE"), index=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    status: Mapped[BroadcastResultStatus] = mapped_column(
        Enum(BroadcastResultStatus), default=BroadcastResultStatus.PENDING, index=True
    )
    message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    job = relationship("BroadcastJob", back_populates="results")


# Backward-compatible aliases for older imports. New code should use BroadcastJob/BroadcastResult.
Broadcast = BroadcastJob
BroadcastRecipient = BroadcastResult
