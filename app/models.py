from datetime import datetime, timezone

from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    bio: Mapped[str | None] = mapped_column(String(500), nullable=True)
    link_github: Mapped[str | None] = mapped_column(String(200), nullable=True)
    link_linkedin: Mapped[str | None] = mapped_column(String(200), nullable=True)
    link_x: Mapped[str | None] = mapped_column(String(200), nullable=True)


class ApiKey(Base):
    __tablename__ = "api_key"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    key_hash: Mapped[str] = mapped_column(String(64), index=True)
    label: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Setup(Base):
    __tablename__ = "setup"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(2000), default="")
    latest_version: Mapped[int] = mapped_column(Integer, default=1)
    downloads: Mapped[int] = mapped_column(Integer, default=0)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)


class SetupVersion(Base):
    __tablename__ = "setup_version"
    __table_args__ = (UniqueConstraint("setup_id", "version", name="uq_setup_version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    setup_id: Mapped[int] = mapped_column(ForeignKey("setup.id"))
    version: Mapped[int] = mapped_column(Integer)
    manifest_json: Mapped[dict] = mapped_column(JSON, default=dict)
    archive_key: Mapped[str] = mapped_column(String(200))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class Follow(Base):
    __tablename__ = "follow"
    __table_args__ = (UniqueConstraint("follower_id", "followee_id", name="uq_follow"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    follower_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    followee_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class PullEvent(Base):
    __tablename__ = "pull_event"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    setup_id: Mapped[int] = mapped_column(ForeignKey("setup.id"))
    version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
