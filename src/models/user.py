from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    total_downloads: Mapped[int] = mapped_column(Integer, default=0)

    subscriptions = relationship("Subscription", back_populates="user")
    downloads = relationship("Download", back_populates="user")
    payment_requests = relationship("PaymentRequest", back_populates="user")

    def is_premium_at(self, moment: datetime | None = None) -> bool:
        now = moment or datetime.now(UTC)
        return any(subscription.expires_at > now for subscription in self.subscriptions)
