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
from models.enums import ContentType, FileAccessLevel, StorageType


class File(Base):
    __tablename__ = "files"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    caption_entities: Mapped[list[dict[str, object]] | None] = mapped_column(JSON, nullable=True)
    content_type: Mapped[ContentType] = mapped_column(
        Enum(ContentType), default=ContentType.MOVIE, server_default=ContentType.MOVIE.name, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    variants = relationship("FileVariant", back_populates="file", cascade="all, delete-orphan")
    episode = relationship("Episode", back_populates="file", uselist=False)
    deep_links = relationship("DeepLink", back_populates="file", cascade="all, delete-orphan")


class FileVariant(Base):
    __tablename__ = "file_variants"
    __table_args__ = (UniqueConstraint("file_id", "quality", name="uq_file_variants_file_quality"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"), index=True)
    episode_id: Mapped[int | None] = mapped_column(ForeignKey("episodes.id", ondelete="CASCADE"), nullable=True, index=True)
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
    episode = relationship("Episode", back_populates="variants")
    deep_links = relationship("DeepLink", back_populates="variant")


class Series(Base):
    __tablename__ = "series"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    episodes = relationship("Episode", back_populates="series", cascade="all, delete-orphan")


class Episode(Base):
    __tablename__ = "episodes"
    __table_args__ = (UniqueConstraint("series_id", "number", name="uq_episodes_series_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    series_id: Mapped[int] = mapped_column(ForeignKey("series.id", ondelete="CASCADE"), index=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"), unique=True, index=True)
    number: Mapped[str] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    series = relationship("Series", back_populates="episodes")
    file = relationship("File", back_populates="episode")
    variants = relationship("FileVariant", back_populates="episode")


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
