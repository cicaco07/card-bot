from __future__ import annotations

from PIL import Image

from poker.assets import render_play_image, render_poker_hand_image
from poker.game import PokerCard
from uno.card_assets import render_hand_image
from uno.game import Card


def _image_info(rendered: tuple[object, str]) -> tuple[str, tuple[int, int], str]:
    buffer, filename = rendered
    image = Image.open(buffer)
    return image.mode, image.size, filename


def test_uno_hand_layout_formula() -> None:
    assert _image_info(render_hand_image([Card("red", "1")] * 6, set(), 0)) == ("RGB", (710, 456), "uno_hand.jpg")


def test_poker_hand_and_play_layout_formula() -> None:
    poker_cards = [PokerCard("4", "diamonds")] * 6
    assert _image_info(render_poker_hand_image(poker_cards, 0)) == ("RGB", (664, 432), "poker_hand.jpg")
    assert _image_info(render_play_image(poker_cards[:3])) == ("RGB", (412, 262), "poker_table.jpg")
