"""Shared action-log cleanup for game UI modules."""

from __future__ import annotations

from typing import Protocol


class LogSession(Protocol):
    end_game_votes: set[int]

    def add_log(self, messages: list[str] | str) -> None: ...


def add_action_log(session: LogSession, messages: list[str]) -> None:
    session.end_game_votes.clear()
    clean_messages = [
        message
        for message in messages
        if message and not message.startswith("Giliran berikutnya:")
    ]
    session.add_log(clean_messages)
