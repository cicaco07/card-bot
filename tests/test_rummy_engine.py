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
    flip_card_penalty,
    is_valid_meld,
    score_hand,
    score_hand_breakdown,
    score_hand_details,
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


def test_start_supports_custom_player_and_counter_clockwise_direction() -> None:
    game = RummyGame()
    game.add_player(1, "Alice")
    game.add_player(2, "Bob")
    game.add_player(3, "Charlie")

    game.start(starting_user_id=3, turn_direction=-1)

    assert game.current_player.user_id == 3
    assert game.public_state()["direction"] == "berlawanan arah jarum jam"
    assert game._advance_to_next_player_with_cards().user_id == 2


def test_meld_validation_supports_run_set_and_joker() -> None:
    joker = RummyCard("JOKER", joker_color="black")
    assert is_valid_meld(cards(("2", "hearts"), ("3", "hearts"), ("4", "hearts")))
    assert is_valid_meld(cards(("K", "diamonds"), ("K", "clubs"), ("K", "spades")))
    assert is_valid_meld([RummyCard("2", "hearts"), joker, RummyCard("4", "hearts")])
    assert is_valid_meld([RummyCard("4", "hearts"), RummyCard("5", "hearts"), joker, RummyCard("7", "hearts"), RummyCard("8", "hearts")])
    assert is_valid_meld([RummyCard("10", "hearts"), RummyCard("J", "hearts"), RummyCard("Q", "hearts"), joker])
    assert not is_valid_meld([RummyCard("Q", "hearts"), RummyCard("K", "hearts"), joker])
    assert not is_valid_meld([RummyCard("J", "diamonds"), RummyCard("J", "clubs"), joker])
    assert not is_valid_meld([RummyCard("A", "diamonds"), RummyCard("A", "clubs"), joker])
    assert not is_valid_meld(cards(("2", "hearts"), ("4", "hearts"), ("6", "hearts")))
    assert can_partition_into_melds(cards(("2", "hearts"), ("3", "hearts"), ("4", "hearts"), ("8", "diamonds"), ("8", "clubs"), ("8", "spades")))


