from __future__ import annotations

import asyncio
from types import SimpleNamespace

from cardbot.presentation.rummy import rummy_finished_text, rummy_lobby_text, rummy_state_text
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
        "Kewajiban meld buangan: **Tidak ada**\n"
        "Sisa deck: **1 kartu**\nKartu buangan teratas: **Belum ada**\nTotal buangan: 0\n"
        "3 buangan teratas:\n- Belum ada\n\n"
        "Meld terbuka dan terkunci:\n- Belum ada meld yang diturunkan.\n\n"
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


def test_rummy_playing_text_shows_discarding_players() -> None:
    session = RummySession(channel_id=10, owner_id=99)
    session.game.status = RummyStatus.PLAYING
    session.game.players = [
        RummyPlayer(1, "Alice", [RummyCard("2", "hearts")]),
        RummyPlayer(
            2,
            "Bob",
            [RummyCard("3", "clubs")],
            opened_melds=[(RummyCard("J", "hearts"), RummyCard("Q", "hearts"), RummyCard("K", "hearts"))],
        ),
    ]
    session.game.discard_pile = [RummyCard("4", "diamonds"), RummyCard("5", "clubs")]
    session.game.discarded_by_user_ids = [1, 2]
    session.game.flip_source_cards_by_user_id = {1: [RummyCard("A", "spades")]}
    text = rummy_state_text(session)
    assert "Kartu buangan teratas: **5 ♣️** - dibuang oleh <@2>" in text
    assert "3 buangan teratas:\n- 1. 5 ♣️ - dibuang oleh <@2>\n- 2. 4 ♦️ - dibuang oleh <@1>" in text
    assert "Meld terbuka dan terkunci:\n- <@2>: [J ♥️, Q ♥️, K ♥️]" in text
    assert "flip card" not in text


def test_rummy_finished_text_shows_score_breakdown() -> None:
    session = RummySession(channel_id=10, owner_id=99)
    session.game.status = RummyStatus.FINISHED
    session.game.players = [RummyPlayer(1, "Alice")]
    session.game.scores = {1: -10}
    session.game.closed_card = RummyCard("2", "spades")
    session.game.flip_source_cards_by_user_id = {1: [RummyCard("J", "clubs")]}
    session.game.score_breakdowns = {
        1: {
            "opened_meld_points": 30,
            "opened_melds": [["J ♥️", "Q ♥️", "K ♥️"]],
            "hand_meld_points": 15,
            "hand_melds": [["3 ♣️", "4 ♣️", "5 ♣️"]],
            "deadwood_points": 5,
            "deadwood_cards": ["9 ♦️"],
            "flip_penalty_points": 50,
            "flip_cards": ["J ♣️"],
            "flip_penalty_card": "2 ♠️",
            "subtotal": -10,
            "total": -10,
        }
    }
    text = rummy_finished_text(session)
    assert "- <@1>: **-10 point**" in text
    assert "Meld terbuka: +30 point -> (J ♥️, Q ♥️, K ♥️)" in text
    assert "Meld tertutup: +15 point -> (3 ♣️, 4 ♣️, 5 ♣️)" in text
    assert "Deadwood: -5 point -> 9 ♦️" in text
    assert "Penalti flip: -50 point -> 2 ♠️ sebagai closed card; asal buangan yang pernah dijadikan meld bukti: J ♣️" in text
    assert "Total: -10 point" in text
    assert "Penalti flip card:\n- <@1>: J ♣️" in text
