"""SQLAlchemy async repository for tournament checkpoints."""

from __future__ import annotations

from collections.abc import Mapping
import json
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from .tournaments import TournamentPlayerSnapshot, TournamentTableSnapshot


class PostgresTournamentRepository:
    def __init__(self, database_url: str) -> None:
        self.engine: AsyncEngine = create_async_engine(_asyncpg_url(database_url), pool_pre_ping=True)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def health_check(self) -> None:
        async with self.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    async def close(self) -> None:
        await self.engine.dispose()

    async def create_table(self, table: TournamentTableSnapshot) -> bool:
        query = text(
            """
            INSERT INTO cardbot.tournament_tables (
                id, table_code, table_name, guild_id, channel_id, table_message_id,
                owner_user_id, game_type, total_rounds, completed_rounds, settings_json
            ) VALUES (
                CAST(:id AS uuid), :table_code, :table_name, :guild_id, :channel_id, :table_message_id,
                :owner_user_id, CAST(:game_type AS cardbot.tournament_game_type), :total_rounds, 0,
                CAST(:settings_json AS jsonb)
            )
            ON CONFLICT (guild_id, table_code) DO NOTHING
            RETURNING id
            """
        )
        async with self.sessions.begin() as session:
            result = await session.execute(query, _table_params(table))
            created = result.scalar_one_or_none() is not None
            if created:
                await self._replace_players(session, table)
            return created

    async def replace_lobby_players(self, table: TournamentTableSnapshot) -> None:
        async with self.sessions.begin() as session:
            await session.execute(
                text(
                    """
                    UPDATE cardbot.tournament_tables
                    SET total_rounds = :total_rounds,
                        settings_json = CAST(:settings_json AS jsonb),
                        updated_at = now()
                    WHERE id = CAST(:id AS uuid)
                    """
                ),
                _table_params(table),
            )
            await self._replace_players(session, table)

    async def _replace_players(self, session, table: TournamentTableSnapshot) -> None:
        await session.execute(
            text("DELETE FROM cardbot.tournament_players WHERE table_id = CAST(:table_id AS uuid)"),
            {"table_id": table.table_id},
        )
        query = text(
            """
            INSERT INTO cardbot.tournament_players (
                id, table_id, user_id, display_name, seat_order, cumulative_score
            ) VALUES (
                CAST(:id AS uuid), CAST(:table_id AS uuid), :user_id, :display_name, :seat_order, :cumulative_score
            )
            """
        )
        for player in table.players:
            await session.execute(
                query,
                {
                    "id": str(uuid4()),
                    "table_id": table.table_id,
                    "user_id": player.user_id,
                    "display_name": player.display_name,
                    "seat_order": player.seat_order,
                    "cumulative_score": player.cumulative_score,
                },
            )

    async def checkpoint_round(
        self,
        table_id: str,
        round_number: int,
        result: dict[str, Any],
        round_points: dict[int, int],
        finished: bool,
    ) -> bool:
        async with self.sessions.begin() as session:
            inserted = await session.execute(
                text(
                    """
                    INSERT INTO cardbot.tournament_rounds (id, table_id, round_number, result_json)
                    VALUES (CAST(:id AS uuid), CAST(:table_id AS uuid), :round_number, CAST(:result_json AS jsonb))
                    ON CONFLICT (table_id, round_number) DO NOTHING
                    RETURNING id
                    """
                ),
                {
                    "id": str(uuid4()),
                    "table_id": table_id,
                    "round_number": round_number,
                    "result_json": json.dumps(result),
                },
            )
            if inserted.scalar_one_or_none() is None:
                return False

            for user_id, points in round_points.items():
                await session.execute(
                    text(
                        """
                        UPDATE cardbot.tournament_players
                        SET cumulative_score = cumulative_score + :points, updated_at = now()
                        WHERE table_id = CAST(:table_id AS uuid) AND user_id = :user_id
                        """
                    ),
                    {"table_id": table_id, "user_id": user_id, "points": points},
                )
            await session.execute(
                text(
                    """
                    UPDATE cardbot.tournament_tables
                    SET completed_rounds = :round_number,
                        status = CAST(:status AS cardbot.tournament_table_status),
                        version = version + 1,
                        updated_at = now()
                    WHERE id = CAST(:table_id AS uuid)
                    """
                ),
                {"table_id": table_id, "round_number": round_number, "status": "finished" if finished else "between_rounds"},
            )
            if finished:
                await self._update_finished_stats(session, table_id)
            return True

    async def _update_finished_stats(self, session, table_id: str) -> None:
        table_row = (
            await session.execute(
                text("SELECT guild_id, game_type FROM cardbot.tournament_tables WHERE id = CAST(:table_id AS uuid)"),
                {"table_id": table_id},
            )
        ).mappings().one()
        players = (
            await session.execute(
                text(
                    """
                    SELECT user_id, cumulative_score
                    FROM cardbot.tournament_players
                    WHERE table_id = CAST(:table_id AS uuid)
                    ORDER BY cumulative_score DESC, seat_order ASC
                    """
                ),
                {"table_id": table_id},
            )
        ).mappings().all()
        winning_score = players[0]["cumulative_score"] if players else None
        query = text(
            """
            INSERT INTO cardbot.tournament_player_stats (
                id, guild_id, user_id, game_type, tournaments_played, tournaments_won, total_score
            ) VALUES (
                CAST(:id AS uuid), :guild_id, :user_id, CAST(:game_type AS cardbot.tournament_game_type),
                1, :won, :total_score
            )
            ON CONFLICT (guild_id, user_id, game_type) DO UPDATE
            SET tournaments_played = cardbot.tournament_player_stats.tournaments_played + 1,
                tournaments_won = cardbot.tournament_player_stats.tournaments_won + EXCLUDED.tournaments_won,
                total_score = cardbot.tournament_player_stats.total_score + EXCLUDED.total_score,
                updated_at = now()
            """
        )
        for player in players:
            await session.execute(
                query,
                {
                    "id": str(uuid4()),
                    "guild_id": table_row["guild_id"],
                    "user_id": player["user_id"],
                    "game_type": table_row["game_type"],
                    "won": int(player["cumulative_score"] == winning_score),
                    "total_score": player["cumulative_score"],
                },
            )

    async def list_tables(self, guild_id: int, game_type: str | None = None) -> list[TournamentTableSnapshot]:
        where_game_type = "AND game_type = CAST(:game_type AS cardbot.tournament_game_type)" if game_type else ""
        async with self.sessions() as session:
            rows = (
                await session.execute(
                text(
                    f"""
                    SELECT *
                    FROM cardbot.tournament_tables
                    WHERE guild_id = :guild_id AND status = 'between_rounds' {where_game_type}
                    ORDER BY updated_at DESC
                    """
                ),
                {"guild_id": guild_id, "game_type": game_type},
            )
            ).mappings().all()
        return [_table_snapshot(row) for row in rows]

    async def get_table(self, guild_id: int, table_code: str) -> TournamentTableSnapshot | None:
        async with self.sessions() as session:
            row = (
                await session.execute(
                    text("SELECT * FROM cardbot.tournament_tables WHERE guild_id = :guild_id AND table_code = :table_code"),
                    {"guild_id": guild_id, "table_code": table_code},
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
                    {"table_id": str(row["id"])},
                )
            ).mappings().all()
            rounds = (
                await session.execute(
                    text(
                        """
                        SELECT result_json
                        FROM cardbot.tournament_rounds
                        WHERE table_id = CAST(:table_id AS uuid)
                        ORDER BY round_number
                        """
                    ),
                    {"table_id": str(row["id"])},
                )
            ).scalars().all()
            return _table_snapshot(row, players, list(rounds))

    async def archive_table(self, guild_id: int, table_code: str) -> bool:
        async with self.sessions.begin() as session:
            result = await session.execute(
                text(
                    """
                    UPDATE cardbot.tournament_tables
                    SET status = 'archived', updated_at = now()
                    WHERE guild_id = :guild_id AND table_code = :table_code AND status != 'archived'
                    """
                ),
                {"guild_id": guild_id, "table_code": table_code},
            )
            return bool(result.rowcount)

    async def update_panel(self, table_id: str, channel_id: int, table_message_id: int | None) -> None:
        async with self.sessions.begin() as session:
            await session.execute(
                text(
                    """
                    UPDATE cardbot.tournament_tables
                    SET channel_id = :channel_id, table_message_id = :table_message_id, updated_at = now()
                    WHERE id = CAST(:table_id AS uuid)
                    """
                ),
                {"table_id": table_id, "channel_id": channel_id, "table_message_id": table_message_id},
            )


