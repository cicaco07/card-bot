"""Pydantic response models for the admin API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AdminUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    global_name: str | None = None
    avatar_url: str | None = None


class TournamentPlayerSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    display_name: str
    seat_order: int
    cumulative_score: int


class TournamentRoundSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    round_number: int
    summary: str
    winner_ids: list[int]
    loser_id: int | None = None
    ranking: list[int]
    round_points: dict[int, int]
    result_json: dict[str, Any]


class TournamentTableSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    table_code: str
    table_name: str | None = None
    guild_id: int
    channel_id: int
    table_message_id: int | None = None
    owner_user_id: int
    owner_display_name: str | None = None
    game_type: str
    status: str
    total_rounds: int
    total_rounds_display: str
    completed_rounds: int
    created_at: datetime
    updated_at: datetime


class TournamentTableDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    table: TournamentTableSummary
    settings: dict[str, Any]
    players: list[TournamentPlayerSummary]
    rounds: list[TournamentRoundSummary]


class PlayerStatSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    display_name: str | None = None
    game_type: str
    tournaments_played: int
    tournaments_won: int
    total_score: int
    updated_at: datetime


class DashboardSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    active_tables: int
    archived_tables: int
    finished_tables: int
    total_rounds_saved: int
    top_player_stats: list[PlayerStatSummary]


class ArchiveResponse(BaseModel):
    archived: bool
    table_id: str