def test_draw_from_discard_requires_manual_locked_meld_and_takes_cards_above_target() -> None:
    game = RummyGame()
    game.status = RummyStatus.PLAYING
    game.players = [RummyPlayer(1, "Alice", cards(("3", "hearts"), ("5", "hearts"))), RummyPlayer(2, "Bob", cards(("8", "clubs")))]
    game.deck = cards(("K", "spades"))
    game.discard_pile = cards(("4", "hearts"), ("9", "clubs"))
    game.discarded_by_user_ids = [2, 1]
    assert game.draw_from_discard(1, 2).public_messages == [
        "Alice mengambil 2 kartu dari buangan dengan target 4 ♥️.",
        "Alice wajib menurunkan meld bukti minimal 3 kartu yang memakai 4 ♥️ sebelum membuang kartu.",
    ]
    assert game.discard_pile == []
    assert game.discarded_by_user_ids == []
    assert game.flip_source_cards_by_user_id == {}
    assert game.pending_flip_source_cards_by_user_id == {
        2: [RummyCard("4", "hearts")],
        1: [RummyCard("9", "clubs")],
    }
    assert game.players[0].hand == cards(("9", "clubs"), ("3", "hearts"), ("4", "hearts"), ("5", "hearts"))
    assert game.players[0].opened_melds == []
    with pytest.raises(RummyGameError, match="Turunkan meld bukti"):
        game.discard_card(1, 1)
    assert game.lay_down_meld(1, [2, 3, 4]).public_messages == [
        "Alice menurunkan meld bukti dan menguncinya: 3 ♥️, 4 ♥️, 5 ♥️.",
    ]
    assert game.flip_source_cards_by_user_id == {}
    assert game.pending_flip_source_cards_by_user_id == {
        2: [RummyCard("4", "hearts")],
        1: [RummyCard("9", "clubs")],
    }
    assert game.public_state()["flipped_cards"] == []
    assert game.players[0].hand == cards(("9", "clubs"))
    assert game.players[0].opened_melds == [tuple(cards(("3", "hearts"), ("4", "hearts"), ("5", "hearts")))]
    assert game.required_discard_meld_card is None
    assert game.discard_card(1, 1).public_messages == [
        "Alice menghabiskan seluruh kartu dengan membuang 9 ♣️.",
        "Giliran berikutnya: Bob.",
    ]
    assert game.discard_pile == cards(("9", "clubs"))
    assert game.discarded_by_user_ids == [1]
    assert game.pending_flip_source_cards_by_user_id == {}
    assert game.flip_source_cards_by_user_id == {}

    game = RummyGame()
    game.status = RummyStatus.PLAYING
    game.players = [RummyPlayer(1, "Alice", cards(("3", "hearts"), ("5", "hearts"))), RummyPlayer(2, "Bob")]
    game.discard_pile = cards(("4", "hearts"), ("9", "clubs"), ("K", "spades"))
    assert game.draw_from_discard(1, 3).public_messages == [
        "Alice mengambil 3 kartu dari buangan dengan target 4 ♥️.",
        "Alice wajib menurunkan meld bukti minimal 3 kartu yang memakai 4 ♥️ sebelum membuang kartu.",
    ]
    assert game.lay_down_meld(1, [2, 3, 4]).public_messages == [
        "Alice menurunkan meld bukti dan menguncinya: 3 ♥️, 4 ♥️, 5 ♥️."
    ]
    assert game.players[0].hand == cards(("9", "clubs"), ("K", "spades"))

    game = RummyGame()
    game.status = RummyStatus.PLAYING
    game.players = [RummyPlayer(1, "Alice", cards(("2", "hearts"), ("8", "clubs"))), RummyPlayer(2, "Bob")]
    game.discard_pile = cards(("4", "hearts"), ("3", "hearts"), ("5", "hearts"))
    with pytest.raises(RummyGameError, match="minimal 2 kartu dari tangan"):
        game.draw_from_discard(1, 3)

    game = RummyGame()
    game.status = RummyStatus.PLAYING
    game.players = [RummyPlayer(1, "Alice", cards(("3", "hearts"), ("5", "hearts"), ("6", "hearts"))), RummyPlayer(2, "Bob")]
    game.discard_pile = cards(("4", "hearts"))
    game.draw_from_discard(1, 1)
    assert game.lay_down_meld(1, [1, 2, 3, 4]).public_messages == [
        "Alice menghabiskan seluruh kartu melalui meld. Deck habis. Perhitungan skor dimulai.",
        "Skor ronde: Alice +20, Bob +0.",
    ]

    game = RummyGame()
    game.status = RummyStatus.PLAYING
    game.players = [RummyPlayer(1, "Alice", cards(("3", "hearts"), ("6", "hearts"))), RummyPlayer(2, "Bob")]
    game.discard_pile = cards(("4", "hearts"), ("9", "clubs"))
    with pytest.raises(RummyGameError, match="meld bukti 3 kartu"):
        game.draw_from_discard(1, 2)

    game = RummyGame()
    game.status = RummyStatus.PLAYING
    game.players = [RummyPlayer(1, "Alice", cards(("3", "hearts"), ("5", "spades"))), RummyPlayer(2, "Bob")]
    game.discard_pile = cards(("4", "clubs"))
    with pytest.raises(RummyGameError, match="meld bukti 3 kartu"):
        game.draw_from_discard(1, 1)


def test_empty_hand_from_meld_continues_round_and_skips_players_without_cards() -> None:
    game = RummyGame()
    game.status = RummyStatus.PLAYING
    game.players = [
        RummyPlayer(1, "Alice", cards(("2", "hearts"), ("3", "hearts"), ("4", "hearts"))),
        RummyPlayer(2, "Bob"),
        RummyPlayer(3, "Charlie", cards(("9", "clubs"))),
    ]
    game.deck = cards(("K", "spades"))
    game.awaiting_discard_user_id = 1
    assert game.lay_down_meld(1, [1, 2, 3]).public_messages == [
        "Alice menghabiskan seluruh kartu melalui meld.",
        "Giliran berikutnya: Charlie.",
    ]
    assert game.status == RummyStatus.PLAYING
    assert game.current_player.user_id == 3


