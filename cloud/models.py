"""Business registry and bounded monitoring projection; UTC milliseconds."""
import hashlib
import secrets
import time

from sqlalchemy import BigInteger, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now_ms():
    return int(time.time() * 1000)


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 600_000)
    return salt + ':' + digest.hex()


def verify_password(password, stored):
    return secrets.compare_digest(password_hash(password, stored.split(':')[0]), stored)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    password: Mapped[str] = mapped_column(String)


class LoginSession(Base):
    __tablename__ = 'login_sessions'
    token_hash: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    expires_ms: Mapped[int] = mapped_column(BigInteger)


class Site(Base):
    __tablename__ = 'sites'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    edge_id: Mapped[str] = mapped_column(String, unique=True)
    timezone: Mapped[str] = mapped_column(String, default='Europe/Bucharest')
    component: Mapped[str] = mapped_column(String, default='growatt0')
    origin: Mapped[str] = mapped_column(String, default='equipment')
    connection: Mapped[str] = mapped_column(String, default='awaiting_gateway')
    last_contact_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class Membership(Base):
    __tablename__ = 'memberships'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), primary_key=True)
    site_id: Mapped[str] = mapped_column(ForeignKey('sites.id'), primary_key=True)
    role: Mapped[str] = mapped_column(String, default='owner')


class Sample(Base):
    __tablename__ = 'cloud_samples'
    __table_args__ = (UniqueConstraint('site_id', 'observed_ms'),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    site_id: Mapped[str] = mapped_column(ForeignKey('sites.id'), index=True)
    observed_ms: Mapped[int] = mapped_column(BigInteger, index=True)
    received_ms: Mapped[int] = mapped_column(BigInteger)
    values: Mapped[dict] = mapped_column(JSON)


class Audit(Base):
    __tablename__ = 'audit_events'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: secrets.token_hex(16))
    at_ms: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    user_id: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    site_id: Mapped[str | None] = mapped_column(String, nullable=True)
