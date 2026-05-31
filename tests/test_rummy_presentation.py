from __future__ import annotations

import asyncio
from types import SimpleNamespace

from cardbot.presentation.rummy import rummy_lobby_text, rummy_state_text
from cardbot.sessions import RummySession
from cardbot.ui.common import reply_error
from rummy.cards import RummyCard
from rummy.game import RummyGameError, RummyPlayer, RummyStatus


def test_rummy_lobby_and_playing_text() -> None:
    session = RummySession(channel_id=10, owner_id=99)
    assert rummy_lobby_text(session) == (
        "**Rummy: Lobby**\nBuat meld run atau set, lalu raih skor tertinggi.\n\n"
        "Owner: <@99>\nMode: **Regular**\nPemain (0/4):\nBelum ada pemain."
    )
    session.game.status = RummyStatus.PLAYING
    session.game.players = [
        RummyPlayer(1, "Alice", [RummyCard("2", "hearts")]),
        RummyPlayer(2, "Bob", [RummyCard("3", "clubs")]),
    ]
    session.game.deck = [RummyCard("4", "diamonds")]
    session.log = ["Game dimulai."]
    assert rummy_state_text(session) == (
        "**Rummy: Game Berjalan**\nGilirannya: <@1>\nFase giliran: **ambil kartu**\n"
        "Sisa deck: **1 kartu**\nKartu buangan teratas: **Belum ada**\nTotal buangan: 0\n\n"
        "Jumlah kartu pemain:\n- <@1>: 1 kartu\n- <@2>: 1 kartu\n\n"
        "Vote akhiri game: **0/2 setuju**\n\nAksi terakhir:\n- Game dimulai."
    )


def test_rummy_reply_error_prefix() -> None:
    sent: list[str] = []

    class Response:
        def is_done(self) -> bool:
            return False

        async def send_message(self, message: str, ephemeral: bool) -> None:
            sent.append(message)

    asyncio.run(reply_error(SimpleNamespace(response=Response()), RummyGameError("contoh")))
    assert sent == ["Rummy: contoh"]