def test_discard_proof_meld_accepts_long_run_with_joker() -> None:
    joker = RummyCard("JOKER", joker_color="red")
    game = RummyGame()
    game.status = RummyStatus.PLAYING
    game.players = [
        RummyPlayer(1, "Alice", [*cards(("5", "hearts"), ("7", "hearts"), ("8", "hearts")), joker]),
        RummyPlayer(2, "Bob", cards(("9", "clubs"))),
    ]
    game.discard_pile = cards(("4", "hearts"))
    game.draw_from_discard(1, 1)
    assert game.lay_down_meld(1, [1, 2, 3, 4, 5]).public_messages == [
        "Alice menghabiskan seluruh kartu melalui meld. Deck habis. Perhitungan skor dimulai.",
        "Skor ronde: Alice +40, Bob -5.",
    ]
    assert game.players[0].opened_melds == [
        tuple([*cards(("4", "hearts"), ("5", "hearts"), ("7", "hearts"), ("8", "hearts")), joker])
    ]


def test_empty_hand_from_regular_discard_continues_round() -> None:
    game = RummyGame()
    game.status = RummyStatus.PLAYING
    game.players = [RummyPlayer(1, "Alice", cards(("9", "clubs"))), RummyPlayer(2, "Bob", cards(("8", "clubs")))]
    game.deck = cards(("K", "spades"))
    game.awaiting_discard_user_id = 1
    game.last_draw_source = "deck"
    assert game.discard_card(1, 1).public_messages == [
        "Alice menghabiskan seluruh kartu dengan membuang 9 ♣️.",
        "Giliran berikutnya: Bob.",
    ]
    assert game.status == RummyStatus.PLAYING
    assert game.current_player.user_id == 2


def test_visible_discards_are_limited_to_three_cards() -> None:
    game = RummyGame()
    game.discard_pile = cards(("2", "hearts"), ("3", "hearts"), ("4", "hearts"), ("5", "hearts"))
    game.discarded_by_user_ids = [1, 2, 1, 2]
    assert game.visible_discards() == cards(("5", "hearts"), ("4", "hearts"), ("3", "hearts"))
    assert game.visible_discard_details() == [
        (RummyCard("5", "hearts"), 2),
        (RummyCard("4", "hearts"), 1),
        (RummyCard("3", "hearts"), 2),
    ]


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


def test_regular_discard_rejects_joker_but_close_allows_it_without_bonus() -> None:
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
    assert result.scores[1] == 15
    assert result.scores[2] == -5
    assert game.score_breakdowns == {
        1: {
            "opened_meld_points": 0,
            "opened_melds": [],
            "hand_meld_points": 15,
            "hand_melds": [["2 ♥️", "3 ♥️", "4 ♥️"]],
            "deadwood_points": 0,
            "deadwood_cards": [],
            "flip_reward_points": 0,
            "flip_reward_user_ids": [],
            "flip_reward_card": None,
            "flip_penalty_points": 0,
            "flip_cards": [],
            "flip_penalty_card": None,
            "subtotal": 15,
            "total": 15,
        },
        2: {
            "opened_meld_points": 0,
            "opened_melds": [],
            "hand_meld_points": 0,
            "hand_melds": [],
            "deadwood_points": 5,
            "deadwood_cards": ["9 ♣️"],
            "flip_reward_points": 0,
            "flip_reward_user_ids": [],
            "flip_reward_card": None,
            "flip_penalty_points": 0,
            "flip_cards": [],
            "flip_penalty_card": None,
            "subtotal": -5,
            "total": -5,
        },
    }


