"""Discord OAuth helpers and auth dependencies for the admin API."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from authlib.integrations.starlette_client import OAuth
from fastapi import Depends, HTTPException, Request, status

from .config import AdminSettings
from .models import AdminUser


def build_oauth(settings: AdminSettings) -> OAuth:
    oauth = OAuth()
    if settings.discord_oauth_enabled:
        oauth.register(
            name="discord",
            client_id=settings.discord_client_id,
            client_secret=settings.discord_client_secret,
            access_token_url="https://discord.com/api/oauth2/token",
            authorize_url="https://discord.com/api/oauth2/authorize",
            api_base_url="https://discord.com/api/",
            client_kwargs={"scope": "identify"},
        )
    return oauth


def avatar_url(user_id: int, avatar_hash: str | None) -> str | None:
    if not avatar_hash:
        return None
    return f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.png"


def get_settings(request: Request) -> AdminSettings:
    return request.app.state.admin_settings  # type: ignore[return-value]


def get_oauth(request: Request) -> OAuth:
    return request.app.state.admin_oauth  # type: ignore[return-value]


async def get_session_user(request: Request) -> AdminUser:
    payload = request.session.get("admin_user")
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login admin diperlukan.")
    return AdminUser(**payload)


async def require_admin_user(
    user: AdminUser = Depends(get_session_user),
    settings: AdminSettings = Depends(get_settings),
) -> AdminUser:
    if not settings.admin_discord_user_ids:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ADMIN_DISCORD_USER_IDS belum dikonfigurasi.",
        )
    if user.id not in settings.admin_discord_user_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User Discord ini bukan admin web.")
    return user


def discord_callback_redirect(settings: AdminSettings) -> str:
    return f"{settings.frontend_url.rstrip('/')}/"


def serialize_discord_user(payload: dict[str, Any]) -> AdminUser:
    return AdminUser(
        id=int(payload["id"]),
        username=str(payload["username"]),
        global_name=payload.get("global_name"),
        avatar_url=avatar_url(int(payload["id"]), payload.get("avatar")),
    )


def require_discord_oauth(settings: AdminSettings) -> None:
    if settings.discord_oauth_enabled:
        return
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Discord OAuth belum dikonfigurasi. Isi DISCORD_CLIENT_ID dan DISCORD_CLIENT_SECRET.",
    )
