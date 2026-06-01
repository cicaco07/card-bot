"""Discord UI and message lifecycle for rummy."""

from __future__ import annotations

import asyncio

import discord

from rummy.game import RummyGameError, RummyStatus

from ..presentation.rummy import rummy_hand_text, rummy_hand_visuals, rummy_table_text, rummy_table_visuals
from ..sessions import RummySession, finalize_rummy_round_if_needed, get_rummy_session, require_rummy_player
from ..state import get_client, rummy_sessions_by_channel
from .common import reply_error
from .log_utils import add_action_log


def rummy_table_view(session: RummySession) -> discord.ui.View:
    if session.game.status == RummyStatus.WAITING:
        return RummyLobbyView(session.channel_id)
    if session.tournament_between_rounds:
        return RummyTournamentRoundFinishedView(session.channel_id)
    if session.game.status == RummyStatus.FINISHED:
        return RummyFinishedView(session.channel_id)
    return RummyGameView(session.channel_id)


async def refresh_rummy_table_message(session: RummySession) -> None:
    finalize_rummy_round_if_needed(session)
    await repost_rummy_table_message(session)


async def repost_rummy_table_message(session: RummySession) -> None:
    finalize_rummy_round_if_needed(session)
    channel = get_client().get_channel(session.channel_id)
    if not hasattr(channel, "send"):
        return
    old_message_id = session.table_message_id
    embed, files = rummy_table_visuals(session)
    message = await channel.send(content=rummy_table_text(session), view=rummy_table_view(session), embed=embed, files=files)
    session.table_message_id = message.id
    if old_message_id is not None:
        await delete_rummy_table_message(session, old_message_id)


async def delete_rummy_table_message(session: RummySession, message_id: int) -> None:
    channel = get_client().get_channel(session.channel_id)
    if not hasattr(channel, "fetch_message"):
        return
    try:
        await (await channel.fetch_message(message_id)).delete()
    except (discord.Forbidden, discord.HTTPException, discord.NotFound):
        return


async def update_rummy_table_from_interaction(interaction: discord.Interaction, session: RummySession) -> None:
    if not interaction.response.is_done():
        await interaction.response.defer()
    await refresh_rummy_table_message(session)


class RummyModeSelect(discord.ui.Select):
    def __init__(self, channel_id: int) -> None:
        self.channel_id = channel_id
        session = get_rummy_session(channel_id)
        super().__init__(placeholder="Pilih mode permainan", options=[
            discord.SelectOption(label="Regular", value="regular", default=not session.is_tournament),
            discord.SelectOption(label="Tournament", value="tournament", default=session.is_tournament),
        ])

    async def callback(self, interaction: discord.Interaction) -> None:
        try:
            session = get_rummy_session(self.channel_id)
            require_rummy_player(session, interaction.user.id)
            if session.game.status != RummyStatus.WAITING:
                raise RummyGameError("Mode hanya bisa diubah saat lobby belum mulai.")
            session.mode = self.values[0]
            if not session.is_tournament:
                session.tournament_scores.clear()
                session.tournament_scored_rounds.clear()
            await update_rummy_table_from_interaction(interaction, session)
        except RummyGameError as error:
            await reply_error(interaction, error)


class RummyRoundSelect(discord.ui.Select):
    def __init__(self, channel_id: int) -> None:
        self.channel_id = channel_id
        super().__init__(placeholder="Pilih jumlah ronde", options=[discord.SelectOption(label=f"{count} ronde", value=str(count)) for count in range(3, 21)])

    async def callback(self, interaction: discord.Interaction) -> None:
        try:
            session = get_rummy_session(self.channel_id)
            require_rummy_player(session, interaction.user.id)
            if not session.is_tournament or session.game.status != RummyStatus.WAITING:
                raise RummyGameError("Jumlah ronde hanya bisa diubah di lobby tournament.")
            session.tournament_total_rounds = int(self.values[0])
            await update_rummy_table_from_interaction(interaction, session)
        except RummyGameError as error:
            await reply_error(interaction, error)


