"""CardBot application entry point."""

from __future__ import annotations

import os

from dotenv import load_dotenv

from .client import bot
from .state import set_client


def main() -> None:
    load_dotenv()
    set_client(bot)
    from . import commands as _commands  # noqa: F401

    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN belum diisi. Salin .env.example menjadi .env lalu isi token bot.")
    bot.run(token)
