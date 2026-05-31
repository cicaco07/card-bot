from __future__ import annotations

from uno.game import Card, GameStatus, Player, UnoGame


def _playing_game(*hands: list[Card]) -> UnoGame:
    game = UnoGame()
    game.status = GameStatus.PLAYING
    game.players = [
        Player(user_id=index, name=name, hand=list(hand))
        for index, (name, hand) in enumerate(zip(("Alice", "Bob", "Cara"), hands), start=1)
    ]
    game.deck = [Card("green", "0"), Card("yellow", "1"), Card("blue", "2"), Card("red", "3")]
    game.discard_pile = [Card("red", "7")]
    game.current_color = "red"
    return game


def test_seeded_start_is_stable(seeded: int) -> None:
    game = UnoGame()
    game.add_player(1, "Alice")
    game.add_player(2, "Bob")

    assert game.start() == [
        "Game UNO dimulai dengan 2 pemain.",
        "Kartu pertama: Merah 3.",
        "Giliran pertama: Alice.",
    ]
    assert game.public_state() == {
        "status": "playing",
        "top_card": "Merah 3",
        "current_color": "Merah",
        "current_player_id": 1,
        "direction": "searah jarum jam",
        "hand_counts": [(1, "Alice", 7), (2, "Bob", 7)],
        "uno_pending": [],
        "deck_count": 93,
    }


def test_action_cards_keep_their_public_messages() -> None:
    skip = _playing_game([Card("red", "skip"), Card("green", "4"), Card("yellow", "6")], [Card("blue", "1")])
    assert skip.play_card(1, 1).public_messages == [
        "Alice memainkan Merah Stop.",
        "Bob kena Stop dan dilewati.",
        "Giliran berikutnya: Alice.",
    ]

    reverse = _playing_game(
        [Card("red", "reverse"), Card("green", "4"), Card("yellow", "6")],
        [Card("blue", "1")],
        [Card("yellow", "2")],
    )
    assert reverse.play_card(1, 1).public_messages == [
        "Alice memainkan Merah Reverse.",
        "Arah permainan dibalik.",
        "Giliran berikutnya: Cara.",
    ]

    draw_two = _playing_game([Card("red", "draw2"), Card("green", "4"), Card("yellow", "6")], [Card("blue", "1")])
    assert draw_two.play_card(1, 1).public_messages == [
        "Alice memainkan Merah +2.",
        "Bob mengambil 2 kartu dan dilewati.",
        "Giliran berikutnya: Alice.",
    ]

    draw_four = _playing_game([Card(None, "wild_draw4"), Card("green", "4"), Card("yellow", "6")], [Card("blue", "1")])
    assert draw_four.play_card(1, 1, "blue").public_messages == [
        "Alice memainkan Change Color +4.",
        "Warna diganti menjadi Biru.",
        "Bob mengambil 4 kartu dan dilewati.",
        "Giliran berikutnya: Alice.",
    ]


def test_draw_pass_call_and_challenge_uno() -> None:
    game = _playing_game([Card("blue", "4")], [Card("yellow", "5")])
    game.deck = [Card("blue", "9")]
    assert game.draw_card(1).public_messages == [
        "Alice mengambil 1 kartu.",
        "Kartu belum cocok. Giliran berpindah ke Bob.",
    ]
    assert game.pass_turn(2).public_messages == ["Bob pass.", "Giliran berikutnya: Alice."]

    game.pending_uno_user_ids.add(2)
    assert game.call_uno(2).public_messages == ["Bob menekan tombol UNO!"]
    game.pending_uno_user_ids.add(2)
    game.deck = [Card("blue", "1"), Card("green", "2")]
    assert game.challenge_uno(1, 2).public_messages == [
        "Alice berhasil challenge UNO terhadap Bob.",
        "Bob lupa menekan UNO! dan mengambil 2 kartu penalti.",
    ]


def test_discard_is_reshuffled_when_deck_runs_out() -> None:
    game = _playing_game([Card("blue", "4")], [Card("yellow", "5")])
    game.deck = []
    game.discard_pile = [Card("green", "1"), Card("blue", "2"), Card("red", "7")]

    drawn = game._draw_one()

    assert drawn in {Card("green", "1"), Card("blue", "2")}
    assert game.discard_pile == [Card("red", "7")]
    assert len(game.deck) == 1