class RummyLobbyView(discord.ui.View):
    def __init__(self, channel_id: int) -> None:
        super().__init__(timeout=None)
        self.channel_id = channel_id
        session = get_rummy_session(channel_id)
        self.add_item(RummyModeSelect(channel_id))
        if session.is_tournament:
            self.add_item(RummyRoundSelect(channel_id))

    @discord.ui.button(label="Ikut Main", style=discord.ButtonStyle.success)
    async def join_game(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session = get_rummy_session(self.channel_id)
            session.game.add_player(interaction.user.id, interaction.user.display_name)
            await update_rummy_table_from_interaction(interaction, session)
        except RummyGameError as error:
            await reply_error(interaction, error)

    @discord.ui.button(label="Mulai Game", style=discord.ButtonStyle.primary)
    async def start_game(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session = get_rummy_session(self.channel_id)
            session.add_log(session.start_rummy_round())
            await update_rummy_table_from_interaction(interaction, session)
        except RummyGameError as error:
            await reply_error(interaction, error)

    @discord.ui.button(label="Tutup Lobby", style=discord.ButtonStyle.danger)
    async def close_lobby(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session = get_rummy_session(self.channel_id)
            require_rummy_player(session, interaction.user.id)
            rummy_sessions_by_channel.pop(self.channel_id, None)
            await interaction.response.edit_message(content=f"**Rummy ditutup** oleh {interaction.user.mention}.", embed=None, attachments=[], view=None)
        except RummyGameError as error:
            await reply_error(interaction, error)


class RummyGameView(discord.ui.View):
    def __init__(self, channel_id: int) -> None:
        super().__init__(timeout=None)
        self.channel_id = channel_id

    @discord.ui.button(label="Lihat / Buang Kartu", style=discord.ButtonStyle.primary)
    async def show_hand(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session = get_rummy_session(self.channel_id)
            session.game.hand_for(interaction.user.id)
            await interaction.response.defer(ephemeral=True, thinking=True)
            embed, files = await asyncio.to_thread(rummy_hand_visuals, session.game, interaction.user.id)
            await interaction.followup.send(rummy_hand_text(session.game, interaction.user.id), embed=embed, files=files, view=RummyHandView(self.channel_id, interaction.user.id), ephemeral=True)
        except RummyGameError as error:
            await reply_error(interaction, error)

    @discord.ui.button(label="Ambil Deck", style=discord.ButtonStyle.secondary)
    async def draw_deck(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session = get_rummy_session(self.channel_id)
            add_action_log(session, session.game.draw_from_deck(interaction.user.id).public_messages)
            await update_rummy_table_from_interaction(interaction, session)
        except RummyGameError as error:
            await reply_error(interaction, error)

    @discord.ui.button(label="Ambil Buangan", style=discord.ButtonStyle.secondary)
    async def draw_discard(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session = get_rummy_session(self.channel_id)
            require_rummy_player(session, interaction.user.id)
            await interaction.response.send_message("Pilih target dari maksimal 3 kartu buangan teratas. Ambil 1-3 wajib meld bukti 3 kartu: kartu target dan minimal 2 kartu tangan sebelumnya. Kartu di atas target bebas disimpan atau dibuang lagi:", view=RummyDiscardView(self.channel_id, interaction.user.id), ephemeral=True)
        except RummyGameError as error:
            await reply_error(interaction, error)

    @discord.ui.button(label="Refresh Meja", style=discord.ButtonStyle.secondary, row=1)
    async def refresh(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await update_rummy_table_from_interaction(interaction, get_rummy_session(self.channel_id))

    @discord.ui.button(label="Vote End Game", style=discord.ButtonStyle.danger, row=1)
    async def vote_end(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session = get_rummy_session(self.channel_id)
            votes, required, approved = session.add_end_vote(interaction.user.id)
            if approved:
                session.game.status = RummyStatus.FINISHED
                session.game.scores = {player.user_id: 0 for player in session.game.players}
                session.add_log(f"Vote end game disetujui {votes}/{required}. Game diakhiri.")
            await update_rummy_table_from_interaction(interaction, session)
        except RummyGameError as error:
            await reply_error(interaction, error)


class RummyDiscardSelect(discord.ui.Select):
    def __init__(self, channel_id: int, user_id: int) -> None:
        self.channel_id, self.user_id = channel_id, user_id
        game = get_rummy_session(channel_id).game
        options = [
            discord.SelectOption(label=f"{depth}. {card.label}{self._discarded_by_name(game, user_id)}"[:100], value=str(depth))
            for depth, (card, user_id) in enumerate(game.visible_discard_details(), 1)
        ]
        super().__init__(placeholder="Pilih kartu buangan", options=options or [discord.SelectOption(label="Tidak ada buangan", value="empty")])

    @staticmethod
    def _discarded_by_name(game, user_id: int | None) -> str:
        player = game.get_player(user_id) if user_id is not None else None
        return f" - dari {player.name}" if player is not None else ""

    async def callback(self, interaction: discord.Interaction) -> None:
        try:
            if interaction.user.id != self.user_id or self.values[0] == "empty":
                raise RummyGameError("Tidak ada kartu buangan yang bisa dipilih.")
            session = get_rummy_session(self.channel_id)
            result = session.game.draw_from_discard(self.user_id, int(self.values[0]))
            add_action_log(session, result.public_messages)
            await interaction.response.edit_message(content="\n".join(result.public_messages), view=None)
            await refresh_rummy_table_message(session)
        except RummyGameError as error:
            await reply_error(interaction, error)


class RummyDiscardView(discord.ui.View):
    def __init__(self, channel_id: int, user_id: int) -> None:
        super().__init__(timeout=60)
        self.add_item(RummyDiscardSelect(channel_id, user_id))


class RummyHandSelect(discord.ui.Select):
    def __init__(self, channel_id: int, user_id: int, selected_numbers: set[int]) -> None:
        self.channel_id, self.user_id = channel_id, user_id
        cards = get_rummy_session(channel_id).game.hand_for(user_id)
        options = [
            discord.SelectOption(label=f"{index}. {card.label}"[:100], value=str(index), default=index in selected_numbers)
            for index, card in enumerate(cards[:25], 1)
        ]
        if not options:
            options = [discord.SelectOption(label="Tidak ada kartu", value="empty")]
        super().__init__(placeholder="Pilih kartu buang atau meld", min_values=1, max_values=len(options), options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        try:
            if interaction.user.id != self.user_id:
                raise RummyGameError("Ini panel kartu pemain lain.")
            if self.values[0] == "empty":
                raise RummyGameError("Tidak ada kartu yang bisa dipilih.")
            session = get_rummy_session(self.channel_id)
            selected = {int(value) for value in self.values}
            await interaction.response.defer()
            embed, files = await asyncio.to_thread(rummy_hand_visuals, session.game, self.user_id, 0, 25, selected)
            await interaction.edit_original_response(content=rummy_hand_text(session.game, self.user_id, selected_numbers=selected), embed=embed, attachments=files, view=RummyHandView(self.channel_id, self.user_id, selected))
        except RummyGameError as error:
            await reply_error(interaction, error)


class RummyHandView(discord.ui.View):
    def __init__(self, channel_id: int, user_id: int, selected_numbers: set[int] | None = None) -> None:
        super().__init__(timeout=180)
        self.channel_id, self.user_id = channel_id, user_id
        self.selected_numbers = selected_numbers or set()
        self.add_item(RummyHandSelect(channel_id, user_id, self.selected_numbers))

    async def _discard(self, interaction: discord.Interaction, close: bool) -> None:
        try:
            if interaction.user.id != self.user_id or len(self.selected_numbers) != 1:
                raise RummyGameError("Pilih tepat 1 kartu untuk dibuang.")
            session = get_rummy_session(self.channel_id)
            result = session.game.discard_card(self.user_id, next(iter(self.selected_numbers)), close)
            add_action_log(session, result.public_messages)
            await interaction.response.edit_message(content="\n".join(result.public_messages), embed=None, attachments=[], view=None)
            await refresh_rummy_table_message(session)
        except RummyGameError as error:
            await reply_error(interaction, error)

    @discord.ui.button(label="Buang Kartu", style=discord.ButtonStyle.primary, row=1)
    async def discard(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._discard(interaction, False)

    @discord.ui.button(label="Closed Card", style=discord.ButtonStyle.success, row=1)
    async def close(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._discard(interaction, True)

    @discord.ui.button(label="Turunkan Meld", style=discord.ButtonStyle.secondary, row=1)
    async def lay_down_meld(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            if interaction.user.id != self.user_id:
                raise RummyGameError("Ini panel kartu pemain lain.")
            session = get_rummy_session(self.channel_id)
            result = session.game.lay_down_meld(self.user_id, sorted(self.selected_numbers))
            add_action_log(session, result.public_messages)
            await interaction.response.edit_message(content="\n".join(result.public_messages), embed=None, attachments=[], view=None)
            await refresh_rummy_table_message(session)
        except RummyGameError as error:
            await reply_error(interaction, error)

    @discord.ui.button(label="Gabungkan Meld", style=discord.ButtonStyle.secondary, row=2)
    async def lay_off_cards(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            if interaction.user.id != self.user_id:
                raise RummyGameError("Ini panel kartu pemain lain.")
            if not self.selected_numbers:
                raise RummyGameError("Pilih minimal 1 kartu untuk digabungkan.")
            session = get_rummy_session(self.channel_id)
            if not any(player.opened_melds for player in session.game.players):
                raise RummyGameError("Belum ada meld terbuka yang bisa digabungkan.")
            await interaction.response.send_message(
                "Pilih meld terbuka yang akan menerima kartu pilihanmu:",
                view=RummyLayOffView(self.channel_id, self.user_id, self.selected_numbers),
                ephemeral=True,
            )
        except RummyGameError as error:
            await reply_error(interaction, error)


class RummyLayOffSelect(discord.ui.Select):
    def __init__(self, channel_id: int, user_id: int, selected_numbers: set[int]) -> None:
        self.channel_id, self.user_id, self.selected_numbers = channel_id, user_id, selected_numbers
        session = get_rummy_session(channel_id)
        options = []
        for player in session.game.players:
            for meld_index, meld in enumerate(player.opened_melds):
                label = f"{player.name}: {', '.join(card.label for card in meld)}"
                options.append(discord.SelectOption(label=label[:100], value=f"{player.user_id}:{meld_index}"))
        super().__init__(placeholder="Pilih meld target", options=options[:25])

    async def callback(self, interaction: discord.Interaction) -> None:
        try:
            if interaction.user.id != self.user_id:
                raise RummyGameError("Ini panel gabungan meld pemain lain.")
            target_user_id, meld_index = (int(value) for value in self.values[0].split(":"))
            session = get_rummy_session(self.channel_id)
            result = session.game.lay_off_cards(
                self.user_id,
                target_user_id,
                meld_index,
                sorted(self.selected_numbers),
            )
            add_action_log(session, result.public_messages)
            await interaction.response.edit_message(content="\n".join(result.public_messages), view=None)
            await refresh_rummy_table_message(session)
        except RummyGameError as error:
            await reply_error(interaction, error)


class RummyLayOffView(discord.ui.View):
    def __init__(self, channel_id: int, user_id: int, selected_numbers: set[int]) -> None:
        super().__init__(timeout=60)
        self.add_item(RummyLayOffSelect(channel_id, user_id, selected_numbers))


class RummyFinishedView(discord.ui.View):
    def __init__(self, channel_id: int) -> None:
        super().__init__(timeout=None)
        self.channel_id = channel_id

    @discord.ui.button(label="Buat Lobby Baru", style=discord.ButtonStyle.success)
    async def new_lobby(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        session = RummySession(self.channel_id, interaction.user.id)
        session.game.add_player(interaction.user.id, interaction.user.display_name)
        old = rummy_sessions_by_channel.get(self.channel_id)
        session.table_message_id = old.table_message_id if old else None
        rummy_sessions_by_channel[self.channel_id] = session
        await update_rummy_table_from_interaction(interaction, session)


class RummyTournamentRoundFinishedView(discord.ui.View):
    def __init__(self, channel_id: int) -> None:
        super().__init__(timeout=None)
        self.channel_id = channel_id

    @discord.ui.button(label="Mulai Ronde Berikutnya", style=discord.ButtonStyle.success)
    async def next_round(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session = get_rummy_session(self.channel_id)
            require_rummy_player(session, interaction.user.id)
            session.add_log(session.start_next_tournament_round())
            await update_rummy_table_from_interaction(interaction, session)
        except RummyGameError as error:
            await reply_error(interaction, error)
