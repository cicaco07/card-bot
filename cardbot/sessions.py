"""Session models and guards shared by Discord UI handlers."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import random

import discord

from poker.game import PokerGame, PokerGameError, PokerStatus
from rummy.game import RummyGame, RummyGameError, RummyStatus
from uno.game import UnoGame, UnoGameError

from .constants import POKER_TOURNAMENT_POINTS
from .state import (
    poker_sessions_by_channel,
    poker_tournament_session_by_code,
    poker_tournament_sessions_by_id,
    rummy_sessions_by_channel,
    rummy_tournament_session_by_code,
    rummy_tournament_sessions_by_id,
    sessions_by_channel,
)
from .text_utils import format_tournament_round_progress, format_tournament_round_summary


@dataclass
class UnoSession:
    channel_id: int
    owner_id: int
    game: UnoGame = field(default_factory=UnoGame)
    table_message_id: int | None = None
    log: list[str] = field(default_factory=list)
    end_game_votes: set[int] = field(default_factory=set)

    def add_log(self, messages: list[str] | str) -> None:
        if isinstance(messages, str):
            messages = [messages]
        # Keep the table calm: show only the latest action, not a growing chat log.
        self.log = messages[-3:]

    @property
    def end_vote_required(self) -> int:
        return (len(self.game.players) // 2) + 1

    @property
    def end_vote_count(self) -> int:
        player_ids = {player.user_id for player in self.game.players}
        self.end_game_votes.intersection_update(player_ids)
        return len(self.end_game_votes)

    def add_end_vote(self, user_id: int) -> tuple[int, int, bool]:
        require_session_player(self, user_id)
        self.end_game_votes.add(user_id)
        votes = self.end_vote_count
        required = self.end_vote_required
        return votes, required, votes >= required


@dataclass
class PokerSession:
    channel_id: int
    owner_id: int
    guild_id: int | None = None
    table_id: str | None = None
    table_code: str | None = None
    table_name: str | None = None
    mode: str = "regular"
    tournament_total_rounds: int | None = 3
    tournament_current_round: int = 0
    tournament_scores: dict[int, int] = field(default_factory=dict)
    tournament_round_summaries: list[str] = field(default_factory=list)
    tournament_round_points: dict[int, dict[int, int]] = field(default_factory=dict)
    tournament_scored_rounds: set[int] = field(default_factory=set)
    tournament_checkpointed_rounds: set[int] = field(default_factory=set)
    tournament_checkpoint_error: str | None = None
    tournament_aborted: bool = False
    game: PokerGame = field(default_factory=PokerGame)
    table_message_id: int | None = None
    log: list[str] = field(default_factory=list)
    end_game_votes: set[int] = field(default_factory=set)
    timer_seconds: int = 45
    turn_timer_task: asyncio.Task | None = field(default=None, repr=False)
    turn_timer_token: int = 0

    def add_log(self, messages: list[str] | str) -> None:
        if isinstance(messages, str):
            messages = [messages]
        self.log = messages[-5:]

    @property
    def end_vote_required(self) -> int:
        return (len(self.game.players) // 2) + 1

    @property
    def end_vote_count(self) -> int:
        player_ids = {player.user_id for player in self.game.players}
        self.end_game_votes.intersection_update(player_ids)
        return len(self.end_game_votes)

    def add_end_vote(self, user_id: int) -> tuple[int, int, bool]:
        require_poker_player(self, user_id)
        self.end_game_votes.add(user_id)
        votes = self.end_vote_count
        required = self.end_vote_required
        return votes, required, votes >= required

    @property
    def is_tournament(self) -> bool:
        return self.mode == "tournament"

    @property
    def tournament_finished(self) -> bool:
        return (
            self.is_tournament
            and self.tournament_total_rounds is not None
            and len(self.tournament_scored_rounds) >= self.tournament_total_rounds
        )

    @property
    def tournament_between_rounds(self) -> bool:
        return (
            self.is_tournament
            and self.game.status == PokerStatus.FINISHED
            and not self.tournament_finished
            and not self.tournament_aborted
        )

    @property
    def runtime_key(self) -> int | str:
        return self.table_id or self.channel_id

    @property
    def tournament_game_type(self) -> str:
        return "poker"

    def start_poker_round(self) -> list[str]:
        if not self.is_tournament:
            return self.game.start()

        self.tournament_current_round += 1
        self.end_game_votes.clear()
        if not self.tournament_scores:
            self.tournament_scores = {player.user_id: 0 for player in self.game.players}
        messages = self.game.start()
        progress = format_tournament_round_progress(self.tournament_current_round, self.tournament_total_rounds)
        return [f"Ronde tournament {progress} dimulai."] + messages

    def start_next_tournament_round(self) -> list[str]:
        if not self.tournament_between_rounds:
            raise PokerGameError("Tournament belum siap masuk ronde berikutnya.")
        if self.table_id and self.tournament_current_round not in self.tournament_checkpointed_rounds:
            raise PokerGameError("Checkpoint ronde belum tersimpan. Tekan Coba Simpan Checkpoint sebelum melanjutkan.")

        previous_players = [(player.user_id, player.name) for player in self.game.players]
        self.game = PokerGame()
        for user_id, name in previous_players:
            self.game.add_player(user_id, name)
        return self.start_poker_round()

    def score_finished_tournament_round(self) -> list[str]:
        if (
            not self.is_tournament
            or self.tournament_aborted
            or self.game.status != PokerStatus.FINISHED
            or self.tournament_current_round in self.tournament_scored_rounds
        ):
            return []

        ranking = list(self.game.winner_ids)
        if self.game.loser_id is not None and self.game.loser_id not in ranking:
            ranking.append(self.game.loser_id)
        ranking.extend(player.user_id for player in self.game.players if player.user_id not in ranking)

        round_points: list[tuple[int, int]] = []
        bomb_bomber_id = self.game.bomb_finish_bomber_id
        bomb_loser_id = self.game.bomb_finish_loser_id
        for place, user_id in enumerate(ranking):
            if bomb_bomber_id is not None and bomb_loser_id is not None:
                if user_id == bomb_bomber_id:
                    points = 40
                elif user_id == bomb_loser_id:
                    points = -40
                else:
                    points = 0
            elif user_id == self.game.loser_id:
                points = POKER_TOURNAMENT_POINTS["loser"]
            elif place == 0:
                points = POKER_TOURNAMENT_POINTS["first"]
            elif place == 1:
                points = POKER_TOURNAMENT_POINTS["second"]
            else:
                points = POKER_TOURNAMENT_POINTS["middle"]
            self.tournament_scores[user_id] = self.tournament_scores.get(user_id, 0) + points
            round_points.append((user_id, points))

        self.tournament_scored_rounds.add(self.tournament_current_round)
        self.tournament_round_points[self.tournament_current_round] = dict(round_points)
        summary = format_tournament_round_summary(self.tournament_current_round, round_points)
        self.tournament_round_summaries.append(summary)
        return [summary]

    def finished_round_payload(self) -> dict[str, object]:
        ranking = list(self.game.winner_ids)
        if self.game.loser_id is not None and self.game.loser_id not in ranking:
            ranking.append(self.game.loser_id)
        ranking.extend(player.user_id for player in self.game.players if player.user_id not in ranking)
        return {
            "summary": self.tournament_round_summaries[-1],
            "round_points": dict(self.tournament_round_points[self.tournament_current_round]),
            "winner_ids": list(self.game.winner_ids),
            "loser_id": self.game.loser_id,
            "ranking": ranking,
            "bomb_finish_bomber_id": self.game.bomb_finish_bomber_id,
            "bomb_finish_loser_id": self.game.bomb_finish_loser_id,
        }


@dataclass
class RummySession:
    channel_id: int
    owner_id: int
    guild_id: int | None = None
    table_id: str | None = None
    table_code: str | None = None
    table_name: str | None = None
    mode: str = "regular"
    tournament_total_rounds: int | None = 3
    tournament_current_round: int = 0
    tournament_scores: dict[int, int] = field(default_factory=dict)
    tournament_round_summaries: list[str] = field(default_factory=list)
    tournament_round_points: dict[int, dict[int, int]] = field(default_factory=dict)
    tournament_scored_rounds: set[int] = field(default_factory=set)
    tournament_checkpointed_rounds: set[int] = field(default_factory=set)
    tournament_checkpoint_error: str | None = None
    tournament_aborted: bool = False
    tournament_next_turn_direction: int = 1
    game: RummyGame = field(default_factory=RummyGame)
    table_message_id: int | None = None
    log: list[str] = field(default_factory=list)
    end_game_votes: set[int] = field(default_factory=set)

    def add_log(self, messages: list[str] | str) -> None:
        if isinstance(messages, str):
            messages = [messages]
        self.log = messages[-5:]

    @property
    def end_vote_required(self) -> int:
        return (len(self.game.players) // 2) + 1

    @property
    def end_vote_count(self) -> int:
        player_ids = {player.user_id for player in self.game.players}
        self.end_game_votes.intersection_update(player_ids)
        return len(self.end_game_votes)

    def add_end_vote(self, user_id: int) -> tuple[int, int, bool]:
        require_rummy_player(self, user_id)
        self.end_game_votes.add(user_id)
        votes = self.end_vote_count
        required = self.end_vote_required
        return votes, required, votes >= required

    @property
    def is_tournament(self) -> bool:
        return self.mode == "tournament"

    @property
    def tournament_finished(self) -> bool:
        return (
            self.is_tournament
            and self.tournament_total_rounds is not None
            and len(self.tournament_scored_rounds) >= self.tournament_total_rounds
        )

    @property
    def tournament_between_rounds(self) -> bool:
        return (
            self.is_tournament
            and self.game.status == RummyStatus.FINISHED
            and not self.tournament_finished
            and not self.tournament_aborted
        )

    @property
    def runtime_key(self) -> int | str:
        return self.table_id or self.channel_id

    @property
    def tournament_game_type(self) -> str:
        return "rummy"

    def start_rummy_round(self) -> list[str]:
        if not self.is_tournament:
            return self.game.start()
        if self.game.status != RummyStatus.WAITING or len(self.game.players) < self.game.min_players:
            return self.game.start()
        round_number = self.tournament_current_round + 1
        self.end_game_votes.clear()
        if not self.tournament_scores:
            self.tournament_scores = {player.user_id: 0 for player in self.game.players}
        if round_number == 1:
            starting_user_id = random.choice(self.game.players).user_id
            turn_direction = 1
        else:
            lowest_score = min(self.tournament_scores.get(player.user_id, 0) for player in self.game.players)
            lowest_score_players = [
                player
                for player in self.game.players
                if self.tournament_scores.get(player.user_id, 0) == lowest_score
            ]
            starting_user_id = random.choice(lowest_score_players).user_id
            turn_direction = self.tournament_next_turn_direction
        messages = self.game.start(starting_user_id=starting_user_id, turn_direction=turn_direction)
        self.tournament_current_round = round_number
        direction = "searah jarum jam" if turn_direction == 1 else "berlawanan arah jarum jam"
        progress = format_tournament_round_progress(self.tournament_current_round, self.tournament_total_rounds)
        return [
            f"Ronde tournament {progress} dimulai.",
            f"Arah giliran ronde: {direction}.",
            *messages,
        ]

    def start_next_tournament_round(self) -> list[str]:
        if not self.tournament_between_rounds:
            raise RummyGameError("Tournament belum siap masuk ronde berikutnya.")
        if self.table_id and self.tournament_current_round not in self.tournament_checkpointed_rounds:
            raise RummyGameError("Checkpoint ronde belum tersimpan. Tekan Coba Simpan Checkpoint sebelum melanjutkan.")
        players = [(player.user_id, player.name) for player in self.game.players]
        self.game = RummyGame()
        for user_id, name in players:
            self.game.add_player(user_id, name)
        return self.start_rummy_round()

    def score_finished_tournament_round(self) -> list[str]:
        if (
            not self.is_tournament
            or self.tournament_aborted
            or self.game.status != RummyStatus.FINISHED
            or self.tournament_current_round in self.tournament_scored_rounds
        ):
            return []
        round_points = [(player.user_id, self.game.scores.get(player.user_id, 0)) for player in self.game.players]
        for user_id, points in round_points:
            self.tournament_scores[user_id] = self.tournament_scores.get(user_id, 0) + points
        self.tournament_next_turn_direction = -1 if self.game.has_flip_penalty else 1
        self.tournament_scored_rounds.add(self.tournament_current_round)
        self.tournament_round_points[self.tournament_current_round] = dict(round_points)
        summary = format_tournament_round_summary(self.tournament_current_round, round_points)
        self.tournament_round_summaries.append(summary)
        return [summary]

    def finished_round_payload(self) -> dict[str, object]:
        return {
            "summary": self.tournament_round_summaries[-1],
            "round_points": dict(self.game.scores),
            "score_breakdowns": self.game.public_state()["score_breakdowns"],
            "closed_user_id": self.game.closed_user_id,
            "closed_card": self.game.closed_card.activity_label if self.game.closed_card else None,
        }


def require_channel_id(interaction: discord.Interaction) -> int:
    if interaction.channel_id is None:
        raise UnoGameError("Command ini harus dipakai di channel server.")
    return interaction.channel_id


def get_session(channel_id: int | None) -> UnoSession:
    if channel_id is None:
        raise UnoGameError("Command ini harus dipakai di channel server.")
    session = sessions_by_channel.get(channel_id)
    if session is None:
        raise UnoGameError("Belum ada meja UNO di channel ini. Gunakan /uno_start untuk membuat panel.")
    return session


def get_poker_session(session_key: int | str | None) -> PokerSession:
    if session_key is None:
        raise PokerGameError("Command ini harus dipakai di channel server.")
    session = (
        poker_tournament_sessions_by_id.get(session_key)
        if isinstance(session_key, str)
        else poker_sessions_by_channel.get(session_key)
    )
    if session is None:
        raise PokerGameError("Belum ada meja remi poker di channel ini. Gunakan /poker-start.")
    return session


def get_rummy_session(session_key: int | str | None) -> RummySession:
    if session_key is None:
        raise RummyGameError("Command ini harus dipakai di channel server.")
    session = (
        rummy_tournament_sessions_by_id.get(session_key)
        if isinstance(session_key, str)
        else rummy_sessions_by_channel.get(session_key)
    )
    if session is None:
        raise RummyGameError("Belum ada meja rummy di channel ini. Gunakan /rummy-start.")
    return session


def find_poker_session(channel_id: int | None, guild_id: int | None, table_code: str | None = None) -> PokerSession:
    if channel_id is None:
        raise PokerGameError("Command ini harus dipakai di channel server.")
    if table_code:
        if guild_id is None:
            raise PokerGameError("Kode meja tournament hanya bisa dipakai di server.")
        session = poker_tournament_session_by_code(guild_id, table_code)
        if session is None:
            raise PokerGameError("Meja Remi Poker tournament dengan kode tersebut belum aktif. Gunakan /tournament-resume.")
        return session
    regular = poker_sessions_by_channel.get(channel_id)
    tournaments = [session for session in poker_tournament_sessions_by_id.values() if session.channel_id == channel_id]
    candidates = ([regular] if regular else []) + tournaments
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        raise PokerGameError("Ada beberapa meja Poker di channel ini. Isi table_code untuk memilih meja tournament.")
    raise PokerGameError("Belum ada meja remi poker di channel ini. Gunakan /poker-start.")


def find_rummy_session(channel_id: int | None, guild_id: int | None, table_code: str | None = None) -> RummySession:
    if channel_id is None:
        raise RummyGameError("Command ini harus dipakai di channel server.")
    if table_code:
        if guild_id is None:
            raise RummyGameError("Kode meja tournament hanya bisa dipakai di server.")
        session = rummy_tournament_session_by_code(guild_id, table_code)
        if session is None:
            raise RummyGameError("Meja Rummy tournament dengan kode tersebut belum aktif. Gunakan /tournament-resume.")
        return session
    regular = rummy_sessions_by_channel.get(channel_id)
    tournaments = [session for session in rummy_tournament_sessions_by_id.values() if session.channel_id == channel_id]
    candidates = ([regular] if regular else []) + tournaments
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        raise RummyGameError("Ada beberapa meja Rummy di channel ini. Isi table_code untuk memilih meja tournament.")
    raise RummyGameError("Belum ada meja rummy di channel ini. Gunakan /rummy-start.")


def require_session_player(session: UnoSession, user_id: int) -> None:
    if session.game.get_player(user_id) is None:
        raise UnoGameError("Hanya pemain yang ikut lobby/game ini yang boleh melakukan aksi tersebut.")


def require_poker_player(session: PokerSession, user_id: int) -> None:
    if session.game.get_player(user_id) is None:
        raise PokerGameError("Hanya pemain yang ikut lobby/game ini yang boleh melakukan aksi tersebut.")


def require_rummy_player(session: RummySession, user_id: int) -> None:
    if session.game.get_player(user_id) is None:
        raise RummyGameError("Hanya pemain yang ikut lobby/game ini yang boleh melakukan aksi tersebut.")


def finalize_poker_round_if_needed(session: PokerSession) -> None:
    score_messages = session.score_finished_tournament_round()
    if score_messages:
        session.log = (score_messages + session.log)[:3]


def finalize_rummy_round_if_needed(session: RummySession) -> None:
    score_messages = session.score_finished_tournament_round()
    if score_messages:
        session.log = (score_messages + session.log)[:3]
