from __future__ import annotations

from hypothesis import given, settings, strategies as st

from uno.game import UnoGame


def _total_cards(game: UnoGame) -> int:
    return len(game.deck) + len(game.discard_pile) + sum(len(player.hand) for player in game.players)


# Feature: clean-code-refactor, Property 1: Konservasi total kartu UNO
@given(st.lists(st.booleans(), min_size=1, max_size=40))
@settings(max_examples=100)
def test_total_card_count_stays_constant(actions: list[bool]) -> None:
    game = UnoGame()
    game.add_player(1, "Alice")
    game.add_player(2, "Bob")
    game.start()
    assert _total_cards(game) == 108

    for prefer_play in actions:
        if game.status.value == "finished":
            break
        player = game.current_player
        playable = game.playable_cards_for(player.user_id)
        if prefer_play and playable:
            card_index = playable[0]
            card = player.hand[card_index]
            game.play_card(player.user_id, card_index + 1, "red" if card.is_wild else None)
        else:
            game.draw_card(player.user_id)
        assert _total_cards(game) == 108
