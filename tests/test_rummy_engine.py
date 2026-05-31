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


def test_deck_contains_standard_cards_and_two_jokers() -> None:
    deck = RummyGame._build_deck()
    assert len(deck) == 54
    assert sum(card.is_joker for card in deck) == 2


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
    assert len(game.deck) == 40
    assert game.public_state()["phase"] == "ambil kartu"


def test_meld_validation_supports_run_set_and_joker() -> None:
    joker = RummyCard("JOKER", joker_color="black")
    assert is_valid_meld(cards(("2", "hearts"), ("3", "hearts"), ("4", "hearts")))
    assert is_valid_meld(cards(("K", "diamonds"), ("K", "clubs"), ("K", "spades")))
    assert is_valid_meld([RummyCard("2", "hearts"), joker, RummyCard("4", "hearts")])
    assert not is_valid_meld(cards(("2", "hearts"), ("4", "hearts"), ("6", "hearts")))
    assert can_partition_into_melds(cards(("2", "hearts"), ("3", "hearts"), ("4", "hearts"), ("8", "diamonds"), ("8", "clubs"), ("8", "spades")))


def test_draw_from_discard_requires_immediate_meld_and_removes_selected_depth() -> None:
    game = RummyGame()
    game.status = RummyStatus.PLAYING
    game.players = [RummyPlayer(1, "Alice", cards(("3", "hearts"), ("5", "hearts"))), RummyPlayer(2, "Bob")]
    game.discard_pile = cards(("4", "hearts"), ("9", "clubs"))
    assert game.draw_from_discard(1, 2).public_messages == ["Alice mengambil 4 of Hearts dari buangan."]
    assert game.discard_pile == cards(("9", "clubs"))

    game.awaiting_discard_user_id = None
    with pytest.raises(RummyGameError, match="langsung melengkapi meld"):
        game.draw_from_discard(1, 1)


def test_draw_deck_then_discard_preserves_cards_and_advances_turn() -> None:
    random.seed(4321)
    game = RummyGame()
    game.add_player(1, "Alice")
    game.add_player(2, "Bob")
    game.start()
    assert len(game.deck) + sum(len(player.hand) for player in game.players) + len(game.discard_pile) == 54
    game.draw_from_deck(1)
    result = game.discard_card(1, 1)
    assert result.public_messages[-1] == "Giliran berikutnya: Bob."
    assert game.current_player.user_id == 2
    assert len(game.deck) + sum(len(player.hand) for player in game.players) + len(game.discard_pile) == 54


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
    assert result.scores[1] == 265


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
