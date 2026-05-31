from __future__ import annotations

import pytest

from cardbot.sessions import PokerSession
from poker.game import (
    PokerCard,
    PokerCombination,
    PokerGame,
    PokerPlayer,
    PokerStatus,
    compare_combinations,
    evaluate_combination,
)


def cards(*values: tuple[str, str]) -> list[PokerCard]:
    return [PokerCard(rank, suit) for rank, suit in values]


def test_seeded_start_is_stable(seeded: int) -> None:
    game = PokerGame()
    for user_id, name in [(1, "Alice"), (2, "Bob"), (3, "Cara"), (4, "Dedi")]:
        game.add_player(user_id, name)

    assert game.start() == [
        "Game Remi Poker dimulai dengan 4 pemain.",
        "Kartu 3 penentu giliran: Alice: 3 of Clubs | Bob: Tidak ada | Cara: 3 of Spades, 3 of Hearts | Dedi: 3 of Diamonds.",
        "Urutan awal berdasarkan kartu 3: Cara -> Alice -> Dedi -> Bob.",
        "Semua kartu 3 dibuang. Rank terendah yang dimainkan adalah 4.",
        "Giliran pertama: Cara.",
    ]
    assert game.public_state()["hand_counts"] == [
        (3, "Cara", 11, False, False),
        (1, "Alice", 12, False, False),
        (4, "Dedi", 12, False, False),
        (2, "Bob", 13, False, False),
    ]


@pytest.mark.parametrize(
    ("expected", "combination_cards"),
    [
        ("single", cards(("4", "diamonds"))),
        ("pair", cards(("4", "diamonds"), ("4", "clubs"))),
        ("three_of_a_kind", cards(("4", "diamonds"), ("4", "clubs"), ("4", "hearts"))),
        ("four_of_a_kind", cards(("4", "diamonds"), ("4", "clubs"), ("4", "hearts"), ("4", "spades"))),
        ("straight", cards(("4", "diamonds"), ("5", "clubs"), ("6", "hearts"), ("7", "spades"), ("8", "diamonds"))),
        ("flush", cards(("4", "clubs"), ("6", "clubs"), ("8", "clubs"), ("10", "clubs"), ("Q", "clubs"))),
        ("full_house", cards(("4", "diamonds"), ("4", "clubs"), ("4", "hearts"), ("5", "diamonds"), ("5", "clubs"))),
        ("straight_flush", cards(("4", "hearts"), ("5", "hearts"), ("6", "hearts"), ("7", "hearts"), ("8", "hearts"))),
        ("royal_flush", cards(("10", "spades"), ("J", "spades"), ("Q", "spades"), ("K", "spades"), ("A", "spades"))),
    ],
)
def test_evaluate_each_combination_kind(expected: str, combination_cards: list[PokerCard]) -> None:
    assert evaluate_combination(combination_cards).kind == expected


def test_pair_play_auto_skips_player_without_higher_pair() -> None:
    game = PokerGame()
    game.status = PokerStatus.PLAYING
    game.players = [
        PokerPlayer(1, "Alice", cards(("4", "diamonds"), ("4", "clubs"), ("9", "spades"))),
        PokerPlayer(2, "Bob", cards(("5", "diamonds"), ("7", "clubs"))),
        PokerPlayer(3, "Cara", cards(("6", "diamonds"), ("6", "clubs"), ("8", "spades"))),
    ]

    result = game.play_cards(1, [1, 2])

    assert result.public_messages == [
        "Alice memainkan Pair: 4 of Diamonds, 4 of Clubs.",
        "Bob auto-skip karena tidak punya kombinasi yang bisa mengalahkan.",
        "Giliran berikutnya: Cara.",
    ]
    assert game.current_player.user_id == 3


def test_pass_clears_table_after_other_players_pass() -> None:
    game = PokerGame()
    game.status = PokerStatus.PLAYING
    game.players = [
        PokerPlayer(1, "Alice", cards(("4", "diamonds"), ("9", "spades"))),
        PokerPlayer(2, "Bob", cards(("5", "diamonds"))),
    ]
    game.last_play = evaluate_combination(cards(("4", "diamonds")))
    game.last_play_player_id = 1
    game.round_pattern = "single"
    game.turn_index = 1

    assert game.pass_turn(2).public_messages == [
        "Bob pass.",
        "Table clear. Alice membuka ronde baru.",
    ]


def test_bomb_duel_eliminates_target_after_all_contenders_pass() -> None:
    game = PokerGame()
    game.status = PokerStatus.PLAYING
    game.players = [
        PokerPlayer(1, "Alice", cards(("2", "spades"), ("9", "diamonds"))),
        PokerPlayer(2, "Bob", cards(("4", "diamonds"), ("4", "clubs"), ("4", "hearts"), ("4", "spades"), ("8", "diamonds"))),
        PokerPlayer(3, "Cara", cards(("5", "diamonds"))),
    ]
    game.last_play = evaluate_combination(cards(("2", "spades")))
    game.last_play_player_id = 1
    game.round_pattern = "single"
    game.turn_index = 1

    result = game.play_cards(2, [1, 2, 3, 4])
    assert result.public_messages[-2:] == [
        "Bob membuka adu bomb. Jika tidak ada bomb lebih tinggi, Alice terkena bomb.",
        "Giliran berikutnya: Cara.",
    ]
    assert game.pass_turn(3).public_messages == ["Cara pass adu bomb.", "Giliran berikutnya: Alice."]
    assert game.pass_turn(1).public_messages == [
        "Alice pass adu bomb.",
        "Alice terkena bombcard dari Bob dan kalah.",
        "Winner: Bob, Cara.",
    ]


def test_tournament_scoring_keeps_regular_and_bomb_points() -> None:
    session = PokerSession(channel_id=1, owner_id=1, mode="tournament")
    session.tournament_current_round = 1
    session.game.status = PokerStatus.FINISHED
    session.game.players = [PokerPlayer(1, "Alice"), PokerPlayer(2, "Bob"), PokerPlayer(3, "Cara")]
    session.game.winner_ids = [1, 2]
    session.game.loser_id = 3
    assert session.score_finished_tournament_round() == ["Skor ronde 1: <@1> +20, <@2> +10, <@3> -10."]

    session.tournament_current_round = 2
    session.game.bomb_finish_bomber_id = 2
    session.game.bomb_finish_loser_id = 1
    session.game.winner_ids = [2, 3]
    session.game.loser_id = 1
    assert session.score_finished_tournament_round() == ["Skor ronde 2: <@2> +40, <@3> +0, <@1> -40."]
    assert session.tournament_scores == {1: -20, 2: 50, 3: -10}