def _table_params(table: TournamentTableSnapshot) -> dict[str, Any]:
    return {
        "id": table.table_id,
        "table_code": table.table_code,
        "table_name": table.table_name,
        "guild_id": table.guild_id,
        "channel_id": table.channel_id,
        "table_message_id": table.table_message_id,
        "owner_user_id": table.owner_user_id,
        "game_type": table.game_type,
        "total_rounds": table.total_rounds,
        "settings_json": json.dumps(table.settings),
    }


def _asyncpg_url(database_url: str):
    url = make_url(database_url)
    query = dict(url.query)
    sslmode = query.pop("sslmode", None)
    if sslmode and "ssl" not in query:
        query["ssl"] = "require" if sslmode in {"require", "verify-ca", "verify-full"} else sslmode
    return url.set(query=query)


def _table_snapshot(
    row: Mapping[str, Any],
    players: list[Mapping[str, Any]] | None = None,
    rounds: list[dict[str, Any]] | None = None,
) -> TournamentTableSnapshot:
    return TournamentTableSnapshot(
        table_id=str(row["id"]),
        table_code=str(row["table_code"]),
        table_name=row["table_name"],
        guild_id=int(row["guild_id"]),
        channel_id=int(row["channel_id"]),
        table_message_id=int(row["table_message_id"]) if row["table_message_id"] is not None else None,
        owner_user_id=int(row["owner_user_id"]),
        game_type=str(row["game_type"]),
        status=str(row["status"]),
        total_rounds=int(row["total_rounds"]) if row["total_rounds"] is not None else None,
        completed_rounds=int(row["completed_rounds"]),
        settings=dict(row["settings_json"]),
        players=[
            TournamentPlayerSnapshot(
                user_id=int(player["user_id"]),
                display_name=str(player["display_name"]),
                seat_order=int(player["seat_order"]),
                cumulative_score=int(player["cumulative_score"]),
            )
            for player in players or []
        ],
        rounds=rounds or [],
    )
