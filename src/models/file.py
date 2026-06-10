from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base
from models.enums import FileAccessLevel, StorageType


class File(Base):
    __tablename__ = "files"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    caption_entities: Mapped[list[dict[str, object]] | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    variants = relationship("FileVariant", back_populates="file", cascade="all, delete-orphan")
    deep_links = relationship("DeepLink", back_populates="file", cascade="all, delete-orphan")


class FileVariant(Base):
    __tablename__ = "file_variants"
    __table_args__ = (UniqueConstraint("file_id", "quality", name="uq_file_variants_file_quality"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"), index=True)
    quality: Mapped[str] = mapped_column(String(50))
    storage_type: Mapped[StorageType] = mapped_column(
        Enum(StorageType), default=StorageType.TELEGRAM, index=True
    )
    storage_key: Mapped[str] = mapped_column(Text)
    telegram_file_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    telegram_file_unique_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    archive_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    archive_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    media_type: Mapped[str] = mapped_column(String(50), default="document")
    filename: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    caption_entities: Mapped[list[dict[str, object]] | None] = mapped_column(JSON, nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    access_level: Mapped[FileAccessLevel] = mapped_column(Enum(FileAccessLevel), default=FileAccessLevel.FREE)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    file = relationship("File", back_populates="variants")
    deep_links = relationship("DeepLink", back_populates="variant")


class DeepLink(Base):
    __tablename__ = "deep_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"), index=True)
    file_variant_id: Mapped[int | None] = mapped_column(
        "file_variant_id", ForeignKey("file_variants.id"), nullable=True, index=True
    )
    requires_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    file = relationship("File", back_populates="deep_links")
    variant = relationship("FileVariant", back_populates="deep_links")
