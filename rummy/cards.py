"""Card model and rank metadata for the rummy engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Suit = Literal["diamonds", "clubs", "hearts", "spades"]
Rank = Literal["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A", "JOKER"]
JokerColor = Literal["black", "red"]

SUITS: tuple[Suit, ...] = ("diamonds", "clubs", "hearts", "spades")
RANKS: tuple[Rank, ...] = ("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A")
RANK_VALUES = {rank: index for index, rank in enumerate(RANKS)}
SUIT_VALUES = {suit: index for index, suit in enumerate(SUITS)}
SUIT_LABELS = {
    "diamonds": "Diamonds",
    "clubs": "Clubs",
    "hearts": "Hearts",
    "spades": "Spades",
}
RANK_LABELS = {"J": "Jack", "Q": "Queen", "K": "King", "A": "Ace"}


@dataclass(frozen=True)
class RummyCard:
    rank: Rank
    suit: Suit | None = None
    joker_color: JokerColor | None = None

    def __post_init__(self) -> None:
        if self.rank == "JOKER":
            if self.suit is not None or self.joker_color not in {"black", "red"}:
                raise ValueError("Joker harus memiliki warna black atau red tanpa suit.")
        elif self.suit not in SUITS or self.joker_color is not None:
            raise ValueError("Kartu biasa harus memiliki suit dan tidak boleh memiliki warna joker.")

    @property
    def is_joker(self) -> bool:
        return self.rank == "JOKER"

    @property
    def rank_value(self) -> int:
        if self.is_joker:
            raise ValueError("Joker tidak memiliki rank tetap.")
        return RANK_VALUES[self.rank]

    @property
    def suit_value(self) -> int:
        if self.suit is None:
            return len(SUITS)
        return SUIT_VALUES[self.suit]

    @property
    def point_value(self) -> int:
        if self.is_joker:
            return 20
        if self.rank == "A":
            return 15
        if self.rank in {"J", "Q", "K"}:
            return 10
        return 5

    @property
    def label(self) -> str:
        if self.is_joker:
            return f"Joker {self.joker_color.title()}"
        return f"{RANK_LABELS.get(self.rank, self.rank)} of {SUIT_LABELS[self.suit]}"
