from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest
import discord

from cardbot.sessions import PokerSession, RummySession, find_poker_session
from cardbot.state import (
    register_poker_session,
    unregister_poker_session,
)
from cardbot.tournaments import (
    TournamentPersistenceError,
    TournamentService,
    TournamentTableSnapshot,
    resume_session,
)
from cardbot.ui.poker import PokerFinishedView, PokerTournamentRoundFinishedView
from cardbot.ui.rummy import RummyFinishedView, RummyTournamentRoundFinishedView
from poker.game import PokerStatus
from rummy.game import RummyPlayer, RummyStatus


class FakeTournamentRepository:
    def __init__(self) -> None:
        self.tables: dict[str, TournamentTableSnapshot] = {}
        self.rounds: dict[str, list[dict]] = {}

    async def health_check(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def create_table(self, table: TournamentTableSnapshot) -> bool:
        if any(existing.guild_id == table.guild_id and existing.table_code == table.table_code for existing in self.tables.values()):
            return False
        self.tables[table.table_id] = table
        self.rounds[table.table_id] = []
        return True

    async def replace_lobby_players(self, table: TournamentTableSnapshot) -> None:
        current = self.tables[table.table_id]
        self.tables[table.table_id] = replace(
            current,
            total_rounds=table.total_rounds,
            settings=table.settings,
            players=table.players,
        )

    async def checkpoint_round(
        self,
        table_id: str,
        round_number: int,
        result: dict,
        round_points: dict[int, int],
        finished: bool,
    ) -> bool:
        if len(self.rounds[table_id]) >= round_number:
            return False
        table = self.tables[table_id]
        players = [
            replace(player, cumulative_score=player.cumulative_score + round_points[player.user_id])
            for player in table.players
        ]
        self.rounds[table_id].append(result)
        self.tables[table_id] = replace(
            table,
            completed_rounds=round_number,
            status="finished" if finished else "between_rounds",
            players=players,
            rounds=list(self.rounds[table_id]),
        )
        return True

    async def list_tables(self, guild_id: int, game_type: str | None = None) -> list[TournamentTableSnapshot]:
        return [
            table
            for table in self.tables.values()
            if table.guild_id == guild_id and table.status == "between_rounds" and (game_type is None or table.game_type == game_type)
        ]

    async def get_table(self, guild_id: int, table_code: str) -> TournamentTableSnapshot | None:
        return next(
            (
                table
                for table in self.tables.values()
                if table.guild_id == guild_id and table.table_code == table_code
            ),
            None,
        )

    async def archive_table(self, guild_id: int, table_code: str) -> bool:
        table = await self.get_table(guild_id, table_code)
        if table is None:
            return False
        self.tables[table.table_id] = replace(table, status="archived")
        return True

    async def update_panel(self, table_id: str, channel_id: int, table_message_id: int | None) -> None:
        table = self.tables[table_id]
        self.tables[table_id] = replace(table, channel_id=channel_id, table_message_id=table_message_id)


def test_two_poker_tournaments_in_same_channel_are_selected_by_table_code() -> None:
    async def scenario() -> None:
        repository = FakeTournamentRepository()
        service = TournamentService(repository)
        first = PokerSession(channel_id=10, owner_id=1, mode="tournament")
        second = PokerSession(channel_id=10, owner_id=2, mode="tournament")
        first.game.add_player(1, "Alice")
        second.game.add_player(2, "Bob")
        await service.create_table(first, guild_id=99, game_type="poker", table_name="A")
        await service.create_table(second, guild_id=99, game_type="poker", table_name="B")
        register_poker_session(first)
        register_poker_session(second)
        try:
            assert find_poker_session(10, 99, first.table_code) is first
            assert find_poker_session(10, 99, second.table_code) is second
            with pytest.raises(Exception, match="beberapa meja"):
                find_poker_session(10, 99)
        finally:
            unregister_poker_session(first)
            unregister_poker_session(second)

    asyncio.run(scenario())


def test_poker_checkpoint_is_idempotent_and_resumes_between_rounds() -> None:
    async def scenario() -> None:
        repository = FakeTournamentRepository()
        service = TournamentService(repository)
        session = PokerSession(channel_id=10, owner_id=1, mode="tournament", tournament_total_rounds=3)
        session.game.add_player(1, "Alice")
        session.game.add_player(2, "Bob")
        await service.create_table(session, guild_id=99, game_type="poker")
        session.tournament_current_round = 1
        session.game.status = PokerStatus.FINISHED
        session.game.winner_ids = [1]
        session.game.loser_id = 2
        session.score_finished_tournament_round()

        assert await service.checkpoint_round(session) is True
        assert await service.checkpoint_round(session) is False
        stored = await service.load_table(99, session.table_code or "")
        assert [(player.user_id, player.cumulative_score) for player in stored.players] == [(1, 20), (2, -10)]

        resumed = resume_session(stored)
        assert isinstance(resumed, PokerSession)
        assert resumed.game.status == PokerStatus.FINISHED
        assert resumed.tournament_current_round == 1
        assert resumed.tournament_scores == {1: 20, 2: -10}
        resumed.start_next_tournament_round()
        assert resumed.tournament_current_round == 2

    asyncio.run(scenario())


def test_resume_is_rejected_before_first_completed_round() -> None:
    async def scenario() -> None:
        repository = FakeTournamentRepository()
        service = TournamentService(repository)
        session = RummySession(channel_id=10, owner_id=1, mode="tournament")
        session.game.add_player(1, "Alice")
        session.game.add_player(2, "Bob")
        await service.create_table(session, guild_id=99, game_type="rummy")
        with pytest.raises(TournamentPersistenceError, match="belum memiliki checkpoint"):
            await service.load_table(99, session.table_code or "")

    asyncio.run(scenario())


def test_tournament_creation_is_rejected_when_database_is_unavailable() -> None:
    async def scenario() -> None:
        service = TournamentService()
        session = PokerSession(channel_id=10, owner_id=1, mode="tournament")
        session.game.add_player(1, "Alice")
        with pytest.raises(TournamentPersistenceError, match="DATABASE_URL"):
            await service.create_table(session, guild_id=99, game_type="poker")

    asyncio.run(scenario())


def test_persisted_tournament_cannot_start_next_round_before_checkpoint() -> None:
    session = PokerSession(channel_id=10, owner_id=1, mode="tournament")
    session.table_id = "11111111111111111111111111111111"
    session.tournament_current_round = 1
    session.game.status = PokerStatus.FINISHED
    with pytest.raises(Exception, match="Checkpoint ronde belum tersimpan"):
        session.start_next_tournament_round()


def test_endless_poker_tournament_checkpoints_without_finishing() -> None:
    async def scenario() -> None:
        repository = FakeTournamentRepository()
        service = TournamentService(repository)
        session = PokerSession(channel_id=10, owner_id=1, mode="tournament", tournament_total_rounds=None)
        session.game.add_player(1, "Alice")
        session.game.add_player(2, "Bob")
        await service.create_table(session, guild_id=99, game_type="poker")
        session.tournament_current_round = 1
        session.game.status = PokerStatus.FINISHED
        session.game.winner_ids = [1]
        session.game.loser_id = 2
        session.score_finished_tournament_round()

        assert session.tournament_finished is False
        assert await service.checkpoint_round(session) is True
        table = repository.tables[session.table_id or ""]
        assert table.total_rounds is None
        assert table.completed_rounds == 1
        assert table.status == "between_rounds"

        stored = await service.load_table(99, session.table_code or "")
        resumed = resume_session(stored)
        assert isinstance(resumed, PokerSession)
        assert resumed.tournament_total_rounds is None
        assert resumed.tournament_between_rounds is True

    asyncio.run(scenario())


def test_rummy_checkpoint_restores_scores_without_active_hand() -> None:
    async def scenario() -> None:
        repository = FakeTournamentRepository()
        service = TournamentService(repository)
        session = RummySession(channel_id=10, owner_id=1, mode="tournament")
        session.game.players = [RummyPlayer(1, "Alice"), RummyPlayer(2, "Bob")]
        await service.create_table(session, guild_id=99, game_type="rummy")
        session.tournament_current_round = 1
        session.game.status = RummyStatus.FINISHED
        session.game.scores = {1: 35, 2: -5}
        session.score_finished_tournament_round()

        await service.checkpoint_round(session)
        stored = await service.load_table(99, session.table_code or "")
        resumed = resume_session(stored)
        assert isinstance(resumed, RummySession)
        assert resumed.game.status == RummyStatus.FINISHED
        assert resumed.tournament_scores == {1: 35, 2: -5}
        assert all(not player.hand for player in resumed.game.players)

    asyncio.run(scenario())


def test_tournament_round_and_final_views_expose_checkpoint_retry() -> None:
    views = [
        PokerTournamentRoundFinishedView(10),
        PokerFinishedView(10),
        RummyTournamentRoundFinishedView(10),
        RummyFinishedView(10),
    ]
    for view in views:
        labels = [child.label for child in view.children if isinstance(child, discord.ui.Button)]
        assert labels.count("Coba Simpan Checkpoint") == 1