def test_closed_card_uses_closing_card_value_for_flip_penalty() -> None:
    game = RummyGame()
    game.status = RummyStatus.PLAYING
    game.players = [
        RummyPlayer(1, "Alice", cards(("A", "spades"), ("3", "hearts"), ("5", "hearts"))),
        RummyPlayer(2, "Bob", cards(("9", "clubs"))),
    ]
    game.deck = cards(("K", "spades"))
    game.discard_pile = cards(("4", "hearts"))
    game.discarded_by_user_ids = [2]
    game.draw_from_discard(1, 1)
    game.lay_down_meld(1, [1, 2, 3])

    result = game.discard_card(1, 1, close=True)

    assert result.public_messages == [
        "Alice closed card dengan A ♠️.",
        "Skor ronde: Alice +165, Bob -155.",
    ]
    assert result.closed_user_id == 1
    assert game.status == RummyStatus.FINISHED
    assert game.flip_source_cards_by_user_id == {2: cards(("4", "hearts"))}
    assert game.score_breakdowns[1]["flip_reward_points"] == 150
    assert game.score_breakdowns[1]["flip_reward_user_ids"] == [2]
    assert game.score_breakdowns[1]["flip_reward_card"] == "A ♠️"
    assert game.score_breakdowns[2] == {
        "opened_meld_points": 0,
        "opened_melds": [],
        "hand_meld_points": 0,
        "hand_melds": [],
        "deadwood_points": 5,
        "deadwood_cards": ["9 ♣️"],
        "flip_reward_points": 0,
        "flip_reward_user_ids": [],
        "flip_reward_card": None,
        "flip_penalty_points": 150,
        "flip_cards": ["4 ♥️"],
        "flip_penalty_card": "A ♠️",
        "subtotal": -155,
        "total": -155,
    }


def test_flip_sources_do_not_apply_penalty_without_closed_card() -> None:
    game = RummyGame()
    game.status = RummyStatus.PLAYING
    game.players = [RummyPlayer(1, "Alice", cards(("2", "spades"))), RummyPlayer(2, "Bob", cards(("9", "clubs")))]
    game.flip_source_cards_by_user_id = {2: cards(("J", "hearts"))}

    result = game.draw_from_deck(1)

    assert result.scores == {1: -5, 2: -5}
    assert game.score_breakdowns[2]["flip_penalty_points"] == 0
    assert game.score_breakdowns[2]["flip_penalty_card"] is None


def test_multiple_discard_meld_sources_only_apply_one_flip_penalty_per_player() -> None:
    game = RummyGame()
    game.status = RummyStatus.PLAYING
    game.players = [RummyPlayer(1, "Alice", cards(("2", "spades"))), RummyPlayer(2, "Bob", cards(("9", "clubs")))]
    game.awaiting_discard_user_id = 1
    game.last_draw_source = "deck"
    game.pending_flip_source_cards_by_user_id = {2: cards(("4", "hearts"), ("J", "hearts"))}

    result = game.discard_card(1, 1, close=True)

    assert result.scores[2] == -55
    assert result.scores[1] == 50
    assert game.score_breakdowns[1]["flip_reward_points"] == 50
    assert game.score_breakdowns[2]["flip_penalty_points"] == 50
    assert game.score_breakdowns[2]["flip_cards"] == ["4 ♥️", "J ♥️"]


def test_flip_card_penalizes_target_and_discards_above_target() -> None:
    game = RummyGame()
    game.status = RummyStatus.PLAYING
    game.players = [
        RummyPlayer(1, "Alice", cards(("3", "hearts"), ("5", "hearts"))),
        RummyPlayer(2, "Bob", cards(("8", "clubs"))),
        RummyPlayer(3, "Charlie", cards(("7", "clubs"))),
    ]
    game.deck = cards(("K", "spades"))
    game.discard_pile = cards(("4", "hearts"), ("9", "diamonds"))
    game.discarded_by_user_ids = [2, 3]

    game.draw_from_discard(1, 2)
    game.lay_down_meld(1, [2, 3, 4])
    game.discard_card(1, 1, close=True)

    assert game.flip_source_cards_by_user_id == {
        2: cards(("4", "hearts")),
        3: cards(("9", "diamonds")),
    }
    assert game.score_breakdowns[2]["flip_penalty_points"] == 50
    assert game.score_breakdowns[3]["flip_penalty_points"] == 50
    assert game.score_breakdowns[1]["flip_reward_points"] == 100
    assert game.score_breakdowns[1]["flip_reward_user_ids"] == [2, 3]


