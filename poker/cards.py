"""Card model, rank metadata, and errors for the remi poker engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Suit = Literal["diamonds", "clubs", "hearts", "spades"]
Rank = Literal["3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A", "2"]

SUITS: tuple[Suit, ...] = ("diamonds", "clubs", "hearts", "spades")
RANKS: tuple[Rank, ...] = ("3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A", "2")
PLAYABLE_RANKS: tuple[Rank, ...] = ("4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A", "2")
STRAIGHT_RANKS: tuple[Rank, ...] = ("4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A")

RANK_VALUES = {rank: index for index, rank in enumerate(RANKS)}
PLAYABLE_RANK_VALUES = {rank: index for index, rank in enumerate(PLAYABLE_RANKS)}
STRAIGHT_RANK_VALUES = {rank: index for index, rank in enumerate(STRAIGHT_RANKS)}
SUIT_VALUES = {suit: index for index, suit in enumerate(SUITS)}
SUIT_LABELS = {
    "diamonds": "Diamonds",
    "clubs": "Clubs",
    "hearts": "Hearts",
    "spades": "Spades",
}
START_THREE_PRIORITY = {
    "diamonds": 0,
    "clubs": 1,
    "hearts": 2,
    "spades": 3,
}
RANK_LABELS = {
    "J": "Jack",
    "Q": "Queen",
    "K": "King",
    "A": "Ace",
}


class PokerGameError(Exception):
    """Raised when a player tries to perform an invalid remi poker action."""


@dataclass(frozen=True)
class PokerCard:
    rank: Rank
    suit: Suit

    @property
    def rank_value(self) -> int:
        return RANK_VALUES[self.rank]

    @property
    def playable_rank_value(self) -> int:
        if self.rank == "3":
            raise PokerGameError("Kartu 3 tidak bisa dimainkan.")
        return PLAYABLE_RANK_VALUES[self.rank]

    @property
    def suit_value(self) -> int:
        return SUIT_VALUES[self.suit]

    @property
    def label(self) -> str:
        return f"{RANK_LABELS.get(self.rank, self.rank)} of {SUIT_LABELS[self.suit]}"
