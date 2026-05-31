"""Discord client events and slash command handlers."""

from __future__ import annotations

import asyncio
import os

import discord
from discord import app_commands

from poker.game import PokerGameError, PokerStatus
from rummy.game import RummyGameError, RummyStatus
from uno.game import GameStatus, UnoGameError

from .changelog import format_changelog_entry, format_public_changelog_entry, latest_changelog_entry, semver_tuple
from .client import bot, tree
from .constants import APP_VERSION, COLOR_CHOICES, POKER_MODE_CHOICES, RUMMY_MODE_CHOICES
from .presentation.poker import poker_hand_text, poker_hand_visuals, poker_table_text, poker_table_visuals
from .presentation.rummy import rummy_hand_text, rummy_hand_visuals, rummy_table_text, rummy_table_visuals
from .presentation.uno import hand_text, hand_visuals, table_text, table_visuals
from .sessions import PokerSession, RummySession, UnoSession, get_poker_session, get_rummy_session, get_session, require_channel_id
from .state import changelog_seen_versions_by_user, poker_sessions_by_channel, rummy_sessions_by_channel, sessions_by_channel
from .ui.common import reply_error
from .ui.poker import PokerHandView, poker_table_view, refresh_poker_table_message
from .ui.rummy import RummyHandView, refresh_rummy_table_message, rummy_table_view
from .ui.uno import HandView, add_result_log, refresh_table_message, table_view


commands_synced = False


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


@tree.command(name="changelog", description="Cek changelog terbaru CardBot.")
async def changelog(interaction: discord.Interaction) -> None:
    latest = latest_changelog_entry()
    latest_version = str(latest["version"])
    seen_version = changelog_seen_versions_by_user.get(interaction.user.id)

    if seen_version is not None and semver_tuple(seen_version) >= semver_tuple(latest_version):
        await interaction.response.send_message(
            f"Tidak ada changelog baru. Versi saat ini: **v{APP_VERSION}**.",
            ephemeral=True,
        )
        return

    changelog_seen_versions_by_user[interaction.user.id] = latest_version
    await interaction.response.send_message(format_changelog_entry(latest), ephemeral=True)


