from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import os

import discord
from discord import app_commands
from dotenv import load_dotenv

from poker.assets import render_play_image, render_poker_hand_image
from poker.game import PokerGame, PokerGameError, PokerStatus
from uno.card_assets import render_card_image, render_hand_image
from uno.game import COLOR_LABELS, GameStatus, UnoGame, UnoGameError


load_dotenv()


intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)
sessions_by_channel: dict[int, "UnoSession"] = {}
poker_sessions_by_channel: dict[int, "PokerSession"] = {}
commands_synced = False


COLOR_CHOICES = [
    app_commands.Choice(name="Merah", value="red"),
    app_commands.Choice(name="Kuning", value="yellow"),
    app_commands.Choice(name="Hijau", value="green"),
    app_commands.Choice(name="Biru", value="blue"),
]

POKER_MODE_CHOICES = [
    app_commands.Choice(name="Regular", value="regular"),
    app_commands.Choice(name="Tournament", value="tournament"),
]

POKER_TOURNAMENT_POINTS = {
    "first": 20,
    "second": 10,
    "middle": 0,
    "loser": -10,
}


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
    mode: str = "regular"
    tournament_total_rounds: int = 3
    tournament_current_round: int = 0
    tournament_scores: dict[int, int] = field(default_factory=dict)
    tournament_round_summaries: list[str] = field(default_factory=list)
    tournament_scored_rounds: set[int] = field(default_factory=set)
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
        return self.is_tournament and len(self.tournament_scored_rounds) >= self.tournament_total_rounds

    @property
    def tournament_between_rounds(self) -> bool:
        return (
            self.is_tournament
            and self.game.status == PokerStatus.FINISHED
            and not self.tournament_finished
            and not self.tournament_aborted
        )

    def start_poker_round(self) -> list[str]:
        if not self.is_tournament:
            return self.game.start()

        self.tournament_current_round += 1
        self.end_game_votes.clear()
        if not self.tournament_scores:
            self.tournament_scores = {player.user_id: 0 for player in self.game.players}
        messages = self.game.start()
        return [f"Ronde tournament {self.tournament_current_round}/{self.tournament_total_rounds} dimulai."] + messages

    def start_next_tournament_round(self) -> list[str]:
        if not self.tournament_between_rounds:
            raise PokerGameError("Tournament belum siap masuk ronde berikutnya.")

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
                    points = 4
                elif user_id == bomb_loser_id:
                    points = -4
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
        summary = format_tournament_round_summary(self.tournament_current_round, round_points)
        self.tournament_round_summaries.append(summary)
        return [summary]


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


def get_poker_session(channel_id: int | None) -> PokerSession:
    if channel_id is None:
        raise PokerGameError("Command ini harus dipakai di channel server.")
    session = poker_sessions_by_channel.get(channel_id)
    if session is None:
        raise PokerGameError("Belum ada meja remi poker di channel ini. Gunakan /poker-start.")
    return session


def require_session_player(session: UnoSession, user_id: int) -> None:
    if session.game.get_player(user_id) is None:
        raise UnoGameError("Hanya pemain yang ikut lobby/game ini yang boleh melakukan aksi tersebut.")


def require_poker_player(session: PokerSession, user_id: int) -> None:
    if session.game.get_player(user_id) is None:
        raise PokerGameError("Hanya pemain yang ikut lobby/game ini yang boleh melakukan aksi tersebut.")


def mention(user_id: int) -> str:
    return f"<@{user_id}>"


def format_tournament_round_summary(round_number: int, round_points: list[tuple[int, int]]) -> str:
    points_text = ", ".join(f"{mention(user_id)} {points:+d}" for user_id, points in round_points)
    return f"Skor ronde {round_number}: {points_text}."


def tournament_scoreboard_text(session: PokerSession) -> str:
    if not session.is_tournament:
        return ""
    if not session.tournament_scores:
        return "Skor tournament: belum ada ronde selesai."

    sorted_scores = sorted(
        session.tournament_scores.items(),
        key=lambda item: (item[1], -item[0]),
        reverse=True,
    )
    rows = [f"- {mention(user_id)}: **{score} point**" for user_id, score in sorted_scores]
    return "Skor tournament:\n" + "\n".join(rows)


def finalize_poker_round_if_needed(session: PokerSession) -> None:
    score_messages = session.score_finished_tournament_round()
    if score_messages:
        session.log = (score_messages + session.log)[:3]


def lobby_text(session: UnoSession) -> str:
    players = "\n".join(f"- {mention(player.user_id)}" for player in session.game.players)
    if not players:
        players = "Belum ada pemain."
    return (
        "**UNO Table: Lobby**\n"
        "Tekan tombol di bawah untuk ikut bermain. Setelah minimal 2 pemain masuk, tekan **Mulai Game**.\n\n"
        f"Owner: {mention(session.owner_id)}\n"
        f"Pemain ({len(session.game.players)}/{session.game.max_players}):\n{players}"
    )


def public_state_text(session: UnoSession) -> str:
    game = session.game
    state = game.public_state()
    hand_counts = "\n".join(
        f"- {mention(user_id)}: {count} kartu"
        for user_id, _name, count in state["hand_counts"]
    )
    uno_pending = "\n".join(
        f"- {mention(user_id)} wajib tekan **UNO!**. Pemain lain bisa menekan **Challenge UNO**."
        for user_id, _name in state["uno_pending"]
    )
    if not uno_pending:
        uno_pending = "- Tidak ada."
    action_text = "\n".join(f"- {message}" for message in session.log[:2]) or "- Belum ada aksi."
    vote_text = f"{session.end_vote_count}/{session.end_vote_required} setuju"
    return (
        "**UNO Table: Game Berjalan**\n"
        "Kartu aktif ada pada gambar di bawah.\n"
        f"Warna aktif: **{state['current_color']}**\n"
        f"Gilirannya: {mention(state['current_player_id'])}\n"
        f"Arah: {state['direction']}\n"
        f"Sisa deck: {state['deck_count']} kartu\n\n"
        f"Jumlah kartu pemain:\n{hand_counts}\n\n"
        f"Status UNO:\n{uno_pending}\n\n"
        f"Vote akhiri game: **{vote_text}**\n\n"
        f"Aksi terakhir:\n{action_text}"
    )


def finished_text(session: UnoSession) -> str:
    log_text = "\n".join(f"- {message}" for message in session.log[-8:]) or "- Game selesai."
    return f"**UNO Table: Selesai**\n\nLog akhir:\n{log_text}\n\nTekan **Buat Lobby Baru** untuk main lagi."


def table_text(session: UnoSession) -> str:
    if session.game.status == GameStatus.WAITING:
        return lobby_text(session)
    if session.game.status == GameStatus.FINISHED:
        return finished_text(session)
    return public_state_text(session)


def table_view(session: UnoSession) -> discord.ui.View:
    if session.game.status == GameStatus.WAITING:
        return LobbyView(session.channel_id)
    if session.game.status == GameStatus.FINISHED:
        return FinishedView(session.channel_id)
    return GameView(session.channel_id)


