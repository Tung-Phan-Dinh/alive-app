from typing import Optional
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Text, DateTime, Integer, BigInteger, ForeignKey, Enum, Boolean, UniqueConstraint
from datetime import datetime

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", "auth_provider", name="uq_users_email_provider"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(254), nullable=False)  # Unique per auth_provider
    name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)  # Display name for notifications

    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    auth_provider: Mapped[str] = mapped_column(
        Enum("local", "google", "apple", name="auth_provider_enum"),
        nullable=False,
        default="local",
    )
    provider_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    apple_refresh_token: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    checkin_period_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=48)
    last_active_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    alarm_sent_for_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_dead: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    contacts = relationship("Contact", back_populates="user", cascade="all, delete-orphan")
    checkins = relationship("Checkin", back_populates="user", cascade="all, delete-orphan")
    trigger_events = relationship("TriggerEvent", back_populates="user", cascade="all, delete-orphan")

class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(254), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    death_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="contacts")

class Checkin(Base):
    __tablename__ = "checkins"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    checked_in_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    user = relationship("User", back_populates="checkins")


class TriggerEvent(Base):
    """Tracks each time a user misses their check-in deadline."""
    __tablename__ = "trigger_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    triggered_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    deadline_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    status: Mapped[str] = mapped_column(
        Enum("triggered", "resolved", name="trigger_status_enum"),
        nullable=False,
        default="triggered",
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="trigger_events")
    notifications = relationship("Notification", back_populates="trigger_event", cascade="all, delete-orphan")


class Notification(Base):
    """Tracks each notification sent for a trigger event."""
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trigger_event_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("trigger_events.id", ondelete="CASCADE"), nullable=False)
    contact_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False)

    channel: Mapped[str] = mapped_column(
        Enum("email", "sms", name="notification_channel_enum"),
        nullable=False,
        default="email",
    )

    recipient_address: Mapped[str] = mapped_column(String(254), nullable=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    status: Mapped[str] = mapped_column(
        Enum("pending", "sent", "failed", name="notification_status_enum"),
        nullable=False,
        default="pending",
    )

    error_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    trigger_event = relationship("TriggerEvent", back_populates="notifications")
    contact = relationship("Contact")
