from __future__ import annotations

from hypothesis import given, settings, strategies as st

from uno.game import Card, GameStatus, Player, UnoGame


# Feature: clean-code-refactor, Property 2: Indeks giliran UNO selalu dalam rentang valid
@given(
    player_count=st.integers(min_value=2, max_value=10),
    direction=st.sampled_from([-1, 1]),
    steps=st.lists(st.integers(min_value=1, max_value=4), min_size=1, max_size=100),
)
@settings(max_examples=100)
def test_turn_index_always_stays_in_range(player_count: int, direction: int, steps: list[int]) -> None:
    game = UnoGame()
    game.status = GameStatus.PLAYING
    game.players = [Player(index, str(index), [Card("red", "1")]) for index in range(player_count)]
    game.direction = direction
    for amount in steps:
        game._advance_turn(amount)
        assert 0 <= game.turn_index < len(game.players)
