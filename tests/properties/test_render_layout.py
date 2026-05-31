from __future__ import annotations

from PIL import Image
from hypothesis import given, settings, strategies as st

from poker.assets import render_poker_hand_image
from poker.game import PokerCard
from uno.card_assets import render_hand_image
from uno.game import Card


def _dimensions(count: int, width: int, height: int, gap: int, header: int) -> tuple[int, int]:
    columns = min(5, count)
    rows = (count + columns - 1) // columns
    return 48 + columns * width + (columns - 1) * gap, 48 + header + rows * height + (rows - 1) * gap


# Feature: clean-code-refactor, Property 7: Parameter render gambar konsisten dengan formula tata letak
@given(st.integers(min_value=1, max_value=25))
@settings(max_examples=100, deadline=None)
def test_render_dimensions_follow_layout_formula(count: int) -> None:
    uno_buffer, _ = render_hand_image([Card("red", "1")] * count, set(), 0)
    poker_buffer, _ = render_poker_hand_image([PokerCard("4", "diamonds")] * count, 0)
    assert Image.open(uno_buffer).mode == "RGB"
    assert Image.open(uno_buffer).size == _dimensions(count, 118, 168, 18, 54)
    assert Image.open(poker_buffer).mode == "RGB"
    assert Image.open(poker_buffer).size == _dimensions(count, 112, 156, 14, 58)
