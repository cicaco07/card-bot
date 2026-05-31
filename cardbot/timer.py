"""Poker turn timer service with an injected timeout callback."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from poker.game import PokerGameError, PokerStatus

from .sessions import PokerSession


TimeoutCallback = Callable[[PokerSession], Awaitable[None]]


def cancel_poker_turn_timer(session: PokerSession) -> None:
    session.turn_timer_token += 1
    current_task = asyncio.current_task()
    if (
        session.turn_timer_task
        and not session.turn_timer_task.done()
        and session.turn_timer_task is not current_task
    ):
        session.turn_timer_task.cancel()
    session.turn_timer_task = None


def schedule_poker_turn_timer(session: PokerSession, on_timeout: TimeoutCallback) -> None:
    cancel_poker_turn_timer(session)
    if session.game.status != PokerStatus.PLAYING:
        return

    try:
        current_player_id = session.game.current_player.user_id
    except PokerGameError:
        return

    session.turn_timer_token += 1
    token = session.turn_timer_token
    session.turn_timer_task = asyncio.create_task(
        poker_turn_timer_worker(session, token, current_player_id, on_timeout)
    )


async def poker_turn_timer_worker(
    session: PokerSession,
    token: int,
    expected_user_id: int,
    on_timeout: TimeoutCallback,
) -> None:
    try:
        await asyncio.sleep(session.timer_seconds)
        if session.turn_timer_token != token or session.game.status != PokerStatus.PLAYING:
            return
        if session.game.current_player.user_id != expected_user_id:
            return
        await on_timeout(session)
    except asyncio.CancelledError:
        return
