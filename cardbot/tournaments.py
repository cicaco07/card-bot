"""Persistent tournament checkpoint service shared by Poker and Rummy."""

from __future__ import annotations

from dataclasses import dataclass, field
import secrets
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from .sessions import PokerSession, RummySession


class TournamentPersistenceError(RuntimeError):
    """Raised when a persistent tournament operation cannot be completed."""


@dataclass(frozen=True)
class TournamentPlayerSnapshot:
    user_id: int
    display_name: str
    seat_order: int
    cumulative_score: int = 0


@dataclass(frozen=True)
class TournamentTableSnapshot:
    table_id: str
    table_code: str
    table_name: str | None
    guild_id: int
    channel_id: int
    table_message_id: int | None
    owner_user_id: int
    game_type: str
    status: str
    total_rounds: int | None
    completed_rounds: int
    settings: dict[str, Any] = field(default_factory=dict)
    players: list[TournamentPlayerSnapshot] = field(default_factory=list)
    rounds: list[dict[str, Any]] = field(default_factory=list)


class TournamentRepository(Protocol):
    async def health_check(self) -> None: ...

    async def close(self) -> None: ...

    async def create_table(self, table: TournamentTableSnapshot) -> bool: ...

    async def replace_lobby_players(self, table: TournamentTableSnapshot) -> None: ...

    async def checkpoint_round(
        self,
        table_id: str,
        round_number: int,
        result: dict[str, Any],
        round_points: dict[int, int],
        finished: bool,
    ) -> bool: ...

    async def list_tables(self, guild_id: int, game_type: str | None = None) -> list[TournamentTableSnapshot]: ...

    async def get_table(self, guild_id: int, table_code: str) -> TournamentTableSnapshot | None: ...

    async def archive_table(self, guild_id: int, table_code: str) -> bool: ...

    async def update_panel(self, table_id: str, channel_id: int, table_message_id: int | None) -> None: ...


class TournamentService:
    def __init__(self, repository: TournamentRepository | None = None, unavailable_reason: str | None = None) -> None:
        self.repository = repository
        self.unavailable_reason = unavailable_reason or "DATABASE_URL belum dikonfigurasi."

    @property
    def available(self) -> bool:
        return self.repository is not None

    def _require_repository(self) -> TournamentRepository:
        if self.repository is None:
            raise TournamentPersistenceError(
                "Tournament persistent sedang tidak tersedia. "
                f"{self.unavailable_reason} Mode regular tetap dapat dimainkan."
            )
        return self.repository

    async def create_table(
        self,
        session: PokerSession | RummySession,
        *,
        guild_id: int,
        game_type: str,
        table_name: str | None = None,
    ) -> None:
        repository = self._require_repository()
        session.guild_id = guild_id
        session.table_name = table_name
        try:
            for _attempt in range(5):
                session.table_id = secrets.token_hex(16)
                session.table_code = secrets.token_hex(4).upper()
                if await repository.create_table(_session_snapshot(session, game_type)):
                    return
        except Exception as error:
            raise _database_error(error) from error
        raise TournamentPersistenceError("Gagal membuat kode meja tournament unik. Coba ulangi command.")

    async def sync_lobby(self, session: PokerSession | RummySession) -> None:
        repository = self._require_repository()
        if not session.table_id:
            raise TournamentPersistenceError("Meja tournament belum memiliki identitas persistence.")
        try:
            await repository.replace_lobby_players(_session_snapshot(session, session.tournament_game_type))
        except Exception as error:
            raise _database_error(error) from error

    async def checkpoint_round(self, session: PokerSession | RummySession) -> bool:
        repository = self._require_repository()
        if not session.table_id:
            return False
        payload = session.finished_round_payload()
        try:
            inserted = await repository.checkpoint_round(
                session.table_id,
                session.tournament_current_round,
                payload,
                {int(user_id): int(points) for user_id, points in payload["round_points"].items()},
                session.tournament_finished,
            )
        except Exception as error:
            raise _database_error(error) from error
        session.tournament_checkpointed_rounds.add(session.tournament_current_round)
        session.tournament_checkpoint_error = None
        return inserted

    async def update_panel(self, session: PokerSession | RummySession) -> None:
        if not session.table_id:
            return
        try:
            await self._require_repository().update_panel(session.table_id, session.channel_id, session.table_message_id)
        except Exception as error:
            raise _database_error(error) from error

    async def list_tables(self, guild_id: int, game_type: str | None = None) -> list[TournamentTableSnapshot]:
        try:
            return await self._require_repository().list_tables(guild_id, game_type)
        except Exception as error:
            raise _database_error(error) from error

    async def load_table(self, guild_id: int, table_code: str) -> TournamentTableSnapshot:
        table = await self.get_table(guild_id, table_code)
        if table is None:
            raise TournamentPersistenceError("Meja tournament tidak ditemukan di server ini.")
        if table.status != "between_rounds":
            raise TournamentPersistenceError("Meja tournament ini sudah selesai atau telah diarsipkan.")
        if table.completed_rounds < 1:
            raise TournamentPersistenceError("Tournament belum memiliki checkpoint akhir ronde yang dapat di-resume.")
        return table

    async def get_table(self, guild_id: int, table_code: str) -> TournamentTableSnapshot | None:
        try:
            return await self._require_repository().get_table(guild_id, table_code.upper())
        except Exception as error:
            raise _database_error(error) from error

    async def archive_table(self, guild_id: int, table_code: str) -> None:
        try:
            archived = await self._require_repository().archive_table(guild_id, table_code.upper())
        except Exception as error:
            raise _database_error(error) from error
        if not archived:
            raise TournamentPersistenceError("Meja tournament tidak ditemukan di server ini.")


