from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from cardbot.presentation.poker import poker_finished_text, poker_lobby_text, poker_state_text
from cardbot.presentation.uno import finished_text, lobby_text, public_state_text
from cardbot.sessions import PokerSession, UnoSession, get_poker_session, get_session
from cardbot.ui.common import reply_error
from poker.game import PokerCard, PokerStatus
from poker.game import PokerGameError
from uno.game import Card, GameStatus, UnoGameError


def test_uno_presentation_golden() -> None:
    session = UnoSession(channel_id=10, owner_id=99)
    assert lobby_text(session) == (
        "**UNO Table: Lobby**\n"
        "Tekan tombol di bawah untuk ikut bermain. Setelah minimal 2 pemain masuk, tekan **Mulai Game**.\n\n"
        "Owner: <@99>\nPemain (0/10):\nBelum ada pemain."
    )
    session.game.add_player(1, "Alice")
    session.game.add_player(2, "Bob")
    session.game.status = GameStatus.PLAYING
    session.game.players[0].hand = [Card("red", "1")]
    session.game.players[1].hand = [Card("blue", "2"), Card(None, "wild")]
    session.game.discard_pile = [Card("red", "7")]
    session.game.deck = [Card("green", "0")]
    session.game.current_color = "red"
    session.log = ["Alice memainkan Merah 7."]
    assert public_state_text(session) == (
        "**UNO Table: Game Berjalan**\nKartu aktif ada pada gambar di bawah.\nWarna aktif: **Merah**\n"
        "Gilirannya: <@1>\nArah: searah jarum jam\nSisa deck: 1 kartu\n\nJumlah kartu pemain:\n"
        "- <@1>: 1 kartu\n- <@2>: 2 kartu\n\nStatus UNO:\n- Tidak ada.\n\nVote akhiri game: **0/2 setuju**\n\n"
        "Aksi terakhir:\n- Alice memainkan Merah 7."
    )
    session.game.status = GameStatus.FINISHED
    session.log = ["Alice menang."]
    assert finished_text(session) == (
        "**UNO Table: Selesai**\n\nLog akhir:\n- Alice menang.\n\nTekan **Buat Lobby Baru** untuk main lagi."
    )


def test_poker_presentation_golden() -> None:
    session = PokerSession(channel_id=20, owner_id=88)
    assert poker_lobby_text(session) == (
        "**Remi Poker: Lobby**\nMode ini memakai rules Big Two style: habiskan kartu, jangan menjadi loser.\n\n"
        "Owner: <@88>\nMode: **Regular**\nTimer auto-pass: **45 detik**\nPemain (0/4):\nBelum ada pemain."
    )
    session.game.add_player(3, "Cara")
    session.game.add_player(4, "Dedi")
    session.game.status = PokerStatus.PLAYING
    session.game.players[0].hand = [PokerCard("4", "diamonds")]
    session.game.players[1].hand = [PokerCard("5", "clubs"), PokerCard("6", "hearts")]
    session.log = ["Game dimulai."]
    assert poker_state_text(session) == (
        "**Remi Poker: Game Berjalan**\nGilirannya: <@3>\nTimer auto-pass: **45 detik**\nPola ronde: **bebas**\n"
        "Kombinasi terakhir: **Belum ada**\nDimainkan oleh: -\nPass ronde ini: 0\n\nJumlah kartu pemain:\n"
        "- <@3>: 1 kartu\n- <@4>: 2 kartu\n\nWinner sementara: Belum ada\nLoser: Belum ada\n"
        "Vote akhiri game: **0/2 setuju**\n\nAksi terakhir:\n- Game dimulai."
    )
    session.game.status = PokerStatus.FINISHED
    session.game.winner_ids = [3]
    session.game.loser_id = 4
    session.log = ["Dedi kalah."]
    assert poker_finished_text(session) == (
        "**Remi Poker: Selesai**\nWinner: <@3>\nLoser: <@4>\n\nLog akhir:\n- Dedi kalah.\n\n"
        "Tekan **Buat Lobby Baru** untuk main lagi."
    )


def test_guard_errors_keep_indonesian_messages() -> None:
    with pytest.raises(UnoGameError, match="Command ini harus dipakai di channel server."):
        get_session(None)
    with pytest.raises(PokerGameError, match="Belum ada meja remi poker di channel ini"):
        get_poker_session(123456)


def test_reply_error_prefix_is_stable() -> None:
    sent: list[tuple[str, bool]] = []

    class Response:
        def is_done(self) -> bool:
            return False

        async def send_message(self, message: str, ephemeral: bool) -> None:
            sent.append((message, ephemeral))

    interaction = SimpleNamespace(response=Response())
    asyncio.run(reply_error(interaction, PokerGameError("contoh")))
    assert sent == [("Remi Poker: contoh", True)]
