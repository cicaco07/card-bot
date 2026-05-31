"""Discord UI, timer callback, and message lifecycle for remi poker."""

from __future__ import annotations

import asyncio

import discord

from poker.game import PokerGameError, PokerStatus

from ..presentation.poker import poker_hand_text, poker_hand_visuals, poker_table_text, poker_table_visuals
from ..sessions import PokerSession, finalize_poker_round_if_needed, get_poker_session, require_poker_player
from ..state import get_client, poker_sessions_by_channel
from ..timer import cancel_poker_turn_timer, schedule_poker_turn_timer as _schedule_poker_turn_timer
from .common import reply_error
from .log_utils import add_action_log


def poker_table_view(session: PokerSession) -> discord.ui.View:
    if session.game.status == PokerStatus.WAITING:
        return PokerLobbyView(session.channel_id)
    if session.tournament_between_rounds:
        return PokerTournamentRoundFinishedView(session.channel_id)
    if session.game.status == PokerStatus.FINISHED:
        return PokerFinishedView(session.channel_id)
    return PokerGameView(session.channel_id)


async def refresh_poker_table_message(session: PokerSession) -> None:
    finalize_poker_round_if_needed(session)
    await repost_poker_table_message(session)
    schedule_poker_turn_timer(session)


async def repost_poker_table_message(session: PokerSession) -> None:
    finalize_poker_round_if_needed(session)
    channel = get_client().get_channel(session.channel_id)
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
    channel = get_client().get_channel(session.channel_id)
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


def schedule_poker_turn_timer(session: PokerSession) -> None:
    _schedule_poker_turn_timer(session, _on_poker_turn_timeout)


async def _on_poker_turn_timeout(session: PokerSession) -> None:
    try:
        result = session.game.timeout_current_player()
        add_poker_result_log(session, result.public_messages)
        await repost_poker_table_message(session)
        schedule_poker_turn_timer(session)
    except PokerGameError as error:
        session.add_log(f"Timer gagal: {error}")
        await repost_poker_table_message(session)


def add_poker_result_log(session: PokerSession, messages: list[str]) -> None:
    add_action_log(session, messages)


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
            channel = get_client().get_channel(session.channel_id)
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
            await interaction.response.defer(ephemeral=True, thinking=True)
            embed, files = await asyncio.to_thread(poker_hand_visuals, session.game, interaction.user.id)
            await interaction.followup.send(
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
            await interaction.response.defer()
            embed, files = await asyncio.to_thread(
                poker_hand_visuals,
                session.game,
                self.user_id,
                self.page,
                self.page_size,
                selected_numbers,
            )
            await interaction.edit_original_response(
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
            await interaction.response.defer()
            embed, files = await asyncio.to_thread(
                poker_hand_visuals,
                session.game,
                self.user_id,
                page,
                self.page_size,
                selected_numbers,
            )
            await interaction.edit_original_response(
                content=poker_hand_text(session.game, self.user_id, page, self.page_size, selected_numbers),
                embed=embed,
                attachments=files,
                view=PokerHandView(self.channel_id, self.user_id, page, selected_numbers),
            )
        except PokerGameError as error:
            await reply_error(interaction, error)
