"""Mutable application registries and the configured Discord client."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from .sessions import PokerSession, RummySession, UnoSession


sessions_by_channel: dict[int, "UnoSession"] = {}
poker_sessions_by_channel: dict[int, "PokerSession"] = {}
rummy_sessions_by_channel: dict[int, "RummySession"] = {}
poker_tournament_sessions_by_id: dict[str, "PokerSession"] = {}
rummy_tournament_sessions_by_id: dict[str, "RummySession"] = {}
changelog_seen_versions_by_user: dict[int, str] = {}
published_changelog_versions_by_channel: dict[int, set[str]] = {}
_client: discord.Client | None = None


def set_client(client: discord.Client) -> None:
    global _client
    _client = client


def get_client() -> discord.Client:
    if _client is None:
        raise RuntimeError("Discord client belum dikonfigurasi.")
    return _client


def register_poker_session(session: "PokerSession") -> None:
    if session.table_id:
        poker_tournament_sessions_by_id[session.table_id] = session
    else:
        poker_sessions_by_channel[session.channel_id] = session


def register_rummy_session(session: "RummySession") -> None:
    if session.table_id:
        rummy_tournament_sessions_by_id[session.table_id] = session
    else:
        rummy_sessions_by_channel[session.channel_id] = session


def unregister_poker_session(session: "PokerSession") -> None:
    if session.table_id:
        poker_tournament_sessions_by_id.pop(session.table_id, None)
    elif poker_sessions_by_channel.get(session.channel_id) is session:
        poker_sessions_by_channel.pop(session.channel_id, None)


def unregister_rummy_session(session: "RummySession") -> None:
    if session.table_id:
        rummy_tournament_sessions_by_id.pop(session.table_id, None)
    elif rummy_sessions_by_channel.get(session.channel_id) is session:
        rummy_sessions_by_channel.pop(session.channel_id, None)


def poker_tournament_session_by_code(guild_id: int, table_code: str) -> "PokerSession | None":
    normalized_code = table_code.upper()
    return next(
        (
            session
            for session in poker_tournament_sessions_by_id.values()
            if session.guild_id == guild_id and session.table_code == normalized_code
        ),
        None,
    )


def rummy_tournament_session_by_code(guild_id: int, table_code: str) -> "RummySession | None":
    normalized_code = table_code.upper()
    return next(
        (
            session
            for session in rummy_tournament_sessions_by_id.values()
            if session.guild_id == guild_id and session.table_code == normalized_code
        ),
        None,
    )
