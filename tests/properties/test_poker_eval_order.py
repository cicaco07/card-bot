from __future__ import annotations

from itertools import permutations

from hypothesis import given, settings, strategies as st

from poker.game import PokerCard, evaluate_combination


VALID_HANDS = [
    [PokerCard("4", "diamonds"), PokerCard("4", "clubs")],
    [PokerCard("4", "diamonds"), PokerCard("4", "clubs"), PokerCard("4", "hearts")],
    [PokerCard("4", "diamonds"), PokerCard("5", "clubs"), PokerCard("6", "hearts"), PokerCard("7", "spades"), PokerCard("8", "diamonds")],
    [PokerCard("10", "spades"), PokerCard("J", "spades"), PokerCard("Q", "spades"), PokerCard("K", "spades"), PokerCard("A", "spades")],
]


# Feature: clean-code-refactor, Property 4: Evaluasi kombinasi tidak bergantung urutan kartu masukan
@given(st.sampled_from(VALID_HANDS), st.integers(min_value=0, max_value=119))
@settings(max_examples=100)
def test_evaluation_is_order_independent(cards: list[PokerCard], permutation_index: int) -> None:
    expected = evaluate_combination(cards)
    variants = list(permutations(cards))
    actual = evaluate_combination(list(variants[permutation_index % len(variants)]))
    assert (actual.kind, actual.pattern, actual.rank_key) == (expected.kind, expected.pattern, expected.rank_key)