def test_closed_card_with_hidden_meld_after_discard_draw_is_not_flip_card() -> None:
    game = RummyGame()
    game.status = RummyStatus.PLAYING
    game.players = [
        RummyPlayer(1, "Alice", cards(("2", "clubs"), ("3", "clubs"), ("4", "clubs"), ("3", "hearts"), ("5", "hearts"))),
        RummyPlayer(2, "Bob", cards(("8", "clubs"))),
        RummyPlayer(3, "Charlie", cards(("7", "clubs"))),
    ]
    game.deck = cards(("K", "spades"))
    game.discard_pile = cards(("4", "hearts"), ("9", "diamonds"))
    game.discarded_by_user_ids = [2, 3]

    game.draw_from_discard(1, 2)
    game.lay_down_meld(1, [5, 6, 7])
    game.discard_card(1, 1, close=True)

    assert game.flip_source_cards_by_user_id == {}
    assert game.score_breakdowns[1]["flip_reward_points"] == 0
    assert game.score_breakdowns[2]["flip_penalty_points"] == 0
    assert game.score_breakdowns[3]["flip_penalty_points"] == 0


def test_ace_discard_requires_own_non_ace_opened_meld() -> None:
    game = RummyGame()
    game.status = RummyStatus.PLAYING
    game.players = [RummyPlayer(1, "Alice", cards(("A", "hearts"), ("9", "clubs"))), RummyPlayer(2, "Bob")]
    game.awaiting_discard_user_id = 1
    with pytest.raises(RummyGameError, match="Ace hanya boleh dibuang"):
        game.discard_card(1, 1)
    with pytest.raises(RummyGameError, match="Ace hanya boleh dibuang"):
        game.discard_card(1, 1, close=True)

    game.players[0].opened_melds = [tuple(cards(("2", "hearts"), ("3", "hearts"), ("4", "hearts")))]
    game.deck = cards(("5", "clubs"))
    game.last_draw_source = "deck"
    assert game.discard_card(1, 1).public_messages[0] == "Alice membuang A ♥️ setelah mengambil dari deck."


def test_ace_draw_from_discard_requires_own_non_ace_opened_meld() -> None:
    game = RummyGame()
    game.status = RummyStatus.PLAYING
    game.players = [
        RummyPlayer(1, "Alice", cards(("Q", "hearts"), ("K", "hearts"))),
        RummyPlayer(2, "Bob", opened_melds=[tuple(cards(("2", "clubs"), ("3", "clubs"), ("4", "clubs")))]),
    ]
    game.discard_pile = cards(("A", "hearts"))
    with pytest.raises(RummyGameError, match="Ace dari buangan hanya boleh diambil"):
        game.draw_from_discard(1, 1)

    game.players[0].opened_melds = [tuple(cards(("Q", "clubs"), ("K", "clubs"), ("A", "clubs")))]
    with pytest.raises(RummyGameError, match="Ace dari buangan hanya boleh diambil"):
        game.draw_from_discard(1, 1)

    game.players[0].opened_melds = [tuple(cards(("2", "clubs"), ("3", "clubs"), ("4", "clubs")))]
    assert game.draw_from_discard(1, 1).public_messages == [
        "Alice mengambil 1 kartu dari buangan dengan target A ♥️.",
        "Alice wajib menurunkan meld bukti minimal 3 kartu yang memakai A ♥️ sebelum membuang kartu.",
    ]


def test_ace_above_discard_target_also_requires_own_non_ace_opened_meld() -> None:
    game = RummyGame()
    game.status = RummyStatus.PLAYING
    game.players = [RummyPlayer(1, "Alice", cards(("3", "hearts"), ("5", "hearts"))), RummyPlayer(2, "Bob")]
    game.discard_pile = cards(("4", "hearts"), ("A", "clubs"))
    with pytest.raises(RummyGameError, match="Ace dari buangan hanya boleh diambil"):
        game.draw_from_discard(1, 2)

    game.players[0].opened_melds = [tuple(cards(("7", "clubs"), ("8", "clubs"), ("9", "clubs")))]
    assert game.draw_from_discard(1, 2).public_messages == [
        "Alice mengambil 2 kartu dari buangan dengan target 4 ♥️.",
        "Alice wajib menurunkan meld bukti minimal 3 kartu yang memakai 4 ♥️ sebelum membuang kartu.",
    ]


