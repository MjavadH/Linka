from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_created_id", "created_at", "id"),
        Index("ix_audit_logs_action_created", "action", "created_at"),
        Index("ix_audit_logs_admin_created", "admin_user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    admin_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    admin_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    admin_full_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    target_type: Mapped[str] = mapped_column(String(100), index=True)
    target_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
