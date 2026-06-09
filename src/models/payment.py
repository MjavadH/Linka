from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base
from models.enums import PaymentRequestStatus


class PaymentRequest(Base):
    __tablename__ = "payment_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    phone_number: Mapped[str] = mapped_column(String(50))
    payment_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    screenshots_metadata: Mapped[list[dict[str, str]]] = mapped_column(JSONB, default=list)
    status: Mapped[PaymentRequestStatus] = mapped_column(
        Enum(PaymentRequestStatus), default=PaymentRequestStatus.PENDING, index=True
    )
    reviewed_by_admin_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="payment_requests", foreign_keys=[user_id])
