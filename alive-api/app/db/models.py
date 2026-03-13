from typing import Optional
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Text, DateTime, Integer, BigInteger, ForeignKey, Enum, Boolean
from datetime import datetime

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)

    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    auth_provider: Mapped[str] = mapped_column(
        Enum("local", "google", "apple", name="auth_provider_enum"),
        nullable=False,
        default="local",
    )
    provider_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    checkin_period_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=48)
    last_active_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    alarm_sent_for_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_dead: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    contacts = relationship("Contact", back_populates="user", cascade="all, delete-orphan")
    checkins = relationship("Checkin", back_populates="user", cascade="all, delete-orphan")

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
