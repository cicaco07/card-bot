from __future__ import annotations

import pytest
from hypothesis import given, settings, strategies as st

from poker.game import PokerCard, PokerGameError, evaluate_combination


INVALID_HANDS = [
    [PokerCard("4", "diamonds"), PokerCard("5", "clubs")],
    [PokerCard("4", "diamonds"), PokerCard("4", "clubs"), PokerCard("5", "hearts")],
    [PokerCard("4", "diamonds"), PokerCard("5", "clubs"), PokerCard("7", "hearts"), PokerCard("8", "spades"), PokerCard("10", "diamonds")],
]


# Feature: clean-code-refactor, Property 5: Himpunan kartu tak valid memunculkan error
@given(st.sampled_from(INVALID_HANDS))
@settings(max_examples=100)
def test_invalid_card_sets_raise(cards: list[PokerCard]) -> None:
    with pytest.raises(PokerGameError):
        evaluate_combination(cards)
