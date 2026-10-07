# -*- coding: utf-8 -*-
"""Request-scoped current user for multi-user isolation."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Optional

ROLE_ADMIN = "admin"
ROLE_USER = "user"


@dataclass(frozen=True)
class CurrentUser:
    """Authenticated user bound to the current request."""

    id: int
    username: str
    role: str = ROLE_USER

    @property
    def owner_id(self) -> str:
        return str(self.id)

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN


_current_user: ContextVar[Optional[CurrentUser]] = ContextVar("dsa_current_user", default=None)


def get_current_user() -> Optional[CurrentUser]:
    """Return the user bound to this request, if any."""
    return _current_user.get()


def set_current_user(user: Optional[CurrentUser]) -> None:
    """Bind or clear the request-scoped user."""
    _current_user.set(user)


def isolation_owner_id() -> Optional[str]:
    """Owner key used to filter per-user records.

    ``None`` means no isolation (auth off / anonymous / CLI).
    """
    user = get_current_user()
    if user is None:
        return None
    return user.owner_id


def stamp_owner(fields: dict, key: str = "user_id") -> dict:
    """Copy current owner onto a create payload when isolation is active."""
    owner = isolation_owner_id()
    if owner is not None:
        fields[key] = owner
    return fields
