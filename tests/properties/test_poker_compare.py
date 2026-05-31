from __future__ import annotations

from hypothesis import given, settings, strategies as st

from poker.game import PokerCard, compare_combinations, evaluate_combination


RANKS = ["4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A", "2"]
SUITS = ["diamonds", "clubs", "hearts", "spades"]


# Feature: clean-code-refactor, Property 3: Anti-simetri perbandingan kombinasi Poker
@given(st.sampled_from(RANKS), st.sampled_from(SUITS), st.sampled_from(RANKS), st.sampled_from(SUITS))
@settings(max_examples=100)
def test_compare_is_antisymmetric(left_rank: str, left_suit: str, right_rank: str, right_suit: str) -> None:
    left = evaluate_combination([PokerCard(left_rank, left_suit)])
    right = evaluate_combination([PokerCard(right_rank, right_suit)])
    assert compare_combinations(left, right) == -compare_combinations(right, left)
    assert compare_combinations(left, left) == 0
