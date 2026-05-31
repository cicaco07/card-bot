from __future__ import annotations

import asyncio

from cardbot.sessions import PokerSession
from cardbot.timer import poker_turn_timer_worker
from poker.game import PokerCard, PokerPlayer, PokerStatus


def test_timer_worker_invokes_callback_for_the_expected_turn() -> None:
    async def run_worker() -> list[int]:
        called: list[int] = []
        session = PokerSession(channel_id=1, owner_id=1, timer_seconds=0)
        session.game.status = PokerStatus.PLAYING
        session.game.players = [
            PokerPlayer(1, "Alice", [PokerCard("4", "diamonds")]),
            PokerPlayer(2, "Bob", [PokerCard("5", "clubs")]),
        ]
        session.turn_timer_token = 7

        async def on_timeout(current_session: PokerSession) -> None:
            called.append(current_session.game.current_player.user_id)

        await poker_turn_timer_worker(session, 7, 1, on_timeout)
        return called

    assert asyncio.run(run_worker()) == [1]


def test_timer_worker_ignores_stale_token() -> None:
    async def run_worker() -> list[int]:
        called: list[int] = []
        session = PokerSession(channel_id=1, owner_id=1, timer_seconds=0)
        session.game.status = PokerStatus.PLAYING
        session.game.players = [
            PokerPlayer(1, "Alice", [PokerCard("4", "diamonds")]),
            PokerPlayer(2, "Bob", [PokerCard("5", "clubs")]),
        ]
        session.turn_timer_token = 8

        async def on_timeout(current_session: PokerSession) -> None:
            called.append(current_session.game.current_player.user_id)

        await poker_turn_timer_worker(session, 7, 1, on_timeout)
        return called

    assert asyncio.run(run_worker()) == []
