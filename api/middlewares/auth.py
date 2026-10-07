# -*- coding: utf-8 -*-
"""
Auth middleware: protect /api/v1/* when admin auth is enabled.
"""

from __future__ import annotations

import logging
from typing import Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.auth import COOKIE_NAME, is_auth_enabled, verify_session_info
from src.identity import CurrentUser, set_current_user

logger = logging.getLogger(__name__)

EXEMPT_PATHS = frozenset({
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/status",
    "/api/health",
    "/api/v1/health",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
})


def _path_exempt(path: str) -> bool:
    """Check if path is exempt from auth."""
    normalized = path.rstrip("/") or "/"
    return normalized in EXEMPT_PATHS


def _bind_user_from_cookie(request: Request) -> bool:
    """Attach request.state.user when the session cookie is valid."""
    cookie_val = request.cookies.get(COOKIE_NAME)
    info = verify_session_info(cookie_val) if cookie_val else None
    if info is None:
        set_current_user(None)
        request.state.user = None
        return False

    user_id = info.get("user_id")
    current = None
    if user_id is not None:
        try:
            from src.user_store import get_user_by_id

            record = get_user_by_id(int(user_id))
        except Exception:
            logger.exception("Failed to load user %s from session", user_id)
            record = None
        if record is not None:
            current = CurrentUser(
                id=int(record.id),
                username=str(record.username),
                role=str(record.role or "user"),
            )
        else:
            set_current_user(None)
            request.state.user = None
            return False
    else:
        current = CurrentUser(id=0, username="admin", role="admin")

    set_current_user(current)
    request.state.user = current
    return True


class AuthMiddleware(BaseHTTPMiddleware):
    """Require valid session for /api/v1/* when auth is enabled."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ):
        set_current_user(None)
        request.state.user = None

        if not is_auth_enabled():
            return await call_next(request)

        path = request.url.path
        if _path_exempt(path):
            _bind_user_from_cookie(request)
            return await call_next(request)

        if not path.startswith("/api/v1/"):
            return await call_next(request)

        if not _bind_user_from_cookie(request):
            return JSONResponse(
                status_code=401,
                content={
                    "error": "unauthorized",
                    "message": "Login required",
                },
            )

        return await call_next(request)


def add_auth_middleware(app):
    """Add auth middleware to protect API routes.

    The middleware is always registered; whether auth is enforced is determined
    at request time by is_auth_enabled() so the decision stays consistent across
    any runtime configuration reload.
    """
    app.add_middleware(AuthMiddleware)
