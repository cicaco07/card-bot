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
            embed, files = await asyncio.to_thread(rummy_hand_visuals, session.game, interaction.user.id)
            await interaction.response.send_message(rummy_hand_text(session.game, interaction.user.id), embed=embed, files=files, view=RummyHandView(self.channel_id, interaction.user.id), ephemeral=True)
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
            await interaction.response.send_message("Pilih salah satu dari maksimal 7 kartu buangan teratas:", view=RummyDiscardView(self.channel_id, interaction.user.id), ephemeral=True)
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
        discards = get_rummy_session(channel_id).game.visible_discards()
        options = [discord.SelectOption(label=f"{depth}. {card.label}"[:100], value=str(depth)) for depth, card in enumerate(discards, 1)]
        super().__init__(placeholder="Pilih kartu buangan", options=options or [discord.SelectOption(label="Tidak ada buangan", value="empty")])

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
    def __init__(self, channel_id: int, user_id: int, selected_number: int | None = None) -> None:
        self.channel_id, self.user_id = channel_id, user_id
        cards = get_rummy_session(channel_id).game.hand_for(user_id)
        super().__init__(placeholder="Pilih kartu untuk dibuang", options=[
            discord.SelectOption(label=f"{index}. {card.label}"[:100], value=str(index), default=index == selected_number)
            for index, card in enumerate(cards, 1)
        ])

    async def callback(self, interaction: discord.Interaction) -> None:
        try:
            if interaction.user.id != self.user_id:
                raise RummyGameError("Ini panel kartu pemain lain.")
            session = get_rummy_session(self.channel_id)
            selected = int(self.values[0])
            embed, files = await asyncio.to_thread(rummy_hand_visuals, session.game, self.user_id, 0, 25, selected)
            await interaction.response.edit_message(content=rummy_hand_text(session.game, self.user_id, selected_number=selected), embed=embed, attachments=files, view=RummyHandView(self.channel_id, self.user_id, selected))
        except RummyGameError as error:
            await reply_error(interaction, error)


class RummyHandView(discord.ui.View):
    def __init__(self, channel_id: int, user_id: int, selected_number: int | None = None) -> None:
        super().__init__(timeout=180)
        self.channel_id, self.user_id, self.selected_number = channel_id, user_id, selected_number
        self.add_item(RummyHandSelect(channel_id, user_id, selected_number))

    async def _discard(self, interaction: discord.Interaction, close: bool) -> None:
        try:
            if interaction.user.id != self.user_id or self.selected_number is None:
                raise RummyGameError("Pilih kartu terlebih dahulu.")
            session = get_rummy_session(self.channel_id)
            result = session.game.discard_card(self.user_id, self.selected_number, close)
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
