"""Application constants shared by CardBot modules."""

from discord import app_commands


APP_VERSION = "1.0.1"

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
