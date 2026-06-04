"""Database access layer for the admin API."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from .models import (
    DashboardSummary,
    PlayerStatSummary,
    TournamentPlayerSummary,
    TournamentRoundSummary,
    TournamentTableDetail,
    TournamentTableSummary,
)


@dataclass(frozen=True)
class TournamentTableFilters:
    status: str | None = None
    game_type: str | None = None
    search: str | None = None
    limit: int = 50


class AdminDataService(Protocol):
    async def close(self) -> None: ...

    async def health(self) -> dict[str, str]: ...

    async def dashboard_summary(self) -> DashboardSummary: ...

    async def list_tournament_tables(self, filters: TournamentTableFilters) -> list[TournamentTableSummary]: ...

    async def get_tournament_table(self, table_id: str) -> TournamentTableDetail | None: ...

    async def archive_tournament_table(self, table_id: str) -> bool: ...

    async def list_player_stats(self, game_type: str | None = None, limit: int = 50) -> list[PlayerStatSummary]: ...


class SqlAdminDataService:
    def __init__(self, database_url: str) -> None:
        self.engine: AsyncEngine = create_async_engine(_asyncpg_url(database_url), pool_pre_ping=True)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def close(self) -> None:
        await self.engine.dispose()

    async def health(self) -> dict[str, str]:
        async with self.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return {"status": "ok"}

    async def dashboard_summary(self) -> DashboardSummary:
        async with self.sessions() as session:
            status_rows = (
                await session.execute(
                    text(
                        """
                        SELECT status::text AS status, COUNT(*) AS total
                        FROM cardbot.tournament_tables
                        GROUP BY status
                        """
                    )
                )
            ).mappings().all()
            rounds_saved = (
                await session.execute(text("SELECT COALESCE(SUM(completed_rounds), 0) FROM cardbot.tournament_tables"))
            ).scalar_one()
            player_rows = (
                await session.execute(
                    text(
                        """
                        SELECT stats.user_id,
                               latest_player.display_name,
                               stats.game_type::text AS game_type,
                               stats.tournaments_played,
                               stats.tournaments_won,
                               stats.total_score,
                               stats.updated_at
                        FROM cardbot.tournament_player_stats AS stats
                        LEFT JOIN LATERAL (
                            SELECT players.display_name
                            FROM cardbot.tournament_players AS players
                            INNER JOIN cardbot.tournament_tables AS tables
                                ON tables.id = players.table_id
                            WHERE players.user_id = stats.user_id
                            ORDER BY
                                CASE WHEN tables.guild_id = stats.guild_id THEN 0 ELSE 1 END,
                                tables.updated_at DESC,
                                players.updated_at DESC,
                                players.seat_order ASC
                            LIMIT 1
                        ) AS latest_player ON TRUE
                        ORDER BY total_score DESC, tournaments_won DESC, tournaments_played DESC
                        LIMIT 10
                        """
                    )
                )
            ).mappings().all()

        totals = {str(row["status"]): int(row["total"]) for row in status_rows}
        return DashboardSummary(
            active_tables=totals.get("between_rounds", 0),
            archived_tables=totals.get("archived", 0),
            finished_tables=totals.get("finished", 0),
            total_rounds_saved=int(rounds_saved or 0),
            top_player_stats=[_player_stat_from_row(row) for row in player_rows],
        )

    async def list_tournament_tables(self, filters: TournamentTableFilters) -> list[TournamentTableSummary]:
        clauses = ["1=1"]
        params: dict[str, Any] = {"limit": max(1, min(filters.limit, 200))}
        if filters.status:
            clauses.append("status = CAST(:status AS cardbot.tournament_table_status)")
            params["status"] = filters.status
        if filters.game_type:
            clauses.append("game_type = CAST(:game_type AS cardbot.tournament_game_type)")
            params["game_type"] = filters.game_type
        if filters.search:
            clauses.append("(table_code ILIKE :search OR COALESCE(table_name, '') ILIKE :search)")
            params["search"] = f"%{filters.search.strip()}%"

        query = text(
            f"""
            SELECT tables.id,
                   tables.table_code,
                   tables.table_name,
                   tables.guild_id,
                   tables.channel_id,
                   tables.table_message_id,
                   tables.owner_user_id,
                   owner_player.display_name AS owner_display_name,
                   tables.game_type::text AS game_type,
                   tables.status::text AS status,
                   tables.total_rounds,
                   tables.completed_rounds,
                   tables.created_at,
                   tables.updated_at
            FROM cardbot.tournament_tables AS tables
            LEFT JOIN LATERAL (
                SELECT players.display_name
                FROM cardbot.tournament_players AS players
                WHERE players.table_id = tables.id
                  AND players.user_id = tables.owner_user_id
                LIMIT 1
            ) AS owner_player ON TRUE
            WHERE {' AND '.join(clauses)}
            ORDER BY tables.updated_at DESC
            LIMIT :limit
            """
        )
        async with self.sessions() as session:
            rows = (await session.execute(query, params)).mappings().all()
        return [_table_summary_from_row(row) for row in rows]

    async def get_tournament_table(self, table_id: str) -> TournamentTableDetail | None:
        async with self.sessions() as session:
            row = (
                await session.execute(
                    text(
                        """
                        SELECT tables.id,
                               tables.table_code,
                               tables.table_name,
                               tables.guild_id,
                               tables.channel_id,
                               tables.table_message_id,
                               tables.owner_user_id,
                               owner_player.display_name AS owner_display_name,
                               tables.game_type::text AS game_type,
                               tables.status::text AS status,
                               tables.total_rounds,
                               tables.completed_rounds,
                               tables.settings_json,
                               tables.created_at,
                               tables.updated_at
                        FROM cardbot.tournament_tables AS tables
                        LEFT JOIN LATERAL (
                            SELECT players.display_name
                            FROM cardbot.tournament_players AS players
                            WHERE players.table_id = tables.id
                              AND players.user_id = tables.owner_user_id
                            LIMIT 1
                        ) AS owner_player ON TRUE
                        WHERE tables.id = CAST(:table_id AS uuid)
                        """
                    ),
                    {"table_id": table_id},
                )
            ).mappings().one_or_none()
            if row is None:
                return None
            players = (
                await session.execute(
                    text(
                        """
                        SELECT user_id, display_name, seat_order, cumulative_score
                        FROM cardbot.tournament_players
                        WHERE table_id = CAST(:table_id AS uuid)
                        ORDER BY seat_order
                        """
                    ),
                    {"table_id": table_id},
                )
            ).mappings().all()
            rounds = (
                await session.execute(
                    text(
                        """
                        SELECT round_number, result_json
                        FROM cardbot.tournament_rounds
                        WHERE table_id = CAST(:table_id AS uuid)
                        ORDER BY round_number DESC
                        """
                    ),
                    {"table_id": table_id},
                )
            ).mappings().all()
        return TournamentTableDetail(
            table=_table_summary_from_row(row),
            settings=dict(row["settings_json"] or {}),
            players=[TournamentPlayerSummary(**_player_summary_payload(player)) for player in players],
            rounds=[_round_summary_from_row(round_row) for round_row in rounds],
        )

    async def archive_tournament_table(self, table_id: str) -> bool:
        async with self.sessions.begin() as session:
            result = await session.execute(
                text(
                    """
                    UPDATE cardbot.tournament_tables
                    SET status = 'archived', updated_at = now()
                    WHERE id = CAST(:table_id AS uuid) AND status != 'archived'
                    """
                ),
                {"table_id": table_id},
            )
        return bool(result.rowcount)

    async def list_player_stats(self, game_type: str | None = None, limit: int = 50) -> list[PlayerStatSummary]:
        params: dict[str, Any] = {"limit": max(1, min(limit, 200))}
        clause = ""
        if game_type:
            clause = "WHERE game_type = CAST(:game_type AS cardbot.tournament_game_type)"
            params["game_type"] = game_type
        query = text(
            f"""
            SELECT stats.user_id,
                   latest_player.display_name,
                   stats.game_type::text AS game_type,
                   stats.tournaments_played,
                   stats.tournaments_won,
                   stats.total_score,
                   stats.updated_at
            FROM cardbot.tournament_player_stats AS stats
            LEFT JOIN LATERAL (
                SELECT players.display_name
                FROM cardbot.tournament_players AS players
                INNER JOIN cardbot.tournament_tables AS tables
                    ON tables.id = players.table_id
                WHERE players.user_id = stats.user_id
                ORDER BY
                    CASE WHEN tables.guild_id = stats.guild_id THEN 0 ELSE 1 END,
                    tables.updated_at DESC,
                    players.updated_at DESC,
                    players.seat_order ASC
                LIMIT 1
            ) AS latest_player ON TRUE
            {clause}
            ORDER BY stats.total_score DESC, stats.tournaments_won DESC, stats.tournaments_played DESC
            LIMIT :limit
            """
        )
        async with self.sessions() as session:
            rows = (await session.execute(query, params)).mappings().all()
        return [_player_stat_from_row(row) for row in rows]


def _asyncpg_url(database_url: str):
    url = database_url
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    parsed = make_url(url)
    query = dict(parsed.query)
    sslmode = query.pop("sslmode", None)
    if sslmode and "ssl" not in query:
        query["ssl"] = "require" if sslmode in {"require", "verify-ca", "verify-full"} else sslmode
    return parsed.set(query=query)


def _total_rounds_payload(total_rounds: int) -> tuple[int, str]:
    if int(total_rounds) == 0:
        return 0, "endless"
    total = int(total_rounds)
    return total, f"{total} game"


def _table_summary_from_row(row: Mapping[str, Any]) -> TournamentTableSummary:
    total_rounds, total_rounds_display = _total_rounds_payload(int(row["total_rounds"]))
    return TournamentTableSummary(
        id=str(row["id"]),
        table_code=str(row["table_code"]),
        table_name=row["table_name"],
        guild_id=int(row["guild_id"]),
        channel_id=int(row["channel_id"]),
        table_message_id=int(row["table_message_id"]) if row["table_message_id"] is not None else None,
        owner_user_id=int(row["owner_user_id"]),
        owner_display_name=str(row["owner_display_name"]) if row.get("owner_display_name") else None,
        game_type=str(row["game_type"]),
        status=str(row["status"]),
        total_rounds=total_rounds,
        total_rounds_display=total_rounds_display,
        completed_rounds=int(row["completed_rounds"]),
        created_at=_datetime_value(row["created_at"]),
        updated_at=_datetime_value(row["updated_at"]),
    )


def _player_summary_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "user_id": int(row["user_id"]),
        "display_name": str(row["display_name"]),
        "seat_order": int(row["seat_order"]),
        "cumulative_score": int(row["cumulative_score"]),
    }


def _round_summary_from_row(row: Mapping[str, Any]) -> TournamentRoundSummary:
    result_json = dict(row["result_json"] or {})
    round_points = {int(user_id): int(points) for user_id, points in dict(result_json.get("round_points", {})).items()}
    return TournamentRoundSummary(
        round_number=int(row["round_number"]),
        summary=str(result_json.get("summary", f"Ronde {row['round_number']} selesai.")),
        winner_ids=[int(user_id) for user_id in result_json.get("winner_ids", [])],
        loser_id=int(result_json["loser_id"]) if result_json.get("loser_id") is not None else None,
        ranking=[int(user_id) for user_id in result_json.get("ranking", [])],
        round_points=round_points,
        result_json=result_json,
    )


def _player_stat_from_row(row: Mapping[str, Any]) -> PlayerStatSummary:
    return PlayerStatSummary(
        user_id=int(row["user_id"]),
        display_name=str(row["display_name"]) if row.get("display_name") else None,
        game_type=str(row["game_type"]),
        tournaments_played=int(row["tournaments_played"]),
        tournaments_won=int(row["tournaments_won"]),
        total_score=int(row["total_score"]),
        updated_at=_datetime_value(row["updated_at"]),
    )


def _datetime_value(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))