def hand_text(game: UnoGame, user_id: int, page: int = 0, page_size: int = 25) -> str:
    cards = game.hand_for(user_id)
    total_pages = max(1, (len(cards) + page_size - 1) // page_size)
    return (
        "**Kartu tanganmu**\n"
        f"Halaman {page + 1}/{total_pages}. Lihat gambar kartu di bawah, lalu pilih nomor kartu dari dropdown.\n"
        "Border hijau berarti kartu tersebut bisa dimainkan."
    )


def rules_embed() -> discord.Embed:
    embed = discord.Embed(
        title="Rules UNO Reguler",
        description="Baca dulu sebelum ikut bermain. Versi ini dibuat sederhana agar ritme game tetap cepat.",
        color=discord.Color.gold(),
    )
    embed.add_field(
        name="Tujuan",
        value="Habiskan semua kartu di tanganmu. Pemain yang kartunya habis pertama menang.",
        inline=False,
    )
    embed.add_field(
        name="Yang Harus Dilakukan",
        value=(
            "- Mainkan kartu yang cocok dengan warna aktif atau angka/aksi kartu aktif.\n"
            "- Gunakan kartu Change Color untuk mengganti warna.\n"
            "- Ambil kartu jika tidak ada kartu yang bisa dimainkan.\n"
            "- Pass hanya jika tidak punya kartu yang bisa dimainkan.\n"
            "- Tekan tombol UNO! saat kartumu tersisa tepat 1.\n"
            "- Challenge pemain lain yang lupa menekan UNO sebelum mereka sempat menekannya."
        ),
        inline=False,
    )
    embed.add_field(
        name="Yang Tidak Boleh Dilakukan",
        value=(
            "- Jangan melihat atau meminta screenshot kartu pemain lain.\n"
            "- Jangan spam tombol draw/pass/refresh.\n"
            "- Jangan sengaja memperlambat giliran terlalu lama.\n"
            "- Jangan memulai lobby baru saat game di channel masih berjalan."
        ),
        inline=False,
    )
    embed.add_field(
        name="Kartu Special",
        value=(
            "**Stop/Skip** melewati pemain berikutnya.\n"
            "**Reverse** membalik arah permainan. Pada 2 pemain, Reverse bertindak seperti Stop.\n"
            "**+2** membuat pemain berikutnya mengambil 2 kartu dan dilewati.\n"
            "**Change Color** memilih warna baru.\n"
            "**Change Color +4** memilih warna baru, pemain berikutnya mengambil 4 kartu dan dilewati."
        ),
        inline=False,
    )
    embed.add_field(
        name="Rule Tombol UNO!",
        value=(
            "Jika setelah memainkan kartu kamu tersisa 1 kartu, kamu wajib menekan tombol **UNO!**. "
            "Kamu tidak bisa memainkan kartu terakhir sebelum tombol UNO! ditekan. Jika pemain lain menekan "
            "**Challenge UNO** lebih dulu, kamu mengambil 2 kartu penalti."
        ),
        inline=False,
    )
    embed.add_field(
        name="Batasan Versi Ini",
        value=(
            "Belum ada stacking +2/+4 dan belum ada challenge +4. Challenge UNO hanya berlaku untuk pemain "
            "yang sedang tersisa 1 kartu dan belum menekan UNO."
        ),
        inline=False,
    )
    embed.set_footer(text="Klik Ikut Main jika setuju mengikuti rules meja ini.")
    return embed


def table_visuals(session: UnoSession) -> tuple[discord.Embed | None, list[discord.File]]:
    if session.game.status == GameStatus.WAITING:
        return rules_embed(), []

    if session.game.status != GameStatus.PLAYING:
        return None, []

    buffer, filename = render_card_image(session.game.top_card, "current_card.jpg")
    file = discord.File(buffer, filename=filename)
    embed = discord.Embed(
        title="Kartu Aktif",
        description=f"Warna aktif: **{COLOR_LABELS[session.game.current_color]}**",
    )
    embed.set_image(url=f"attachment://{filename}")
    return embed, [file]


def hand_visuals(
    game: UnoGame,
    user_id: int,
    page: int = 0,
    page_size: int = 25,
) -> tuple[discord.Embed, list[discord.File]]:
    cards = game.hand_for(user_id)
    playable = set(game.playable_cards_for(user_id))
    buffer, filename = render_hand_image(cards, playable, page, page_size, "your_hand.jpg")
    file = discord.File(buffer, filename=filename)
    embed = discord.Embed(title="Kartu Tangan")
    embed.set_image(url=f"attachment://{filename}")
    return embed, [file]


def poker_lobby_text(session: PokerSession) -> str:
    players = "\n".join(f"- {mention(player.user_id)}" for player in session.game.players)
    if not players:
        players = "Belum ada pemain."
    mode_text = "Tournament" if session.is_tournament else "Regular"
    tournament_text = ""
    if session.is_tournament:
        tournament_text = f"Jumlah ronde tournament: **{session.tournament_total_rounds} game**\n"
    return (
        "**Remi Poker: Lobby**\n"
        "Mode ini memakai rules Big Two style: habiskan kartu, jangan menjadi loser.\n\n"
        f"Owner: {mention(session.owner_id)}\n"
        f"Mode: **{mode_text}**\n"
        f"{tournament_text}"
        f"Timer auto-pass: **{session.timer_seconds} detik**\n"
        f"Pemain ({len(session.game.players)}/{session.game.max_players}):\n{players}"
    )


def poker_state_text(session: PokerSession) -> str:
    state = session.game.public_state()
    hand_counts = "\n".join(
        f"- {mention(user_id)}: {count} kartu"
        + (" (winner)" if finished else "")
        + (" (bombed)" if bombed else "")
        for user_id, _name, count, finished, bombed in state["hand_counts"]
    )
    winners = ", ".join(mention(user_id) for user_id in state["winner_ids"]) or "Belum ada"
    loser = mention(state["loser_id"]) if state["loser_id"] else "Belum ada"
    action_text = "\n".join(f"- {message}" for message in session.log[:2]) or "- Belum ada aksi."
    vote_text = f"{session.end_vote_count}/{session.end_vote_required} setuju"
    current_player = mention(state["current_player_id"]) if state["current_player_id"] else "-"
    last_player = mention(state["last_play_player_id"]) if state["last_play_player_id"] else "-"
    last_play_suffix = " (ronde sebelumnya, table sudah clear)" if state["table_cleared"] else ""
    bomb_duel_text = ""
    if state["bomb_duel_active"]:
        victim = mention(state["bomb_duel_current_victim_id"]) if state["bomb_duel_current_victim_id"] else "-"
        bomber = mention(state["bomb_duel_current_bomber_id"]) if state["bomb_duel_current_bomber_id"] else "-"
        original = mention(state["bomb_duel_original_target_id"]) if state["bomb_duel_original_target_id"] else "-"
        bomb_duel_text = (
            "\n"
            f"Adu bomb aktif: bomb terakhir dari {bomber}. Target saat ini: {victim}. "
            f"Target awal: {original}.\n"
        )
    tournament_header = ""
    tournament_scores = ""
    if session.is_tournament:
        tournament_header = f"Mode: **Tournament ronde {session.tournament_current_round}/{session.tournament_total_rounds}**\n"
        tournament_scores = f"\n\n{tournament_scoreboard_text(session)}"

    return (
        "**Remi Poker: Game Berjalan**\n"
        f"{tournament_header}"
        f"Gilirannya: {current_player}\n"
        f"Timer auto-pass: **{session.timer_seconds} detik**\n"
        f"Pola ronde: **{state['round_pattern']}**\n"
        f"Kombinasi terakhir: **{state['last_play']}**{last_play_suffix}\n"
        f"Dimainkan oleh: {last_player}\n"
        f"{bomb_duel_text}"
        f"Pass ronde ini: {state['pass_count']}\n\n"
        f"Jumlah kartu pemain:\n{hand_counts}\n\n"
        f"Winner sementara: {winners}\n"
        f"Loser: {loser}\n"
        f"Vote akhiri game: **{vote_text}**\n\n"
        f"Aksi terakhir:\n{action_text}"
        f"{tournament_scores}"
    )


def poker_finished_text(session: PokerSession) -> str:
    state = session.game.public_state()
    winners = ", ".join(mention(user_id) for user_id in state["winner_ids"]) or "Tidak ada"
    loser = mention(state["loser_id"]) if state["loser_id"] else "Tidak ada"
    log_text = "\n".join(f"- {message}" for message in session.log[-3:]) or "- Game selesai."
    if session.is_tournament:
        if session.tournament_aborted:
            return (
                "**Remi Poker Tournament: Dihentikan**\n"
                f"Ronde terakhir: {session.tournament_current_round}/{session.tournament_total_rounds}\n\n"
                f"{tournament_scoreboard_text(session)}\n\n"
                f"Log akhir:\n{log_text}\n\n"
                "Tekan **Buat Lobby Baru** untuk main lagi."
            )
        if not session.tournament_finished:
            return (
                "**Remi Poker Tournament: Ronde Selesai**\n"
                f"Ronde selesai: {session.tournament_current_round}/{session.tournament_total_rounds}\n"
                f"Winner ronde: {winners}\n"
                f"Loser ronde: {loser}\n\n"
                f"{tournament_scoreboard_text(session)}\n\n"
                f"Log akhir:\n{log_text}\n\n"
                "Tekan **Mulai Ronde Berikutnya** untuk lanjut."
            )
        champion = next(iter(sorted(session.tournament_scores.items(), key=lambda item: item[1], reverse=True)), None)
        champion_text = mention(champion[0]) if champion else "Tidak ada"
        return (
            "**Remi Poker Tournament: Selesai**\n"
            f"Total ronde: {session.tournament_total_rounds}\n"
            f"Champion: {champion_text}\n\n"
            f"{tournament_scoreboard_text(session)}\n\n"
            f"Log akhir:\n{log_text}\n\n"
            "Tekan **Buat Lobby Baru** untuk main lagi."
        )
    return (
        "**Remi Poker: Selesai**\n"
        f"Winner: {winners}\n"
        f"Loser: {loser}\n\n"
        f"Log akhir:\n{log_text}\n\n"
        "Tekan **Buat Lobby Baru** untuk main lagi."
    )


def poker_table_text(session: PokerSession) -> str:
    if session.game.status == PokerStatus.WAITING:
        return poker_lobby_text(session)
    if session.game.status == PokerStatus.FINISHED:
        return poker_finished_text(session)
    return poker_state_text(session)


def poker_rules_embed() -> discord.Embed:
    embed = discord.Embed(
        title="Rules Remi Poker",
        description="Mode shedding/climbing kartu remi. Habiskan kartu dan jangan menjadi loser.",
        color=discord.Color.dark_gold(),
    )
    embed.add_field(
        name="Setup",
        value=(
            "- Pemain 2-4 orang.\n"
            "- Joker tidak dipakai.\n"
            "- Kartu 3 hanya menentukan first turn, lalu dibuang.\n"
            "- Rank playable terendah adalah 4, tertinggi adalah 2.\n"
            "- Timer auto-pass bisa dipilih di lobby: 45 atau 60 detik."
        ),
        inline=False,
    )
    embed.add_field(
        name="Mode Tournament",
        value=(
            "Regular bermain 1 game. Tournament bermain 3-20 ronde dengan akumulasi point: "
            "winner pertama +20, winner berikutnya +10, posisi tengah +0, loser terakhir -10."
        ),
        inline=False,
    )
    embed.add_field(
        name="First Turn",
        value=(
            "Pemilik 3 diamonds + 3 clubs + 3 hearts mulai dulu. Jika tidak ada, pemilik 3 spades mulai."
        ),
        inline=False,
    )
    embed.add_field(
        name="Kombinasi",
        value=(
            "Single, pair, three of a kind, straight, flush, full house, four of a kind, "
            "straight flush, royal flush."
        ),
        inline=False,
    )
    embed.add_field(
        name="Pola Ronde",
        value=(
            "Pola mengikuti pembuka ronde sampai table clear. Jika semua pemain lain pass, pemain terakhir "
            "yang memainkan kartu membuka ronde baru dengan pola bebas."
        ),
        inline=False,
    )
    embed.add_field(
        name="Bombcard",
        value=(
            "Four of a kind, straight flush, dan royal flush adalah bombcard. Bomb bisa menantang single 2 "
            "jika pemain yang mengeluarkan 2 masih punya sisa kartu. Bomb tidak bisa memotong pair/triple 2. "
            "Jika bomb dibalas bomb lebih besar, target kalah berpindah ke pemain bomb sebelumnya."
        ),
        inline=False,
    )
    return embed


def poker_table_view(session: PokerSession) -> discord.ui.View:
    if session.game.status == PokerStatus.WAITING:
        return PokerLobbyView(session.channel_id)
    if session.tournament_between_rounds:
        return PokerTournamentRoundFinishedView(session.channel_id)
    if session.game.status == PokerStatus.FINISHED:
        return PokerFinishedView(session.channel_id)
    return PokerGameView(session.channel_id)


def poker_table_visuals(session: PokerSession) -> tuple[discord.Embed | None, list[discord.File]]:
    if session.game.status == PokerStatus.WAITING:
        return poker_rules_embed(), []
    if session.game.status != PokerStatus.PLAYING or session.game.visible_last_play is None:
        return None, []

    visible_last_play = session.game.visible_last_play
    buffer, filename = render_play_image(list(visible_last_play.cards), "poker_last_play.jpg")
    file = discord.File(buffer, filename=filename)
    embed = discord.Embed(title="Kombinasi Terakhir", description=visible_last_play.label)
    embed.set_image(url=f"attachment://{filename}")
    return embed, [file]


def poker_hand_text(
    game: PokerGame,
    user_id: int,
    page: int = 0,
    page_size: int = 25,
    selected_numbers: set[int] | None = None,
) -> str:
    cards = game.hand_for(user_id)
    total_pages = max(1, (len(cards) + page_size - 1) // page_size)
    selected = ", ".join(str(number) for number in sorted(selected_numbers or set())) or "belum ada"
    return (
        "**Kartu Remi Tanganmu**\n"
        f"Halaman {page + 1}/{total_pages}. Pilih 1-5 kartu dari dropdown, lalu tekan **Mainkan Pilihan**.\n"
        f"Pilihan saat ini: {selected}"
    )


def poker_hand_visuals(
    game: PokerGame,
    user_id: int,
    page: int = 0,
    page_size: int = 25,
    selected_numbers: set[int] | None = None,
) -> tuple[discord.Embed, list[discord.File]]:
    buffer, filename = render_poker_hand_image(game.hand_for(user_id), page, selected_numbers, page_size)
    file = discord.File(buffer, filename=filename)
    embed = discord.Embed(title="Kartu Remi")
    embed.set_image(url=f"attachment://{filename}")
    return embed, [file]


async def reply_error(interaction: discord.Interaction, error: Exception) -> None:
    prefix = "Remi Poker" if isinstance(error, PokerGameError) else "UNO"
    message = f"{prefix}: {error}"
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


async def refresh_table_message(session: UnoSession) -> None:
    await repost_table_message(session)


async def repost_table_message(session: UnoSession) -> None:
    channel = bot.get_channel(session.channel_id)
    if not hasattr(channel, "send"):
        return

    old_message_id = session.table_message_id
    embed, files = table_visuals(session)
    message = await channel.send(content=table_text(session), view=table_view(session), embed=embed, files=files)
    session.table_message_id = message.id

    if old_message_id is not None:
        await delete_table_message(session, old_message_id)


async def delete_table_message(session: UnoSession, message_id: int) -> None:
    channel = bot.get_channel(session.channel_id)
    if not hasattr(channel, "fetch_message"):
        return
    try:
        old_message = await channel.fetch_message(message_id)
        await old_message.delete()
    except (discord.Forbidden, discord.HTTPException, discord.NotFound):
        return


async def update_table_from_interaction(interaction: discord.Interaction, session: UnoSession) -> None:
    if not interaction.response.is_done():
        await interaction.response.defer()
    await repost_table_message(session)


async def refresh_poker_table_message(session: PokerSession) -> None:
    finalize_poker_round_if_needed(session)
    await repost_poker_table_message(session)
    schedule_poker_turn_timer(session)


async def repost_poker_table_message(session: PokerSession) -> None:
    finalize_poker_round_if_needed(session)
    channel = bot.get_channel(session.channel_id)
    if not hasattr(channel, "send"):
        return

    old_message_id = session.table_message_id
    embed, files = poker_table_visuals(session)
    message = await channel.send(
        content=poker_table_text(session),
        view=poker_table_view(session),
        embed=embed,
        files=files,
    )
    session.table_message_id = message.id

    if old_message_id is not None:
        await delete_poker_table_message(session, old_message_id)


async def delete_poker_table_message(session: PokerSession, message_id: int) -> None:
    channel = bot.get_channel(session.channel_id)
    if not hasattr(channel, "fetch_message"):
        return
    try:
        old_message = await channel.fetch_message(message_id)
        await old_message.delete()
    except (discord.Forbidden, discord.HTTPException, discord.NotFound):
        return


async def update_poker_table_from_interaction(interaction: discord.Interaction, session: PokerSession) -> None:
    if not interaction.response.is_done():
        await interaction.response.defer()
    finalize_poker_round_if_needed(session)
    await repost_poker_table_message(session)
    schedule_poker_turn_timer(session)


def cancel_poker_turn_timer(session: PokerSession) -> None:
    session.turn_timer_token += 1
    current_task = asyncio.current_task()
    if (
        session.turn_timer_task
        and not session.turn_timer_task.done()
        and session.turn_timer_task is not current_task
    ):
        session.turn_timer_task.cancel()
    session.turn_timer_task = None


def schedule_poker_turn_timer(session: PokerSession) -> None:
    cancel_poker_turn_timer(session)
    if session.game.status != PokerStatus.PLAYING:
        return

    try:
        current_player_id = session.game.current_player.user_id
    except PokerGameError:
        return

    session.turn_timer_token += 1
    token = session.turn_timer_token
    session.turn_timer_task = asyncio.create_task(
        poker_turn_timer_worker(session, token, current_player_id)
    )


async def poker_turn_timer_worker(session: PokerSession, token: int, expected_user_id: int) -> None:
    try:
        await asyncio.sleep(session.timer_seconds)
        if session.turn_timer_token != token or session.game.status != PokerStatus.PLAYING:
            return
        if session.game.current_player.user_id != expected_user_id:
            return

        result = session.game.timeout_current_player()
        add_poker_result_log(session, result.public_messages)
        await repost_poker_table_message(session)
        schedule_poker_turn_timer(session)
    except asyncio.CancelledError:
        return
    except PokerGameError as error:
        session.add_log(f"Timer gagal: {error}")
        await repost_poker_table_message(session)


def add_result_log(session: UnoSession, messages: list[str]) -> None:
    session.end_game_votes.clear()
    clean_messages = [
        message
        for message in messages
        if message and not message.startswith("Giliran berikutnya:")
    ]
    session.add_log(clean_messages)


def add_poker_result_log(session: PokerSession, messages: list[str]) -> None:
    session.end_game_votes.clear()
    clean_messages = [
        message
        for message in messages
        if message and not message.startswith("Giliran berikutnya:")
    ]
    session.add_log(clean_messages)


class LobbyView(discord.ui.View):
    def __init__(self, channel_id: int) -> None:
        super().__init__(timeout=None)
        self.channel_id = channel_id

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        _item: discord.ui.Item,
    ) -> None:
        await reply_error(interaction, error)

    @discord.ui.button(label="Ikut Main", style=discord.ButtonStyle.success)
    async def join_game(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session = get_session(self.channel_id)
            session.game.add_player(interaction.user.id, interaction.user.display_name)
            session.add_log(f"{interaction.user.display_name} masuk lobby.")
            await update_table_from_interaction(interaction, session)
        except UnoGameError as error:
            await reply_error(interaction, error)

    @discord.ui.button(label="Mulai Game", style=discord.ButtonStyle.primary)
    async def begin_game(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session = get_session(self.channel_id)
            messages = session.game.start()
            session.add_log(messages)
            await update_table_from_interaction(interaction, session)
        except UnoGameError as error:
            await reply_error(interaction, error)

    @discord.ui.button(label="Tutup Lobby", style=discord.ButtonStyle.danger)
    async def close_lobby(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session = get_session(self.channel_id)
            require_session_player(session, interaction.user.id)
            sessions_by_channel.pop(self.channel_id, None)
            content = f"**UNO Table ditutup** oleh {interaction.user.mention}."
            if not interaction.response.is_done():
                await interaction.response.defer()
            old_message_id = session.table_message_id
            channel = bot.get_channel(session.channel_id)
            if hasattr(channel, "send"):
                await channel.send(content)
            if old_message_id is not None:
                await delete_table_message(session, old_message_id)
            session.table_message_id = None
        except UnoGameError as error:
            await reply_error(interaction, error)


class FinishedView(discord.ui.View):
    def __init__(self, channel_id: int) -> None:
        super().__init__(timeout=None)
        self.channel_id = channel_id

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        _item: discord.ui.Item,
    ) -> None:
        await reply_error(interaction, error)

    @discord.ui.button(label="Buat Lobby Baru", style=discord.ButtonStyle.success)
    async def new_lobby(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session = UnoSession(channel_id=self.channel_id, owner_id=interaction.user.id)
            session.game.add_player(interaction.user.id, interaction.user.display_name)
            session.add_log(f"Lobby baru dibuat oleh {interaction.user.display_name}.")
            old_session = sessions_by_channel.get(self.channel_id)
            if old_session:
                session.table_message_id = old_session.table_message_id
            sessions_by_channel[self.channel_id] = session
            await update_table_from_interaction(interaction, session)
        except UnoGameError as error:
            await reply_error(interaction, error)


class PokerTimerSelect(discord.ui.Select):
    def __init__(self, channel_id: int) -> None:
        self.channel_id = channel_id
        options = [
            discord.SelectOption(label="45 detik", value="45", description="Auto-pass standar"),
            discord.SelectOption(label="60 detik", value="60", description="Auto-pass lebih santai"),
        ]
        super().__init__(
            placeholder="Pilih timer auto-pass",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        try:
            session = get_poker_session(self.channel_id)
            require_poker_player(session, interaction.user.id)
            if session.game.status != PokerStatus.WAITING:
                raise PokerGameError("Timer hanya bisa diubah saat lobby belum mulai.")
            session.timer_seconds = int(self.values[0])
            session.add_log(f"Timer auto-pass diatur ke {session.timer_seconds} detik.")
            await update_poker_table_from_interaction(interaction, session)
        except PokerGameError as error:
            await reply_error(interaction, error)


class PokerModeSelect(discord.ui.Select):
    def __init__(self, channel_id: int) -> None:
        self.channel_id = channel_id
        session = get_poker_session(channel_id)
        options = [
            discord.SelectOption(
                label="Regular",
                value="regular",
                description="Main 1 game seperti biasa",
                default=not session.is_tournament,
            ),
            discord.SelectOption(
                label="Tournament",
                value="tournament",
                description="Main 3-20 ronde dengan akumulasi point",
                default=session.is_tournament,
            ),
        ]
        super().__init__(
            placeholder="Pilih mode permainan",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        try:
            session = get_poker_session(self.channel_id)
            require_poker_player(session, interaction.user.id)
            if session.game.status != PokerStatus.WAITING:
                raise PokerGameError("Mode hanya bisa diubah saat lobby belum mulai.")

            session.mode = self.values[0]
            if session.is_tournament:
                session.tournament_total_rounds = max(3, session.tournament_total_rounds)
                session.add_log("Mode diubah ke Tournament.")
            else:
                session.tournament_current_round = 0
                session.tournament_scores.clear()
                session.tournament_round_summaries.clear()
                session.tournament_scored_rounds.clear()
                session.tournament_aborted = False
                session.add_log("Mode diubah ke Regular.")
            await update_poker_table_from_interaction(interaction, session)
        except PokerGameError as error:
            await reply_error(interaction, error)


class PokerTournamentRoundSelect(discord.ui.Select):
    def __init__(self, channel_id: int) -> None:
        self.channel_id = channel_id
        options = [
            discord.SelectOption(
                label=f"{round_count} ronde",
                value=str(round_count),
                description="Jumlah game dalam tournament",
            )
            for round_count in range(3, 21)
        ]
        super().__init__(
            placeholder="Pilih jumlah ronde tournament",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        try:
            session = get_poker_session(self.channel_id)
            require_poker_player(session, interaction.user.id)
            if not session.is_tournament:
                raise PokerGameError("Jumlah ronde hanya dipakai untuk mode tournament.")
            if session.game.status != PokerStatus.WAITING:
                raise PokerGameError("Jumlah ronde hanya bisa diubah saat lobby belum mulai.")
            session.tournament_total_rounds = int(self.values[0])
            session.add_log(f"Jumlah ronde tournament diatur ke {session.tournament_total_rounds}.")
            await update_poker_table_from_interaction(interaction, session)
        except PokerGameError as error:
            await reply_error(interaction, error)


class PokerLobbyView(discord.ui.View):
    def __init__(self, channel_id: int) -> None:
        super().__init__(timeout=None)
        self.channel_id = channel_id
        session = poker_sessions_by_channel.get(channel_id)
        self.add_item(PokerModeSelect(channel_id))
        self.add_item(PokerTimerSelect(channel_id))
        if session and session.is_tournament:
            self.add_item(PokerTournamentRoundSelect(channel_id))

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        _item: discord.ui.Item,
    ) -> None:
        await reply_error(interaction, error)

    @discord.ui.button(label="Ikut Main", style=discord.ButtonStyle.success)
    async def join_game(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session = get_poker_session(self.channel_id)
            session.game.add_player(interaction.user.id, interaction.user.display_name)
            session.add_log(f"{interaction.user.display_name} masuk lobby.")
            await update_poker_table_from_interaction(interaction, session)
        except PokerGameError as error:
            await reply_error(interaction, error)

    @discord.ui.button(label="Mulai Game", style=discord.ButtonStyle.primary)
    async def begin_game(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session = get_poker_session(self.channel_id)
            messages = session.start_poker_round()
            session.add_log(messages)
            await update_poker_table_from_interaction(interaction, session)
        except PokerGameError as error:
            await reply_error(interaction, error)

    @discord.ui.button(label="Tutup Lobby", style=discord.ButtonStyle.danger)
    async def close_lobby(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session = get_poker_session(self.channel_id)
            require_poker_player(session, interaction.user.id)
            poker_sessions_by_channel.pop(self.channel_id, None)
            cancel_poker_turn_timer(session)
            if not interaction.response.is_done():
                await interaction.response.defer()
            old_message_id = session.table_message_id
            channel = bot.get_channel(session.channel_id)
            if hasattr(channel, "send"):
                await channel.send(f"**Remi Poker ditutup** oleh {interaction.user.mention}.")
            if old_message_id is not None:
                await delete_poker_table_message(session, old_message_id)
            session.table_message_id = None
        except PokerGameError as error:
            await reply_error(interaction, error)


class PokerFinishedView(discord.ui.View):
    def __init__(self, channel_id: int) -> None:
        super().__init__(timeout=None)
        self.channel_id = channel_id

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        _item: discord.ui.Item,
    ) -> None:
        await reply_error(interaction, error)

    @discord.ui.button(label="Buat Lobby Baru", style=discord.ButtonStyle.success)
    async def new_lobby(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session = PokerSession(channel_id=self.channel_id, owner_id=interaction.user.id)
            session.game.add_player(interaction.user.id, interaction.user.display_name)
            session.add_log(f"Lobby baru dibuat oleh {interaction.user.display_name}.")
            old_session = poker_sessions_by_channel.get(self.channel_id)
            if old_session:
                cancel_poker_turn_timer(old_session)
                session.table_message_id = old_session.table_message_id
            poker_sessions_by_channel[self.channel_id] = session
            await update_poker_table_from_interaction(interaction, session)
        except PokerGameError as error:
            await reply_error(interaction, error)


class PokerTournamentRoundFinishedView(discord.ui.View):
    def __init__(self, channel_id: int) -> None:
        super().__init__(timeout=None)
        self.channel_id = channel_id

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        _item: discord.ui.Item,
    ) -> None:
        await reply_error(interaction, error)

    @discord.ui.button(label="Mulai Ronde Berikutnya", style=discord.ButtonStyle.success)
    async def next_round(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session = get_poker_session(self.channel_id)
            require_poker_player(session, interaction.user.id)
            cancel_poker_turn_timer(session)
            messages = session.start_next_tournament_round()
            session.add_log(messages)
            await update_poker_table_from_interaction(interaction, session)
        except PokerGameError as error:
            await reply_error(interaction, error)

    @discord.ui.button(label="Vote End Tournament", style=discord.ButtonStyle.danger)
    async def vote_end_tournament(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session = get_poker_session(self.channel_id)
            votes, required, approved = session.add_end_vote(interaction.user.id)
            if approved:
                session.tournament_aborted = True
                session.end_game_votes.clear()
                session.add_log(f"Vote end tournament disetujui {votes}/{required}. Tournament dihentikan.")
            else:
                session.add_log(f"{interaction.user.display_name} vote end tournament ({votes}/{required}).")
            await update_poker_table_from_interaction(interaction, session)
        except PokerGameError as error:
            await reply_error(interaction, error)


class PokerGameView(discord.ui.View):
    def __init__(self, channel_id: int) -> None:
        super().__init__(timeout=None)
        self.channel_id = channel_id

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        _item: discord.ui.Item,
    ) -> None:
        await reply_error(interaction, error)

    @discord.ui.button(label="Lihat / Mainkan Kartu", style=discord.ButtonStyle.primary)
    async def show_hand(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session = get_poker_session(self.channel_id)
            session.game.hand_for(interaction.user.id)
            embed, files = poker_hand_visuals(session.game, interaction.user.id)
            await interaction.response.send_message(
                poker_hand_text(session.game, interaction.user.id),
                embed=embed,
                files=files,
                view=PokerHandView(self.channel_id, interaction.user.id),
                ephemeral=True,
            )
        except PokerGameError as error:
            await reply_error(interaction, error)

    @discord.ui.button(label="Pass", style=discord.ButtonStyle.secondary)
    async def pass_turn(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session = get_poker_session(self.channel_id)
            result = session.game.pass_turn(interaction.user.id)
            add_poker_result_log(session, result.public_messages)
            await update_poker_table_from_interaction(interaction, session)
        except PokerGameError as error:
            await reply_error(interaction, error)

    @discord.ui.button(label="Refresh Meja", style=discord.ButtonStyle.secondary)
    async def refresh(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session = get_poker_session(self.channel_id)
            await update_poker_table_from_interaction(interaction, session)
        except PokerGameError as error:
            await reply_error(interaction, error)

    @discord.ui.button(label="Vote End Game", style=discord.ButtonStyle.danger)
    async def vote_end_game(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session = get_poker_session(self.channel_id)
            votes, required, approved = session.add_end_vote(interaction.user.id)
            if approved:
                session.game.status = PokerStatus.FINISHED
                if session.is_tournament:
                    session.tournament_aborted = True
                session.end_game_votes.clear()
                label = "Tournament" if session.is_tournament else "Game"
                session.add_log(f"Vote end game disetujui {votes}/{required}. {label} diakhiri.")
            else:
                session.add_log(f"{interaction.user.display_name} vote end game ({votes}/{required}).")
            await update_poker_table_from_interaction(interaction, session)
        except PokerGameError as error:
            await reply_error(interaction, error)


class GameView(discord.ui.View):
    def __init__(self, channel_id: int) -> None:
        super().__init__(timeout=None)
        self.channel_id = channel_id

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        _item: discord.ui.Item,
    ) -> None:
        await reply_error(interaction, error)

    @discord.ui.button(label="Lihat / Mainkan Kartu", style=discord.ButtonStyle.primary)
    async def show_hand(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session = get_session(self.channel_id)
            session.game.hand_for(interaction.user.id)
            embed, files = hand_visuals(session.game, interaction.user.id)
            await interaction.response.send_message(
                hand_text(session.game, interaction.user.id),
                embed=embed,
                files=files,
                view=HandView(self.channel_id, interaction.user.id),
                ephemeral=True,
            )
        except UnoGameError as error:
            await reply_error(interaction, error)

    @discord.ui.button(label="Ambil Kartu", style=discord.ButtonStyle.secondary)
    async def draw_card(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session = get_session(self.channel_id)
            result = session.game.draw_card(interaction.user.id)
            add_result_log(session, result.public_messages)
            await update_table_from_interaction(interaction, session)
        except UnoGameError as error:
            await reply_error(interaction, error)

    @discord.ui.button(label="Pass", style=discord.ButtonStyle.secondary)
    async def pass_turn(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session = get_session(self.channel_id)
            result = session.game.pass_turn(interaction.user.id)
            add_result_log(session, result.public_messages)
            await update_table_from_interaction(interaction, session)
        except UnoGameError as error:
            await reply_error(interaction, error)

    @discord.ui.button(label="UNO!", style=discord.ButtonStyle.success, row=1)
    async def call_uno(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session = get_session(self.channel_id)
            result = session.game.call_uno(interaction.user.id)
            add_result_log(session, result.public_messages)
            await update_table_from_interaction(interaction, session)
        except UnoGameError as error:
            await reply_error(interaction, error)

    @discord.ui.button(label="Challenge UNO", style=discord.ButtonStyle.danger, row=1)
    async def challenge_uno(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session = get_session(self.channel_id)
            pending_players = [
                (user_id, name)
                for user_id, name in session.game.public_state()["uno_pending"]
                if user_id != interaction.user.id
            ]
            if len(pending_players) > 1:
                await interaction.response.send_message(
                    "Pilih pemain yang lupa menekan UNO:",
                    view=ChallengeUnoView(self.channel_id, interaction.user.id),
                    ephemeral=True,
                )
                return

            target_user_id = pending_players[0][0] if pending_players else None
            result = session.game.challenge_uno(interaction.user.id, target_user_id)
            add_result_log(session, result.public_messages)
            await update_table_from_interaction(interaction, session)
        except UnoGameError as error:
            await reply_error(interaction, error)

    @discord.ui.button(label="Refresh Meja", style=discord.ButtonStyle.secondary, row=2)
    async def refresh(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session = get_session(self.channel_id)
            await update_table_from_interaction(interaction, session)
        except UnoGameError as error:
            await reply_error(interaction, error)

    @discord.ui.button(label="Vote End Game", style=discord.ButtonStyle.danger, row=2)
    async def vote_end_game(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session = get_session(self.channel_id)
            votes, required, approved = session.add_end_vote(interaction.user.id)
            if approved:
                session.game.status = GameStatus.FINISHED
                session.end_game_votes.clear()
                session.add_log(
                    f"Vote end game disetujui {votes}/{required}. Game diakhiri."
                )
            else:
                session.add_log(
                    f"{interaction.user.display_name} vote end game ({votes}/{required})."
                )
            await update_table_from_interaction(interaction, session)
        except UnoGameError as error:
            await reply_error(interaction, error)


class CardSelect(discord.ui.Select):
    def __init__(self, channel_id: int, user_id: int, page: int, page_size: int = 25) -> None:
        self.channel_id = channel_id
        self.user_id = user_id
        self.page = page
        self.page_size = page_size

        session = get_session(channel_id)
        cards = session.game.hand_for(user_id)
        playable = set(session.game.playable_cards_for(user_id))
        start = page * page_size
        shown_cards = cards[start : start + page_size]

        options = []
        for index, card in enumerate(shown_cards, start=start + 1):
            status = "Bisa dimainkan" if index - 1 in playable else "Belum cocok"
            options.append(
                discord.SelectOption(
                    label=f"{index}. {card.label}"[:100],
                    description=status,
                    value=str(index),
                )
            )

        if not options:
            options = [discord.SelectOption(label="Tidak ada kartu", value="empty")]

        super().__init__(
            placeholder="Pilih kartu untuk dimainkan",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        try:
            if interaction.user.id != self.user_id:
                raise UnoGameError("Ini panel kartu pemain lain.")
            if self.values[0] == "empty":
                raise UnoGameError("Tidak ada kartu yang bisa dipilih.")

            session = get_session(self.channel_id)
            card_number = int(self.values[0])
            card = session.game.hand_for(self.user_id)[card_number - 1]
            if card.is_wild:
                await interaction.response.edit_message(
                    content=f"Kamu memilih **{card.label}**. Pilih warna baru:",
                    embed=None,
                    attachments=[],
                    view=ColorPickView(self.channel_id, self.user_id, card_number),
                )
                return

            result = session.game.play_card(self.user_id, card_number)
            add_result_log(session, result.public_messages)
            await interaction.response.edit_message(
                content="\n".join(result.public_messages),
                embed=None,
                attachments=[],
                view=None,
            )
            await refresh_table_message(session)
        except UnoGameError as error:
            await reply_error(interaction, error)


class ChallengeTargetSelect(discord.ui.Select):
    def __init__(self, channel_id: int, challenger_user_id: int) -> None:
        self.channel_id = channel_id
        self.challenger_user_id = challenger_user_id
        session = get_session(channel_id)
        pending_players = [
            (user_id, name)
            for user_id, name in session.game.public_state()["uno_pending"]
            if user_id != challenger_user_id
        ]
        options = [
            discord.SelectOption(
                label=name[:100],
                description="Lupa menekan UNO",
                value=str(user_id),
            )
            for user_id, name in pending_players
        ]
        if not options:
            options = [discord.SelectOption(label="Tidak ada target", value="empty")]

        super().__init__(
            placeholder="Pilih target Challenge UNO",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        try:
            if interaction.user.id != self.challenger_user_id:
                raise UnoGameError("Ini panel challenge pemain lain.")
            if self.values[0] == "empty":
                raise UnoGameError("Tidak ada target Challenge UNO saat ini.")

            session = get_session(self.channel_id)
            result = session.game.challenge_uno(interaction.user.id, int(self.values[0]))
            add_result_log(session, result.public_messages)
            await interaction.response.edit_message(content="\n".join(result.public_messages), view=None)
            await refresh_table_message(session)
        except UnoGameError as error:
            await reply_error(interaction, error)


class ChallengeUnoView(discord.ui.View):
    def __init__(self, channel_id: int, challenger_user_id: int) -> None:
        super().__init__(timeout=60)
        self.channel_id = channel_id
        self.challenger_user_id = challenger_user_id
        self.add_item(ChallengeTargetSelect(channel_id, challenger_user_id))

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        _item: discord.ui.Item,
    ) -> None:
        await reply_error(interaction, error)


class PokerCardSelect(discord.ui.Select):
    def __init__(
        self,
        channel_id: int,
        user_id: int,
        page: int,
        selected_numbers: set[int],
        page_size: int = 25,
    ) -> None:
        self.channel_id = channel_id
        self.user_id = user_id
        self.page = page
        self.selected_numbers = selected_numbers
        self.page_size = page_size

        session = get_poker_session(channel_id)
        cards = session.game.hand_for(user_id)
        start = page * page_size
        shown_cards = cards[start : start + page_size]

        options = []
        for index, card in enumerate(shown_cards, start=start + 1):
            options.append(
                discord.SelectOption(
                    label=f"{index}. {card.label}"[:100],
                    description="Pilih untuk kombinasi",
                    value=str(index),
                    default=index in selected_numbers,
                )
            )

        if not options:
            options = [discord.SelectOption(label="Tidak ada kartu", value="empty")]

        super().__init__(
            placeholder="Pilih 1-5 kartu untuk dimainkan",
            min_values=1,
            max_values=min(5, len(options)),
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        try:
            if interaction.user.id != self.user_id:
                raise PokerGameError("Ini panel kartu pemain lain.")
            if self.values[0] == "empty":
                raise PokerGameError("Tidak ada kartu yang bisa dipilih.")

            session = get_poker_session(self.channel_id)
            selected_numbers = {int(value) for value in self.values}
            embed, files = poker_hand_visuals(
                session.game,
                self.user_id,
                self.page,
                self.page_size,
                selected_numbers,
            )
            await interaction.response.edit_message(
                content=poker_hand_text(
                    session.game,
                    self.user_id,
                    self.page,
                    self.page_size,
                    selected_numbers,
                ),
                embed=embed,
                attachments=files,
                view=PokerHandView(self.channel_id, self.user_id, self.page, selected_numbers),
            )
        except PokerGameError as error:
            await reply_error(interaction, error)


class PokerHandView(discord.ui.View):
    page_size = 25

    def __init__(
        self,
        channel_id: int,
        user_id: int,
        page: int = 0,
        selected_numbers: set[int] | None = None,
    ) -> None:
        super().__init__(timeout=180)
        self.channel_id = channel_id
        self.user_id = user_id
        self.page = page
        self.selected_numbers = selected_numbers or set()
        self.add_item(PokerCardSelect(channel_id, user_id, page, self.selected_numbers, self.page_size))

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        _item: discord.ui.Item,
    ) -> None:
        await reply_error(interaction, error)

    @discord.ui.button(label="Mainkan Pilihan", style=discord.ButtonStyle.primary, row=1)
    async def play_selected(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            if interaction.user.id != self.user_id:
                raise PokerGameError("Ini panel kartu pemain lain.")
            if not self.selected_numbers:
                raise PokerGameError("Pilih kartu dulu dari dropdown.")

            session = get_poker_session(self.channel_id)
            result = session.game.play_cards(self.user_id, sorted(self.selected_numbers))
            add_poker_result_log(session, result.public_messages)
            action_text = "\n".join(result.public_messages)
            await interaction.response.edit_message(
                content=(
                    f"{action_text}\n\n"
                    "Panel kartu ini ditutup agar chat tidak penuh. Tekan **Lihat / Mainkan Kartu** lagi "
                    "jika ingin melihat sisa kartu."
                ),
                embed=None,
                attachments=[],
                view=None,
            )
            await refresh_poker_table_message(session)
        except PokerGameError as error:
            await reply_error(interaction, error)

    @discord.ui.button(label="Sebelumnya", style=discord.ButtonStyle.secondary, row=2)
    async def previous_page(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._change_page(interaction, max(0, self.page - 1))

    @discord.ui.button(label="Refresh Kartu", style=discord.ButtonStyle.secondary, row=2)
    async def refresh_hand(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._change_page(interaction, self.page)

    @discord.ui.button(label="Berikutnya", style=discord.ButtonStyle.secondary, row=2)
    async def next_page(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            if interaction.user.id != self.user_id:
                raise PokerGameError("Ini panel kartu pemain lain.")
            session = get_poker_session(self.channel_id)
            total_cards = len(session.game.hand_for(self.user_id))
            max_page = max(0, (total_cards - 1) // self.page_size)
            await self._change_page(interaction, min(max_page, self.page + 1))
        except PokerGameError as error:
            await reply_error(interaction, error)

    async def _change_page(self, interaction: discord.Interaction, page: int) -> None:
        try:
            if interaction.user.id != self.user_id:
                raise PokerGameError("Ini panel kartu pemain lain.")
            session = get_poker_session(self.channel_id)
            selected_numbers: set[int] = set()
            embed, files = poker_hand_visuals(session.game, self.user_id, page, self.page_size, selected_numbers)
            await interaction.response.edit_message(
                content=poker_hand_text(session.game, self.user_id, page, self.page_size, selected_numbers),
                embed=embed,
                attachments=files,
                view=PokerHandView(self.channel_id, self.user_id, page, selected_numbers),
            )
        except PokerGameError as error:
            await reply_error(interaction, error)


class HandView(discord.ui.View):
    page_size = 25

    def __init__(self, channel_id: int, user_id: int, page: int = 0) -> None:
        super().__init__(timeout=180)
        self.channel_id = channel_id
        self.user_id = user_id
        self.page = page
        self.add_item(CardSelect(channel_id, user_id, page, self.page_size))

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        _item: discord.ui.Item,
    ) -> None:
        await reply_error(interaction, error)

    @discord.ui.button(label="Sebelumnya", style=discord.ButtonStyle.secondary, row=1)
    async def previous_page(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            if interaction.user.id != self.user_id:
                raise UnoGameError("Ini panel kartu pemain lain.")
            session = get_session(self.channel_id)
            page = max(0, self.page - 1)
            embed, files = hand_visuals(session.game, self.user_id, page, self.page_size)
            await interaction.response.edit_message(
                content=hand_text(session.game, self.user_id, page, self.page_size),
                embed=embed,
                attachments=files,
                view=HandView(self.channel_id, self.user_id, page),
            )
        except UnoGameError as error:
            await reply_error(interaction, error)

    @discord.ui.button(label="Refresh Kartu", style=discord.ButtonStyle.primary, row=1)
    async def refresh_hand(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            if interaction.user.id != self.user_id:
                raise UnoGameError("Ini panel kartu pemain lain.")
            session = get_session(self.channel_id)
            embed, files = hand_visuals(session.game, self.user_id, self.page, self.page_size)
            await interaction.response.edit_message(
                content=hand_text(session.game, self.user_id, self.page, self.page_size),
                embed=embed,
                attachments=files,
                view=HandView(self.channel_id, self.user_id, self.page),
            )
        except UnoGameError as error:
            await reply_error(interaction, error)

    @discord.ui.button(label="Berikutnya", style=discord.ButtonStyle.secondary, row=1)
    async def next_page(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            if interaction.user.id != self.user_id:
                raise UnoGameError("Ini panel kartu pemain lain.")
            session = get_session(self.channel_id)
            total_cards = len(session.game.hand_for(self.user_id))
            max_page = max(0, (total_cards - 1) // self.page_size)
            page = min(max_page, self.page + 1)
            embed, files = hand_visuals(session.game, self.user_id, page, self.page_size)
            await interaction.response.edit_message(
                content=hand_text(session.game, self.user_id, page, self.page_size),
                embed=embed,
                attachments=files,
                view=HandView(self.channel_id, self.user_id, page),
            )
        except UnoGameError as error:
            await reply_error(interaction, error)


class ColorPickView(discord.ui.View):
    def __init__(self, channel_id: int, user_id: int, card_number: int) -> None:
        super().__init__(timeout=60)
        self.channel_id = channel_id
        self.user_id = user_id
        self.card_number = card_number

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        _item: discord.ui.Item,
    ) -> None:
        await reply_error(interaction, error)

    async def play_wild(self, interaction: discord.Interaction, color: str) -> None:
        try:
            if interaction.user.id != self.user_id:
                raise UnoGameError("Ini pilihan warna pemain lain.")
            session = get_session(self.channel_id)
            result = session.game.play_card(self.user_id, self.card_number, color)
            add_result_log(session, result.public_messages)
            await interaction.response.edit_message(
                content="\n".join(result.public_messages),
                embed=None,
                attachments=[],
                view=None,
            )
            await refresh_table_message(session)
        except UnoGameError as error:
            await reply_error(interaction, error)

    @discord.ui.button(label="Merah", style=discord.ButtonStyle.danger)
    async def red(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.play_wild(interaction, "red")

    @discord.ui.button(label="Kuning", style=discord.ButtonStyle.primary)
    async def yellow(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.play_wild(interaction, "yellow")

    @discord.ui.button(label="Hijau", style=discord.ButtonStyle.success)
    async def green(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.play_wild(interaction, "green")

    @discord.ui.button(label="Biru", style=discord.ButtonStyle.primary)
    async def blue(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.play_wild(interaction, "blue")


@bot.event
async def on_ready() -> None:
    global commands_synced
    if commands_synced:
        print(f"Bot logged in as {bot.user}.")
        return

    guild_id = os.getenv("DISCORD_GUILD_ID")
    if guild_id:
        guild = discord.Object(id=int(guild_id))
        tree.copy_global_to(guild=guild)
        await tree.sync(guild=guild)
        print(f"Slash commands synced to guild {guild_id}.")
    else:
        await tree.sync()
        print("Slash commands synced globally.")
    commands_synced = True
    print(f"Bot logged in as {bot.user}.")


@tree.command(name="uno_start", description="Tampilkan meja UNO interaktif di channel ini.")
async def uno_start(interaction: discord.Interaction) -> None:
    try:
        channel_id = require_channel_id(interaction)
        existing = sessions_by_channel.get(channel_id)
        if existing and existing.game.status != GameStatus.FINISHED:
            raise UnoGameError("Sudah ada meja UNO aktif di channel ini.")

        session = UnoSession(channel_id=channel_id, owner_id=interaction.user.id)
        session.game.add_player(interaction.user.id, interaction.user.display_name)
        session.add_log(f"Lobby dibuat oleh {interaction.user.display_name}.")
        sessions_by_channel[channel_id] = session

        embed, files = table_visuals(session)
        await interaction.response.send_message(
            table_text(session),
            embed=embed,
            files=files,
            view=table_view(session),
        )
        message = await interaction.original_response()
        session.table_message_id = message.id
    except UnoGameError as error:
        await reply_error(interaction, error)


@tree.command(name="uno_hand", description="Fallback: lihat kartu tanganmu secara private.")
async def uno_hand(interaction: discord.Interaction) -> None:
    try:
        session = get_session(interaction.channel_id)
        embed, files = hand_visuals(session.game, interaction.user.id)
        await interaction.response.send_message(
            hand_text(session.game, interaction.user.id),
            embed=embed,
            files=files,
            view=HandView(session.channel_id, interaction.user.id),
            ephemeral=True,
        )
    except UnoGameError as error:
        await reply_error(interaction, error)


@tree.command(name="uno_status", description="Fallback: refresh status meja UNO.")
async def uno_status(interaction: discord.Interaction) -> None:
    try:
        session = get_session(interaction.channel_id)
        await refresh_table_message(session)
        await interaction.response.send_message("Meja UNO direfresh.", ephemeral=True)
    except UnoGameError as error:
        await reply_error(interaction, error)


@tree.command(name="uno_play", description="Fallback: mainkan kartu berdasarkan nomor di /uno_hand.")
@app_commands.describe(card_number="Nomor kartu dari /uno_hand", color="Warna baru jika memainkan Change Color")
@app_commands.choices(color=COLOR_CHOICES)
async def uno_play(
    interaction: discord.Interaction,
    card_number: app_commands.Range[int, 1, 50],
    color: str | None = None,
) -> None:
    try:
        session = get_session(interaction.channel_id)
        result = session.game.play_card(interaction.user.id, card_number, color)
        add_result_log(session, result.public_messages)
        await refresh_table_message(session)
        await interaction.response.send_message("\n".join(result.public_messages), ephemeral=True)
    except UnoGameError as error:
        await reply_error(interaction, error)


@tree.command(name="poker-start", description="Tampilkan meja Remi Poker interaktif di channel ini.")
@app_commands.describe(
    mode="Pilih regular untuk 1 game atau tournament untuk multi-round.",
    rounds="Jumlah ronde tournament, minimal 3 dan maksimal 20.",
)
@app_commands.choices(mode=POKER_MODE_CHOICES)
async def poker_start(
    interaction: discord.Interaction,
    mode: str = "regular",
    rounds: app_commands.Range[int, 3, 20] = 3,
) -> None:
    try:
        channel_id = require_channel_id(interaction)
        existing = poker_sessions_by_channel.get(channel_id)
        if existing and (existing.game.status != PokerStatus.FINISHED or existing.tournament_between_rounds):
            raise PokerGameError("Sudah ada meja Remi Poker aktif di channel ini.")

        session = PokerSession(
            channel_id=channel_id,
            owner_id=interaction.user.id,
            mode=mode,
            tournament_total_rounds=rounds,
        )
        session.game.add_player(interaction.user.id, interaction.user.display_name)
        mode_label = "Tournament" if session.is_tournament else "Regular"
        session.add_log(f"Lobby {mode_label} dibuat oleh {interaction.user.display_name}.")
        poker_sessions_by_channel[channel_id] = session

        embed, files = poker_table_visuals(session)
        await interaction.response.send_message(
            poker_table_text(session),
            embed=embed,
            files=files,
            view=poker_table_view(session),
        )
        message = await interaction.original_response()
        session.table_message_id = message.id
    except PokerGameError as error:
        await reply_error(interaction, error)


@tree.command(name="poker-hand", description="Fallback: lihat kartu Remi Poker tanganmu secara private.")
async def poker_hand(interaction: discord.Interaction) -> None:
    try:
        session = get_poker_session(interaction.channel_id)
        embed, files = poker_hand_visuals(session.game, interaction.user.id)
        await interaction.response.send_message(
            poker_hand_text(session.game, interaction.user.id),
            embed=embed,
            files=files,
            view=PokerHandView(session.channel_id, interaction.user.id),
            ephemeral=True,
        )
    except PokerGameError as error:
        await reply_error(interaction, error)


@tree.command(name="poker-status", description="Fallback: refresh status meja Remi Poker.")
async def poker_status(interaction: discord.Interaction) -> None:
    try:
        session = get_poker_session(interaction.channel_id)
        await refresh_poker_table_message(session)
        await interaction.response.send_message("Meja Remi Poker direfresh.", ephemeral=True)
    except PokerGameError as error:
        await reply_error(interaction, error)


def main() -> None:
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN belum diisi. Salin .env.example menjadi .env lalu isi token bot.")
    bot.run(token)


if __name__ == "__main__":
    main()