def _session_snapshot(session: PokerSession | RummySession, game_type: str) -> TournamentTableSnapshot:
    if session.table_id is None or session.table_code is None or session.guild_id is None:
        raise TournamentPersistenceError("Identitas persistence meja tournament belum lengkap.")
    settings: dict[str, Any] = {}
    if game_type == "poker":
        settings["timer_seconds"] = session.timer_seconds
    players = [
        TournamentPlayerSnapshot(
            user_id=player.user_id,
            display_name=player.name,
            seat_order=index,
            cumulative_score=session.tournament_scores.get(player.user_id, 0),
        )
        for index, player in enumerate(session.game.players)
    ]
    return TournamentTableSnapshot(
        table_id=session.table_id,
        table_code=session.table_code,
        table_name=session.table_name,
        guild_id=session.guild_id,
        channel_id=session.channel_id,
        table_message_id=session.table_message_id,
        owner_user_id=session.owner_id,
        game_type=game_type,
        status="finished" if session.tournament_finished else "between_rounds",
        total_rounds=session.tournament_total_rounds,
        completed_rounds=len(session.tournament_checkpointed_rounds),
        settings=settings,
        players=players,
    )


def _database_error(error: Exception) -> TournamentPersistenceError:
    if isinstance(error, TournamentPersistenceError):
        return error
    return TournamentPersistenceError(f"Operasi PostgreSQL tournament gagal: {error}")


async def checkpoint_session_if_needed(session: PokerSession | RummySession) -> None:
    if (
        not session.table_id
        or session.tournament_current_round not in session.tournament_scored_rounds
        or session.tournament_current_round in session.tournament_checkpointed_rounds
    ):
        return
    try:
        await get_tournament_service().checkpoint_round(session)
    except TournamentPersistenceError as error:
        message = str(error)
        session.tournament_checkpoint_error = message
        checkpoint_log = f"Checkpoint ronde gagal: {message}"
        if not session.log or session.log[0] != checkpoint_log:
            session.log = ([checkpoint_log] + session.log)[:5]


async def update_panel_if_persisted(session: PokerSession | RummySession) -> None:
    if not session.table_id:
        return
    try:
        await get_tournament_service().update_panel(session)
    except TournamentPersistenceError as error:
        session.tournament_checkpoint_error = str(error)


def resume_session(table: TournamentTableSnapshot) -> PokerSession | RummySession:
    """Restore a between-rounds session without reconstructing an active hand."""

    if table.game_type == "poker":
        from poker.game import PokerStatus

        from .sessions import PokerSession

        session: PokerSession | RummySession = PokerSession(
            channel_id=table.channel_id,
            owner_id=table.owner_user_id,
            mode="tournament",
            tournament_total_rounds=table.total_rounds,
            timer_seconds=int(table.settings.get("timer_seconds", 45)),
        )
        finished_status = PokerStatus.FINISHED
    elif table.game_type == "rummy":
        from rummy.game import RummyStatus

        from .sessions import RummySession

        session = RummySession(
            channel_id=table.channel_id,
            owner_id=table.owner_user_id,
            mode="tournament",
            tournament_total_rounds=table.total_rounds,
        )
        finished_status = RummyStatus.FINISHED
    else:
        raise TournamentPersistenceError(f"Mode tournament `{table.game_type}` belum didukung.")

    session.guild_id = table.guild_id
    session.table_id = table.table_id
    session.table_code = table.table_code
    session.table_name = table.table_name
    session.table_message_id = table.table_message_id
    session.tournament_current_round = table.completed_rounds
    session.tournament_scored_rounds = set(range(1, table.completed_rounds + 1))
    session.tournament_checkpointed_rounds = set(range(1, table.completed_rounds + 1))
    session.tournament_scores = {player.user_id: player.cumulative_score for player in table.players}
    session.tournament_round_points = {
        index: {int(user_id): int(points) for user_id, points in round_result.get("round_points", {}).items()}
        for index, round_result in enumerate(table.rounds, 1)
    }
    session.tournament_round_summaries = [
        str(round_result.get("summary", f"Ronde {index} selesai."))
        for index, round_result in enumerate(table.rounds, 1)
    ]
    for player in table.players:
        session.game.add_player(player.user_id, player.display_name)
    session.game.status = finished_status
    session.tournament_resume_ready_required = True
    session.tournament_resume_ready_user_ids.clear()
    session.add_log(
        f"Checkpoint meja {table.table_code} dimuat setelah ronde {table.completed_rounds}. "
        "Semua pemain harus menekan Siap Resume sebelum ronde berikutnya dimulai."
    )
    return session


_service = TournamentService()


def configure_tournament_service(
    repository: TournamentRepository | None,
    unavailable_reason: str | None = None,
) -> None:
    global _service
    _service = TournamentService(repository, unavailable_reason)


def get_tournament_service() -> TournamentService:
    return _service
