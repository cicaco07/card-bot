from __future__ import annotations

from dataclasses import dataclass, field
import os

import discord
from discord import app_commands
from dotenv import load_dotenv

from uno.game import COLOR_LABELS, GameStatus, UnoGame, UnoGameError


load_dotenv()


intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)
sessions_by_channel: dict[int, "UnoSession"] = {}
commands_synced = False


COLOR_CHOICES = [
    app_commands.Choice(name="Merah", value="red"),
    app_commands.Choice(name="Kuning", value="yellow"),
    app_commands.Choice(name="Hijau", value="green"),
    app_commands.Choice(name="Biru", value="blue"),
]


@dataclass
class UnoSession:
    channel_id: int
    owner_id: int
    game: UnoGame = field(default_factory=UnoGame)
    table_message_id: int | None = None
    log: list[str] = field(default_factory=list)

    def add_log(self, messages: list[str] | str) -> None:
        if isinstance(messages, str):
            messages = [messages]
        self.log.extend(messages)
        self.log = self.log[-8:]


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


def mention(user_id: int) -> str:
    return f"<@{user_id}>"


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
    log_text = "\n".join(f"- {message}" for message in session.log[-5:]) or "- Belum ada aksi."
    return (
        "**UNO Table: Game Berjalan**\n"
        f"Top card: **{state['top_card']}**\n"
        f"Warna aktif: **{state['current_color']}**\n"
        f"Gilirannya: {mention(state['current_player_id'])}\n"
        f"Arah: {state['direction']}\n"
        f"Sisa deck: {state['deck_count']} kartu\n\n"
        f"Jumlah kartu pemain:\n{hand_counts}\n\n"
        f"Log terakhir:\n{log_text}"
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
    playable = set(game.playable_cards_for(user_id))
    total_pages = max(1, (len(cards) + page_size - 1) // page_size)
    start = page * page_size
    shown_cards = cards[start : start + page_size]

    lines = [
        "**Kartu tanganmu**",
        f"Halaman {page + 1}/{total_pages}. Kartu bertanda `bisa` cocok dengan meja saat ini.",
        "",
    ]
    for offset, card in enumerate(shown_cards, start=start + 1):
        marker = "bisa" if offset - 1 in playable else "tahan"
        lines.append(f"{offset}. {card.label} ({marker})")
    return "\n".join(lines) if shown_cards else "Tanganmu kosong."


async def reply_error(interaction: discord.Interaction, error: Exception) -> None:
    message = f"UNO: {error}"
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


async def refresh_table_message(session: UnoSession) -> None:
    if session.table_message_id is None:
        return
    channel = bot.get_channel(session.channel_id)
    if not hasattr(channel, "fetch_message"):
        return
    message = await channel.fetch_message(session.table_message_id)
    await message.edit(content=table_text(session), view=table_view(session))


async def edit_table_from_interaction(interaction: discord.Interaction, session: UnoSession) -> None:
    content = table_text(session)
    view = table_view(session)

    if interaction.message and interaction.message.id == session.table_message_id:
        if interaction.response.is_done():
            await interaction.message.edit(content=content, view=view)
        else:
            await interaction.response.edit_message(content=content, view=view)
        return

    await refresh_table_message(session)


def add_result_log(session: UnoSession, messages: list[str]) -> None:
    clean_messages = [message for message in messages if message]
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
            await edit_table_from_interaction(interaction, session)
        except UnoGameError as error:
            await reply_error(interaction, error)

    @discord.ui.button(label="Mulai Game", style=discord.ButtonStyle.primary)
    async def begin_game(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session = get_session(self.channel_id)
            messages = session.game.start()
            session.add_log(messages)
            await edit_table_from_interaction(interaction, session)
        except UnoGameError as error:
            await reply_error(interaction, error)

    @discord.ui.button(label="Tutup Lobby", style=discord.ButtonStyle.danger)
    async def close_lobby(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session = get_session(self.channel_id)
            sessions_by_channel.pop(self.channel_id, None)
            content = f"**UNO Table ditutup** oleh {interaction.user.mention}."
            if interaction.response.is_done():
                await interaction.followup.send(content)
            else:
                await interaction.response.edit_message(content=content, view=None)
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
            await edit_table_from_interaction(interaction, session)
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
            await interaction.response.send_message(
                hand_text(session.game, interaction.user.id),
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
            await edit_table_from_interaction(interaction, session)
            await interaction.followup.send("\n".join(result.public_messages), ephemeral=True)
        except UnoGameError as error:
            await reply_error(interaction, error)

    @discord.ui.button(label="Pass", style=discord.ButtonStyle.secondary)
    async def pass_turn(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session = get_session(self.channel_id)
            result = session.game.pass_turn(interaction.user.id)
            add_result_log(session, result.public_messages)
            await edit_table_from_interaction(interaction, session)
            await interaction.followup.send("\n".join(result.public_messages), ephemeral=True)
        except UnoGameError as error:
            await reply_error(interaction, error)

    @discord.ui.button(label="Refresh Meja", style=discord.ButtonStyle.secondary, row=1)
    async def refresh(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session = get_session(self.channel_id)
            await edit_table_from_interaction(interaction, session)
        except UnoGameError as error:
            await reply_error(interaction, error)

    @discord.ui.button(label="Akhiri Game", style=discord.ButtonStyle.danger, row=1)
    async def end_game(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        try:
            session = get_session(self.channel_id)
            session.game.status = GameStatus.FINISHED
            session.add_log(f"Game diakhiri oleh {interaction.user.display_name}.")
            await edit_table_from_interaction(interaction, session)
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
                    view=ColorPickView(self.channel_id, self.user_id, card_number),
                )
                return

            result = session.game.play_card(self.user_id, card_number)
            add_result_log(session, result.public_messages)
            await refresh_table_message(session)
            await interaction.response.edit_message(content="\n".join(result.public_messages), view=None)
        except UnoGameError as error:
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
            await interaction.response.edit_message(
                content=hand_text(session.game, self.user_id, page, self.page_size),
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
            await interaction.response.edit_message(
                content=hand_text(session.game, self.user_id, self.page, self.page_size),
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
            await interaction.response.edit_message(
                content=hand_text(session.game, self.user_id, page, self.page_size),
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
            await refresh_table_message(session)
            await interaction.response.edit_message(content="\n".join(result.public_messages), view=None)
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

        await interaction.response.send_message(table_text(session), view=table_view(session))
        message = await interaction.original_response()
        session.table_message_id = message.id
    except UnoGameError as error:
        await reply_error(interaction, error)


@tree.command(name="uno_hand", description="Fallback: lihat kartu tanganmu secara private.")
async def uno_hand(interaction: discord.Interaction) -> None:
    try:
        session = get_session(interaction.channel_id)
        await interaction.response.send_message(
            hand_text(session.game, interaction.user.id),
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


def main() -> None:
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN belum diisi. Salin .env.example menjadi .env lalu isi token bot.")
    bot.run(token)


if __name__ == "__main__":
    main()
