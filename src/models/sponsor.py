from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base


class Sponsor(Base):
    __tablename__ = "sponsors"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    channel_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    invite_url: Mapped[str] = mapped_column(String(1024))
    expiration_type: Mapped[str] = mapped_column(String(20), default="none")
    expiration_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    current_member_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    @property
    def channel_id(self) -> int:
        return self.chat_id

    @property
    def invite_link(self) -> str:
        return self.invite_url

    requirements = relationship("SponsorRequirement", back_populates="sponsor")


class SponsorCampaign(Base):
    __tablename__ = "sponsor_campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    target_member_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)

    requirements = relationship("SponsorRequirement", back_populates="campaign", cascade="all, delete-orphan")


class SponsorRequirement(Base):
    __tablename__ = "sponsor_requirements"
    __table_args__ = (UniqueConstraint("campaign_id", "sponsor_id", name="uq_campaign_sponsor"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("sponsor_campaigns.id", ondelete="CASCADE"))
    sponsor_id: Mapped[int] = mapped_column(ForeignKey("sponsors.id", ondelete="CASCADE"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)

    campaign = relationship("SponsorCampaign", back_populates="requirements")
    sponsor = relationship("Sponsor", back_populates="requirements")
