"""Shared Discord UI error response helper."""

from __future__ import annotations

import discord

from poker.game import PokerGameError


async def reply_error(interaction: discord.Interaction, error: Exception) -> None:
    prefix = "Remi Poker" if isinstance(error, PokerGameError) else "UNO"
    message = f"{prefix}: {error}"
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)
