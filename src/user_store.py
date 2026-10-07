# -*- coding: utf-8 -*-
"""Multi-user store: bcrypt credentials, watchlists, bootstrap admin.

Users live on DATABASE_URL when it points at Postgres (Compose hostname ``db``),
otherwise on the same SQLite file as analysis data.
"""

from __future__ import annotations

import logging
import os
import re
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, List, Optional

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from src.auth import _validate_password

logger = logging.getLogger(__name__)

UserBase = declarative_base()

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
ROLE_ADMIN = "admin"
ROLE_USER = "user"

_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


class UserRecord(UserBase):
    """Registered application user."""

    __tablename__ = "app_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(16), nullable=False, default=ROLE_USER, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class UserWatchlistRecord(UserBase):
    """Per-user watchlist codes, stored as a comma-separated string."""

    __tablename__ = "user_watchlists"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, unique=True, index=True)
    stock_codes = Column(Text, nullable=False, default="")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", name="uix_user_watchlist_user"),)


def _hash_password(password: str) -> str:
    import bcrypt

    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password_hash(password: str, stored: str) -> bool:
    """Verify a bcrypt hash. Returns False on malformed input."""
    if not password or not stored:
        return False
    try:
        import bcrypt

        return bcrypt.checkpw(password.encode("utf-8"), stored.encode("ascii"))
    except (ValueError, TypeError):
        return False


def validate_username(username: str) -> Optional[str]:
    """Return an error message if the username is invalid."""
    value = (username or "").strip()
    if not value:
        return "用户名不能为空"
    if not USERNAME_RE.match(value):
        return "用户名需为 3-32 位字母、数字、点、下划线或连字符"
    return None


def get_user_database_url() -> str:
    """Resolve the user-store URL: DATABASE_URL, else the analysis SQLite file."""
    url = (os.getenv("DATABASE_URL") or "").strip()
    if url:
        return url
    db_path = os.getenv("DATABASE_PATH", "./data/stock_analysis.db")
    resolved = Path(db_path).expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{resolved}"


def _build_engine(url: str) -> Engine:
    kwargs = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)


def init_user_store(url: Optional[str] = None) -> Engine:
    """Create engine/tables. Safe to call more than once."""
    global _engine, _SessionLocal
    if _engine is not None:
        return _engine
    engine = _build_engine(url or get_user_database_url())
    UserBase.metadata.create_all(engine)
    _engine = engine
    _SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    logger.info("User store initialized: %s", engine.url.render_as_string(hide_password=True))
    return engine


def reset_user_store() -> None:
    """Drop the cached engine (tests)."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


@contextmanager
def user_session() -> Iterator[Session]:
    init_user_store()
    assert _SessionLocal is not None
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_user_by_id(user_id: int) -> Optional[UserRecord]:
    init_user_store()
    assert _SessionLocal is not None
    session = _SessionLocal()
    try:
        return session.get(UserRecord, user_id)
    finally:
        session.close()


def get_user_by_username(username: str) -> Optional[UserRecord]:
    init_user_store()
    assert _SessionLocal is not None
    session = _SessionLocal()
    try:
        return (
            session.query(UserRecord)
            .filter(UserRecord.username == username.strip())
            .one_or_none()
        )
    finally:
        session.close()


def user_count() -> int:
    init_user_store()
    assert _SessionLocal is not None
    session = _SessionLocal()
    try:
        return int(session.query(UserRecord).count())
    finally:
        session.close()


def create_user(username: str, password: str, role: str = ROLE_USER) -> tuple[Optional[UserRecord], Optional[str]]:
    """Create a user. Returns (record, error)."""
    name_err = validate_username(username)
    if name_err:
        return None, name_err
    pwd_err = _validate_password(password)
    if pwd_err:
        return None, pwd_err
    if role not in (ROLE_ADMIN, ROLE_USER):
        return None, "无效角色"

    with user_session() as session:
        existing = (
            session.query(UserRecord)
            .filter(UserRecord.username == username.strip())
            .one_or_none()
        )
        if existing is not None:
            return None, "用户名已存在"
        record = UserRecord(
            username=username.strip(),
            password_hash=_hash_password(password),
            role=role,
        )
        session.add(record)
        session.flush()
        session.refresh(record)
        session.expunge(record)
        return record, None


def authenticate_user(username: str, password: str) -> Optional[UserRecord]:
    """Return the user when username+password match a bcrypt hash."""
    record = get_user_by_username(username)
    if record is None:
        return None
    if not verify_password_hash(password, record.password_hash):
        return None
    return record


def change_user_password(user_id: int, current: str, new: str) -> Optional[str]:
    """Change password for a user. Returns error or None."""
    pwd_err = _validate_password(new)
    if pwd_err:
        return pwd_err
    with user_session() as session:
        record = session.get(UserRecord, user_id)
        if record is None:
            return "用户不存在"
        if not verify_password_hash(current, record.password_hash):
            return "当前密码错误"
        record.password_hash = _hash_password(new)
        record.updated_at = datetime.utcnow()
        return None


def get_watchlist_codes(user_id: int) -> List[str]:
    init_user_store()
    assert _SessionLocal is not None
    session = _SessionLocal()
    try:
        row = (
            session.query(UserWatchlistRecord)
            .filter(UserWatchlistRecord.user_id == user_id)
            .one_or_none()
        )
        if row is None or not row.stock_codes:
            return []
        return [code.strip() for code in row.stock_codes.split(",") if code.strip()]
    finally:
        session.close()


def set_watchlist_codes(user_id: int, codes: List[str]) -> List[str]:
    cleaned = [code.strip() for code in codes if code and code.strip()]
    with user_session() as session:
        row = (
            session.query(UserWatchlistRecord)
            .filter(UserWatchlistRecord.user_id == user_id)
            .one_or_none()
        )
        payload = ",".join(cleaned)
        if row is None:
            session.add(UserWatchlistRecord(user_id=user_id, stock_codes=payload))
        else:
            row.stock_codes = payload
            row.updated_at = datetime.utcnow()
    return cleaned


def registration_enabled() -> bool:
    raw = (os.getenv("AUTH_REGISTRATION_ENABLED") or "true").strip().lower()
    return raw in ("true", "1", "yes", "on")


def bootstrap_admin_from_env() -> Optional[UserRecord]:
    """Create the first admin from ADMIN_USERNAME / ADMIN_PASSWORD if missing."""
    username = (os.getenv("ADMIN_USERNAME") or "").strip()
    password = os.getenv("ADMIN_PASSWORD") or ""
    if not username or not password.strip():
        return None
    existing = get_user_by_username(username)
    if existing is not None:
        return existing
    record, err = create_user(username, password, role=ROLE_ADMIN)
    if err:
        logger.warning("Failed to bootstrap admin user %s: %s", username, err)
        return None
    logger.info("Bootstrapped admin user %s", username)
    return record
