"""Mutable application registries and the configured Discord client."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from .sessions import PokerSession, RummySession, UnoSession


sessions_by_channel: dict[int, "UnoSession"] = {}
poker_sessions_by_channel: dict[int, "PokerSession"] = {}
rummy_sessions_by_channel: dict[int, "RummySession"] = {}
changelog_seen_versions_by_user: dict[int, str] = {}
_client: discord.Client | None = None


def set_client(client: discord.Client) -> None:
    global _client
    _client = client


def get_client() -> discord.Client:
    if _client is None:
        raise RuntimeError("Discord client belum dikonfigurasi.")
    return _client
