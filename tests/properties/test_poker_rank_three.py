from __future__ import annotations

import pytest
from hypothesis import given, settings, strategies as st

from poker.game import PokerCard, PokerGameError, evaluate_combination


# Feature: clean-code-refactor, Property 6: Kartu rank "3" pada evaluasi memunculkan error
@given(st.sampled_from(["diamonds", "clubs", "hearts", "spades"]))
@settings(max_examples=100)
def test_rank_three_always_raises(suit: str) -> None:
    with pytest.raises(PokerGameError, match="Kartu 3"):
        evaluate_combination([PokerCard("3", suit)])
