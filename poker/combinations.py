"""Combination evaluation and comparison for the remi poker engine."""

from __future__ import annotations

from dataclasses import dataclass

from .cards import PLAYABLE_RANK_VALUES, STRAIGHT_RANK_VALUES, PokerCard, PokerGameError


@dataclass(frozen=True)
class PokerCombination:
    kind: str
    cards: tuple[PokerCard, ...]
    rank_key: tuple[int, ...]
    label: str

    @property
    def card_count(self) -> int:
        return len(self.cards)

    @property
    def pattern(self) -> str:
        if self.card_count == 5 or self.kind == "four_of_a_kind":
            return "five"
        return self.kind

    @property
    def is_bomb(self) -> bool:
        return self.kind in {"four_of_a_kind", "straight_flush", "royal_flush"}


def evaluate_combination(cards: list[PokerCard]) -> PokerCombination:
    if any(card.rank == "3" for card in cards):
        raise PokerGameError("Kartu 3 sudah dibuang dan tidak bisa dimainkan.")

    sorted_cards = sorted(cards, key=lambda card: (card.playable_rank_value, card.suit_value))
    count = len(sorted_cards)
    ranks = [card.rank for card in sorted_cards]
    suits = [card.suit for card in sorted_cards]
    rank_counts = {rank: ranks.count(rank) for rank in set(ranks)}

    if count == 1:
        card = sorted_cards[0]
        return PokerCombination(
            "single",
            tuple(sorted_cards),
            (card.playable_rank_value, card.suit_value),
            card.label,
        )

    if count == 2 and len(rank_counts) == 1:
        high_suit = max(card.suit_value for card in sorted_cards)
        return PokerCombination("pair", tuple(sorted_cards), (sorted_cards[0].playable_rank_value, high_suit), _cards_label("Pair", sorted_cards))

    if count == 3 and len(rank_counts) == 1:
        return PokerCombination("three_of_a_kind", tuple(sorted_cards), (sorted_cards[0].playable_rank_value,), _cards_label("Three of a Kind", sorted_cards))

    if count == 4 and len(rank_counts) == 1:
        high_suit = max(card.suit_value for card in sorted_cards)
        return PokerCombination(
            "four_of_a_kind",
            tuple(sorted_cards),
            (3, sorted_cards[0].playable_rank_value, high_suit),
            _cards_label("Four of a Kind", sorted_cards),
        )

    if count != 5:
        raise PokerGameError("Kombinasi harus single, pair, three of a kind, four of a kind, atau 5 kartu.")

    is_flush = len(set(suits)) == 1
    straight_info = _straight_key(sorted_cards)
    is_straight = straight_info is not None
    counts = sorted(rank_counts.values(), reverse=True)

    if is_flush and ranks == ["10", "J", "Q", "K", "A"]:
        suit_value = sorted_cards[-1].suit_value
        return PokerCombination("royal_flush", tuple(sorted_cards), (5, suit_value), _cards_label("Royal Flush", sorted_cards))

    if is_flush and is_straight:
        return PokerCombination("straight_flush", tuple(sorted_cards), (4, *straight_info), _cards_label("Straight Flush", sorted_cards))

    if counts == [4, 1]:
        quad_rank = next(rank for rank, amount in rank_counts.items() if amount == 4)
        high_suit = max(card.suit_value for card in sorted_cards if card.rank == quad_rank)
        return PokerCombination(
            "four_of_a_kind",
            tuple(sorted_cards),
            (3, PLAYABLE_RANK_VALUES[quad_rank], high_suit),
            _cards_label("Four of a Kind Bomb", sorted_cards),
        )

    if counts == [3, 2]:
        triple_rank = next(rank for rank, amount in rank_counts.items() if amount == 3)
        high_suit = max(card.suit_value for card in sorted_cards if card.rank == triple_rank)
        return PokerCombination("full_house", tuple(sorted_cards), (2, PLAYABLE_RANK_VALUES[triple_rank], high_suit), _cards_label("Full House", sorted_cards))

    if is_flush:
        descending = tuple(
            value
            for card in sorted(sorted_cards, key=lambda c: (c.playable_rank_value, c.suit_value), reverse=True)
            for value in (card.playable_rank_value, card.suit_value)
        )
        return PokerCombination("flush", tuple(sorted_cards), (1, *descending), _cards_label("Flush", sorted_cards))

    if is_straight:
        return PokerCombination("straight", tuple(sorted_cards), (0, *straight_info), _cards_label("Straight", sorted_cards))

    raise PokerGameError("Kombinasi 5 kartu tidak valid.")


def compare_combinations(left: PokerCombination, right: PokerCombination) -> int:
    if left.pattern != right.pattern:
        raise PokerGameError("Pola kombinasi berbeda.")
    if left.card_count != 5 and left.kind != right.kind:
        if left.kind != "four_of_a_kind" and right.kind != "four_of_a_kind":
            raise PokerGameError("Tipe kombinasi berbeda.")
    if left.pattern == "five":
        left_type = left.rank_key[0]
        right_type = right.rank_key[0]
        if left_type != right_type:
            return 1 if left_type > right_type else -1
    if left.rank_key == right.rank_key:
        return 0
    return 1 if left.rank_key > right.rank_key else -1


def _straight_key(cards: list[PokerCard]) -> tuple[int, int] | None:
    if any(card.rank == "2" for card in cards):
        return None
    rank_values = sorted(STRAIGHT_RANK_VALUES.get(card.rank, -100) for card in cards)
    if -100 in rank_values:
        return None
    if len(set(rank_values)) != 5:
        return None
    if rank_values != list(range(rank_values[0], rank_values[0] + 5)):
        return None
    high_rank_value = rank_values[-1]
    high_cards = [card for card in cards if STRAIGHT_RANK_VALUES[card.rank] == high_rank_value]
    return high_rank_value, max(card.suit_value for card in high_cards)


def _cards_label(prefix: str, cards: list[PokerCard]) -> str:
    return f"{prefix}: {', '.join(card.label for card in cards)}"
