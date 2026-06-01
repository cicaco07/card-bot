from __future__ import annotations

import discord

from cardbot.sessions import RummySession
from cardbot.state import rummy_sessions_by_channel
from cardbot.ui.rummy import RummyDiscardSelect, RummyDiscardView
from rummy.cards import RummyCard


def test_discard_view_marks_selected_target_and_requires_confirmation() -> None:
    session = RummySession(channel_id=10, owner_id=1)
    session.game.discard_pile = [RummyCard("4", "hearts"), RummyCard("9", "clubs")]
    rummy_sessions_by_channel[10] = session
    try:
        view = RummyDiscardView(10, 1, selected_depth=2)
        select = next(child for child in view.children if isinstance(child, RummyDiscardSelect))
        button = next(child for child in view.children if isinstance(child, discord.ui.Button))

        assert view.selected_depth == 2
        assert [(option.value, option.default) for option in select.options] == [("1", False), ("2", True)]
        assert button.label == "Konfirmasi Ambil"
    finally:
        rummy_sessions_by_channel.pop(10, None)
