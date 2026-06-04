"""Small text formatting helpers with no UI dependencies."""

from __future__ import annotations


def mention(user_id: int) -> str:
    return f"<@{user_id}>"


def format_tournament_total_rounds(total_rounds: int | None) -> str:
    return "endless" if total_rounds is None else str(total_rounds)


def format_tournament_round_progress(current_round: int, total_rounds: int | None) -> str:
    return f"{current_round}/{format_tournament_total_rounds(total_rounds)}"


def format_tournament_round_count(total_rounds: int | None) -> str:
    return "endless" if total_rounds is None else f"{total_rounds} game"


def format_tournament_round_summary(round_number: int, round_points: list[tuple[int, int]]) -> str:
    points_text = ", ".join(f"{mention(user_id)} {points:+d}" for user_id, points in round_points)
    return f"Skor ronde {round_number}: {points_text}."
