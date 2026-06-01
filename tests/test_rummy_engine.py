from __future__ import annotations

import random

import pytest

from cardbot.sessions import RummySession
from rummy.cards import RummyCard
from rummy.game import (
    RummyGame,
    RummyGameError,
    RummyPlayer,
    RummyStatus,
    can_partition_into_melds,
    closed_card_bonus,
    is_valid_meld,
    score_hand,
)


def cards(*values: tuple[str, str | None]) -> list[RummyCard]:
    return [RummyCard(rank, suit) for rank, suit in values]


def test_deck_contains_standard_cards_and_four_jokers() -> None:
    deck = RummyGame._build_deck()
    assert len(deck) == 56
    assert sum(card.is_joker for card in deck) == 4
    assert sum(card.joker_color == "black" for card in deck) == 2
    assert sum(card.joker_color == "red" for card in deck) == 2


def test_seeded_start_deals_seven_cards_and_starts_with_draw_phase() -> None:
    random.seed(1234)
    game = RummyGame()
    game.add_player(1, "Alice")
    game.add_player(2, "Bob")
    assert game.start() == [
        "Game Rummy dimulai dengan 2 pemain.",
        "Setiap pemain mendapat 7 kartu.",
        "Giliran pertama: Alice. Ambil kartu dari deck.",
    ]
    assert [len(player.hand) for player in game.players] == [7, 7]
    assert len(game.deck) == 42
    assert game.public_state()["phase"] == "ambil kartu"


def test_meld_validation_supports_run_set_and_joker() -> None:
    joker = RummyCard("JOKER", joker_color="black")
    assert is_valid_meld(cards(("2", "hearts"), ("3", "hearts"), ("4", "hearts")))
    assert is_valid_meld(cards(("K", "diamonds"), ("K", "clubs"), ("K", "spades")))
    assert is_valid_meld([RummyCard("2", "hearts"), joker, RummyCard("4", "hearts")])
    assert not is_valid_meld(cards(("2", "hearts"), ("4", "hearts"), ("6", "hearts")))
    assert can_partition_into_melds(cards(("2", "hearts"), ("3", "hearts"), ("4", "hearts"), ("8", "diamonds"), ("8", "clubs"), ("8", "spades")))


def test_draw_from_discard_opens_locked_meld_and_takes_cards_above_target() -> None:
    game = RummyGame()
    game.status = RummyStatus.PLAYING
    game.players = [RummyPlayer(1, "Alice", cards(("3", "hearts"), ("5", "hearts"))), RummyPlayer(2, "Bob")]
    game.discard_pile = cards(("4", "hearts"), ("9", "clubs"))
    assert game.draw_from_discard(1, 2).public_messages == [
        "Alice mengambil 2 kartu dari buangan dengan target 4 of Hearts.",
        "Meld bukti Alice dibuka dan dikunci: 3 of Hearts, 5 of Hearts, 4 of Hearts.",
    ]
    assert game.discard_pile == []
    assert game.players[0].hand == cards(("9", "clubs"))
    assert game.players[0].opened_melds == [tuple(cards(("3", "hearts"), ("5", "hearts"), ("4", "hearts")))]

    game = RummyGame()
    game.status = RummyStatus.PLAYING
    game.players = [RummyPlayer(1, "Alice", cards(("3", "hearts"), ("5", "spades"))), RummyPlayer(2, "Bob")]
    game.discard_pile = cards(("4", "clubs"))
    with pytest.raises(RummyGameError, match="langsung melengkapi meld"):
        game.draw_from_discard(1, 1)


def test_visible_discards_are_limited_to_three_cards() -> None:
    game = RummyGame()
    game.discard_pile = cards(("2", "hearts"), ("3", "hearts"), ("4", "hearts"), ("5", "hearts"))
    assert game.visible_discards() == cards(("5", "hearts"), ("4", "hearts"), ("3", "hearts"))


def test_draw_deck_then_discard_preserves_cards_and_advances_turn() -> None:
    random.seed(4321)
    game = RummyGame()
    game.add_player(1, "Alice")
    game.add_player(2, "Bob")
    game.start()
    assert len(game.deck) + sum(len(player.hand) for player in game.players) + len(game.discard_pile) == 56
    game.draw_from_deck(1)
    result = game.discard_card(1, 1)
    assert result.public_messages[-1] == "Giliran berikutnya: Bob."
    assert game.current_player.user_id == 2
    assert len(game.deck) + sum(len(player.hand) for player in game.players) + len(game.discard_pile) == 56


