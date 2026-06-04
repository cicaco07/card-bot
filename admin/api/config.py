"""Configuration helpers for the admin API."""

from __future__ import annotations

from dataclasses import dataclass
import os


def _csv_ints(value: str) -> set[int]:
    return {int(item.strip()) for item in value.split(",") if item.strip()}


@dataclass(frozen=True)
class AdminSettings:
    database_url: str
    frontend_url: str = "http://localhost:5173"
    frontend_origin: str = "http://localhost:5173"
    session_secret: str = "dev-admin-session-secret"
    discord_client_id: str | None = None
    discord_client_secret: str | None = None
    admin_discord_user_ids: set[int] = frozenset()

    @property
    def discord_oauth_enabled(self) -> bool:
        return bool(self.discord_client_id and self.discord_client_secret)

    @classmethod
    def from_env(cls) -> "AdminSettings":
        database_url = os.getenv("DATABASE_URL", "").strip()
        if not database_url:
            raise RuntimeError("DATABASE_URL belum diisi. Admin API membutuhkan koneksi PostgreSQL yang sama dengan bot.")
        user_ids = _csv_ints(os.getenv("ADMIN_DISCORD_USER_IDS", ""))
        return cls(
            database_url=database_url,
            frontend_url=os.getenv("ADMIN_FRONTEND_URL", "http://localhost:5173").strip() or "http://localhost:5173",
            frontend_origin=os.getenv("ADMIN_FRONTEND_ORIGIN", "http://localhost:5173").strip() or "http://localhost:5173",
            session_secret=os.getenv("ADMIN_SESSION_SECRET", "dev-admin-session-secret").strip() or "dev-admin-session-secret",
            discord_client_id=os.getenv("DISCORD_CLIENT_ID", "").strip() or None,
            discord_client_secret=os.getenv("DISCORD_CLIENT_SECRET", "").strip() or None,
            admin_discord_user_ids=user_ids,
        )
