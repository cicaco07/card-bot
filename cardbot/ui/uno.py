"""Discord UI and message lifecycle for UNO."""

from __future__ import annotations

import discord

from uno.game import GameStatus, UnoGameError

from ..presentation.uno import hand_text, hand_visuals, table_text, table_visuals
from ..sessions import UnoSession, get_session, require_session_player
from ..state import get_client, sessions_by_channel
from .common import reply_error
from .log_utils import add_action_log


def table_view(session: UnoSession) -> discord.ui.View:
    if session.game.status == GameStatus.WAITING:
        return LobbyView(session.channel_id)
    if session.game.status == GameStatus.FINISHED:
        return FinishedView(session.channel_id)
    return GameView(session.channel_id)


async def refresh_table_message(session: UnoSession) -> None:
    await repost_table_message(session)


async def repost_table_message(session: UnoSession) -> None:
    channel = get_client().get_channel(session.channel_id)
    if not hasattr(channel, "send"):
        return

    old_message_id = session.table_message_id
    embed, files = table_visuals(session)
    message = await channel.send(content=table_text(session), view=table_view(session), embed=embed, files=files)
    session.table_message_id = message.id

    if old_message_id is not None:
        await delete_table_message(session, old_message_id)


async def delete_table_message(session: UnoSession, message_id: int) -> None:
    channel = get_client().get_channel(session.channel_id)
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


def add_result_log(session: UnoSession, messages: list[str]) -> None:
    add_action_log(session, messages)


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
            channel = get_client().get_channel(session.channel_id)
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