def test_regular_discard_rejects_joker_but_close_allows_it() -> None:
    joker = RummyCard("JOKER", joker_color="red")
    game = RummyGame()
    game.status = RummyStatus.PLAYING
    game.players = [
        RummyPlayer(1, "Alice", [*cards(("2", "hearts"), ("3", "hearts"), ("4", "hearts")), joker]),
        RummyPlayer(2, "Bob", cards(("9", "clubs"))),
    ]
    game.awaiting_discard_user_id = 1
    game.last_draw_source = "deck"
    with pytest.raises(RummyGameError, match="Joker tidak boleh dibuang"):
        game.discard_card(1, 4)
    result = game.discard_card(1, 4, close=True)
    assert result.closed_user_id == 1
    assert result.scores[1] == 530
    assert result.scores[2] == -10
    assert game.go_rummy_user_id == 1


def test_ace_discard_requires_opened_meld() -> None:
    game = RummyGame()
    game.status = RummyStatus.PLAYING
    game.players = [RummyPlayer(1, "Alice", cards(("A", "hearts"), ("9", "clubs"))), RummyPlayer(2, "Bob")]
    game.awaiting_discard_user_id = 1
    with pytest.raises(RummyGameError, match="Ace belum boleh dibuang"):
        game.discard_card(1, 1)

    game.players[0].opened_melds = [tuple(cards(("2", "hearts"), ("3", "hearts"), ("4", "hearts")))]
    game.deck = cards(("5", "clubs"))
    game.last_draw_source = "deck"
    assert game.discard_card(1, 1).public_messages[0] == "Alice membuang Ace of Hearts setelah mengambil dari deck."


def test_lay_down_meld_removes_cards_from_hand_and_locks_them() -> None:
    game = RummyGame()
    game.status = RummyStatus.PLAYING
    game.players = [
        RummyPlayer(1, "Alice", cards(("2", "hearts"), ("3", "hearts"), ("4", "hearts"), ("9", "clubs"))),
        RummyPlayer(2, "Bob"),
    ]
    game.awaiting_discard_user_id = 1
    result = game.lay_down_meld(1, [1, 2, 3])
    assert result.public_messages == ["Alice menurunkan meld dan menguncinya: 2 of Hearts, 3 of Hearts, 4 of Hearts."]
    assert game.players[0].hand == cards(("9", "clubs"))
    assert game.players[0].opened_melds == [tuple(cards(("2", "hearts"), ("3", "hearts"), ("4", "hearts")))]


def test_lay_off_cards_extends_opened_meld() -> None:
    game = RummyGame()
    game.status = RummyStatus.PLAYING
    game.players = [
        RummyPlayer(1, "Alice", cards(("5", "hearts"), ("9", "clubs"))),
        RummyPlayer(2, "Bob", opened_melds=[tuple(cards(("2", "hearts"), ("3", "hearts"), ("4", "hearts")))]),
    ]
    game.awaiting_discard_user_id = 1
    result = game.lay_off_cards(1, 2, 0, [1])
    assert result.public_messages == ["Alice menggabungkan 5 of Hearts ke meld terbuka Bob."]
    assert game.players[0].hand == cards(("9", "clubs"))
    assert game.players[1].opened_melds == [tuple(cards(("2", "hearts"), ("3", "hearts"), ("4", "hearts"), ("5", "hearts")))]


def test_score_and_closed_bonus_rules() -> None:
    hand = cards(("2", "hearts"), ("3", "hearts"), ("4", "hearts"), ("A", "clubs"))
    assert score_hand(hand) == 0
    assert closed_card_bonus(RummyCard("9", "clubs")) == 50
    assert closed_card_bonus(RummyCard("K", "clubs")) == 100
    assert closed_card_bonus(RummyCard("A", "clubs")) == 150
    assert closed_card_bonus(RummyCard("JOKER", joker_color="black")) == 250


def test_tournament_accumulates_round_scores() -> None:
    session = RummySession(channel_id=1, owner_id=1, mode="tournament")
    session.tournament_current_round = 1
    session.game.status = RummyStatus.FINISHED
    session.game.players = [RummyPlayer(1, "Alice"), RummyPlayer(2, "Bob")]
    session.game.scores = {1: 65, 2: -15}
    assert session.score_finished_tournament_round() == ["Skor ronde 1: <@1> +65, <@2> -15."]
    assert session.tournament_scores == {1: 65, 2: -15}
