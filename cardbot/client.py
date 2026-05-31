"""Discord client and slash-command tree."""

import discord
from discord import app_commands


intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)