@tree.command(name="publish-changelog", description="Kirim changelog terbaru ke channel sebagai bot.")
@app_commands.default_permissions(manage_guild=True)
@app_commands.describe(
    channel="Channel tujuan. Kosongkan untuk memakai channel ini.",
    mention_everyone="Aktifkan jika ingin ping @everyone.",
)
async def publish_changelog(
    interaction: discord.Interaction,
    channel: discord.TextChannel | None = None,
    mention_everyone: bool = False,
) -> None:
    if interaction.guild is None:
        await interaction.response.send_message("Command ini hanya bisa dipakai di server.", ephemeral=True)
        return

    user_permissions = getattr(interaction.user, "guild_permissions", None)
    if user_permissions is None or not user_permissions.manage_guild:
        await interaction.response.send_message(
            "Kamu perlu permission **Manage Server** untuk publish changelog.",
            ephemeral=True,
        )
        return

    destination = channel or interaction.channel
    if not isinstance(destination, discord.TextChannel):
        await interaction.response.send_message(
            "Pilih text/announcement channel sebagai tujuan changelog.",
            ephemeral=True,
        )
        return

    latest = latest_changelog_entry()
    await interaction.response.defer(ephemeral=True, thinking=True)
    bot_member = interaction.guild.me
    if bot_member is None and bot.user is not None:
        bot_member = interaction.guild.get_member(bot.user.id)
    if bot_member is None:
        await interaction.followup.send("Bot member tidak ditemukan di server ini.", ephemeral=True)
        return

    bot_permissions = destination.permissions_for(bot_member)
    if not bot_permissions.send_messages:
        await interaction.followup.send(
            f"Bot belum punya permission **Send Messages** di {destination.mention}.",
            ephemeral=True,
        )
        return
    if mention_everyone and not bot_permissions.mention_everyone:
        await interaction.followup.send(
            f"Bot belum punya permission **Mention Everyone** di {destination.mention}.",
            ephemeral=True,
        )
        return

    try:
        message = await asyncio.wait_for(
            destination.send(
                format_public_changelog_entry(latest, mention_everyone),
                allowed_mentions=discord.AllowedMentions(everyone=mention_everyone),
            ),
            timeout=15,
        )
    except TimeoutError:
        await interaction.followup.send(
            "Bot terlalu lama saat mencoba mengirim changelog. Coba lagi atau cek koneksi host bot.",
            ephemeral=True,
        )
        return
    except discord.Forbidden:
        await interaction.followup.send(
            f"Discord menolak pesan ke {destination.mention}. Cek permission bot di channel itu.",
            ephemeral=True,
        )
        return
    except discord.HTTPException as error:
        await interaction.followup.send(
            f"Gagal mengirim changelog: `{error}`",
            ephemeral=True,
        )
        return

    reaction_error = not bot_permissions.add_reactions
    if not reaction_error:
        for emoji in ("\U0001f525", "\U0001f44d", "\u2764\ufe0f"):
            try:
                await asyncio.wait_for(message.add_reaction(emoji), timeout=5)
            except (TimeoutError, discord.HTTPException):
                reaction_error = True
                break

    note = " Reaksi default gagal ditambahkan; cek permission **Add Reactions**." if reaction_error else ""
    await interaction.followup.send(
        f"Changelog v{latest['version']} sudah dikirim ke {destination.mention}.{note}",
        ephemeral=True,
    )


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
        session.game.hand_for(interaction.user.id)
        await interaction.response.defer(ephemeral=True, thinking=True)
        embed, files = await asyncio.to_thread(poker_hand_visuals, session.game, interaction.user.id)
        await interaction.followup.send(
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


@tree.command(name="rummy-start", description="Tampilkan meja Rummy interaktif di channel ini.")
@app_commands.describe(
    mode="Pilih regular untuk 1 game atau tournament untuk multi-round.",
    rounds="Jumlah ronde tournament, minimal 3 dan maksimal 20.",
)
@app_commands.choices(mode=RUMMY_MODE_CHOICES)
async def rummy_start(
    interaction: discord.Interaction,
    mode: str = "regular",
    rounds: app_commands.Range[int, 3, 20] = 3,
) -> None:
    try:
        channel_id = require_channel_id(interaction)
        existing = rummy_sessions_by_channel.get(channel_id)
        if existing and (existing.game.status != RummyStatus.FINISHED or existing.tournament_between_rounds):
            raise RummyGameError("Sudah ada meja Rummy aktif di channel ini.")
        session = RummySession(channel_id, interaction.user.id, mode=mode, tournament_total_rounds=rounds)
        session.game.add_player(interaction.user.id, interaction.user.display_name)
        session.add_log(f"Lobby Rummy dibuat oleh {interaction.user.display_name}.")
        rummy_sessions_by_channel[channel_id] = session
        embed, files = rummy_table_visuals(session)
        await interaction.response.send_message(rummy_table_text(session), embed=embed, files=files, view=rummy_table_view(session))
        session.table_message_id = (await interaction.original_response()).id
    except RummyGameError as error:
        await reply_error(interaction, error)


@tree.command(name="rummy-hand", description="Fallback: lihat kartu Rummy tanganmu secara private.")
async def rummy_hand(interaction: discord.Interaction) -> None:
    try:
        session = get_rummy_session(interaction.channel_id)
        embed, files = await asyncio.to_thread(rummy_hand_visuals, session.game, interaction.user.id)
        await interaction.response.send_message(
            rummy_hand_text(session.game, interaction.user.id),
            embed=embed,
            files=files,
            view=RummyHandView(session.channel_id, interaction.user.id),
            ephemeral=True,
        )
    except RummyGameError as error:
        await reply_error(interaction, error)


@tree.command(name="rummy-status", description="Fallback: refresh status meja Rummy.")
async def rummy_status(interaction: discord.Interaction) -> None:
    try:
        session = get_rummy_session(interaction.channel_id)
        await refresh_rummy_table_message(session)
        await interaction.response.send_message("Meja Rummy direfresh.", ephemeral=True)
    except RummyGameError as error:
        await reply_error(interaction, error)