def test_lay_down_meld_removes_cards_from_hand_and_locks_them() -> None:
    game = RummyGame()
    game.status = RummyStatus.PLAYING
    game.players = [
        RummyPlayer(1, "Alice", cards(("2", "hearts"), ("3", "hearts"), ("4", "hearts"), ("9", "clubs"))),
        RummyPlayer(2, "Bob"),
    ]
    game.awaiting_discard_user_id = 1
    result = game.lay_down_meld(1, [1, 2, 3])
    assert result.public_messages == ["Alice menurunkan meld dan menguncinya: 2 ♥️, 3 ♥️, 4 ♥️."]
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
    assert result.public_messages == ["Alice menggabungkan 5 ♥️ ke meld terbuka Bob."]
    assert game.players[0].hand == cards(("9", "clubs"))
    assert game.players[1].opened_melds == [tuple(cards(("2", "hearts"), ("3", "hearts"), ("4", "hearts"), ("5", "hearts")))]


def test_score_and_flip_card_penalty_rules() -> None:
    hand = cards(("2", "hearts"), ("3", "hearts"), ("4", "hearts"), ("A", "clubs"))
    assert score_hand(hand) == 0
    assert score_hand_breakdown(hand) == (15, 15)
    assert score_hand_details(hand) == ([tuple(cards(("2", "hearts"), ("3", "hearts"), ("4", "hearts")))], cards(("A", "clubs")))
    assert flip_card_penalty(RummyCard("9", "clubs")) == 50
    assert flip_card_penalty(RummyCard("K", "clubs")) == 100
    assert flip_card_penalty(RummyCard("A", "clubs")) == 150
    assert flip_card_penalty(RummyCard("JOKER", joker_color="black")) == 250


def test_tournament_accumulates_round_scores() -> None:
    session = RummySession(channel_id=1, owner_id=1, mode="tournament")
    session.tournament_current_round = 1
    session.game.status = RummyStatus.FINISHED
    session.game.players = [RummyPlayer(1, "Alice"), RummyPlayer(2, "Bob")]
    session.game.scores = {1: 65, 2: -15}
    assert session.score_finished_tournament_round() == ["Skor ronde 1: <@1> +65, <@2> -15."]
    assert session.tournament_scores == {1: 65, 2: -15}
    assert session.tournament_next_turn_direction == 1


def test_tournament_first_round_randomizes_start_and_uses_clockwise_direction(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(random, "choice", lambda players: players[-1])
    session = RummySession(channel_id=1, owner_id=1, mode="tournament")
    session.game.add_player(1, "Alice")
    session.game.add_player(2, "Bob")
    session.game.add_player(3, "Charlie")

    messages = session.start_rummy_round()

    assert messages[:2] == [
        "Ronde tournament 1/3 dimulai.",
        "Arah giliran ronde: searah jarum jam.",
    ]
    assert session.game.current_player.user_id == 3
    assert session.game.turn_direction == 1


def test_tournament_next_round_starts_at_lowest_score_and_reverses_after_flip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(random, "choice", lambda players: players[0])
    session = RummySession(channel_id=1, owner_id=1, mode="tournament")
    session.tournament_current_round = 1
    session.tournament_scores = {1: 100, 2: 0, 3: 50}
    session.game.status = RummyStatus.FINISHED
    session.game.players = [RummyPlayer(1, "Alice"), RummyPlayer(2, "Bob"), RummyPlayer(3, "Charlie")]
    session.game.scores = {1: 5, 2: -10, 3: 0}
    session.game.closed_card = RummyCard("2", "spades")
    session.game.flip_source_cards_by_user_id = {3: cards(("4", "hearts"))}

    session.score_finished_tournament_round()
    messages = session.start_next_tournament_round()

    assert messages[:2] == [
        "Ronde tournament 2/3 dimulai.",
        "Arah giliran ronde: berlawanan arah jarum jam.",
    ]
    assert session.tournament_scores == {1: 105, 2: -10, 3: 50}
    assert session.game.current_player.user_id == 2
    assert session.game.turn_direction == -1
    assert session.game._advance_to_next_player_with_cards().user_id == 1
