from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import itertools
import random
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
RANK_LABELS = {
    "J": "Jack",
    "Q": "Queen",
    "K": "King",
    "A": "Ace",
}


class PokerGameError(Exception):
    """Raised when a player tries to perform an invalid remi poker action."""


class PokerStatus(str, Enum):
    WAITING = "waiting"
    PLAYING = "playing"
    FINISHED = "finished"


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


@dataclass
class PokerPlayer:
    user_id: int
    name: str
    hand: list[PokerCard] = field(default_factory=list)
    passed: bool = False
    finished: bool = False
    eliminated_by_bomb: bool = False


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


@dataclass
class PokerActionResult:
    public_messages: list[str]
    winner_ids: list[int] = field(default_factory=list)
    loser_id: int | None = None


class PokerGame:
    min_players = 2
    max_players = 4
    max_redeal_attempts = 20

    def __init__(self) -> None:
        self.status = PokerStatus.WAITING
        self.players: list[PokerPlayer] = []
        self.turn_index = 0
        self.last_play: PokerCombination | None = None
        self.last_play_player_id: int | None = None
        self.cleared_last_play: PokerCombination | None = None
        self.cleared_last_play_player_id: int | None = None
        self.round_pattern: str | None = None
        self.passed_user_ids: set[int] = set()
        self.winner_ids: list[int] = []
        self.loser_id: int | None = None
        self.discarded_start_cards: list[PokerCard] = []
        self.redeal_count = 0

    def add_player(self, user_id: int, name: str) -> None:
        if self.status != PokerStatus.WAITING:
            raise PokerGameError("Game sudah dimulai, pemain baru belum bisa masuk.")
        if self.get_player(user_id) is not None:
            raise PokerGameError("Kamu sudah masuk lobby remi poker.")
        if len(self.players) >= self.max_players:
            raise PokerGameError(f"Lobby penuh. Maksimal {self.max_players} pemain.")
        self.players.append(PokerPlayer(user_id=user_id, name=name))

    def start(self) -> list[str]:
        if self.status != PokerStatus.WAITING:
            raise PokerGameError("Game ini sudah dimulai.")
        if len(self.players) < self.min_players:
            raise PokerGameError(f"Butuh minimal {self.min_players} pemain untuk mulai.")

        messages = []
        for attempt in range(self.max_redeal_attempts):
            self._reset_round_state()
            deck = self._build_deck()
            random.shuffle(deck)
            self._deal(deck)
            first_index = self._find_first_turn_index()
            self.turn_index = first_index
            if not self._has_four_twos():
                break
            messages.append("Redeal karena ada pemain memegang 4 poker.")
            self.redeal_count += 1
        else:
            raise PokerGameError("Redeal terlalu sering karena 4 poker. Coba mulai ulang game.")

        self._discard_rank_threes()
        for player in self.players:
            player.hand = self._sort_cards(player.hand)

        self.status = PokerStatus.PLAYING
        first_player = self.current_player
        messages.extend(
            [
                f"Game Remi Poker dimulai dengan {len(self.players)} pemain.",
                f"Semua kartu 3 dibuang. Rank terendah yang dimainkan adalah 4.",
                f"Giliran pertama: {first_player.name}.",
            ]
        )
        return messages

    @property
    def current_player(self) -> PokerPlayer:
        self._ensure_playing()
        return self.players[self.turn_index]

    def get_player(self, user_id: int) -> PokerPlayer | None:
        return next((player for player in self.players if player.user_id == user_id), None)

    def hand_for(self, user_id: int) -> list[PokerCard]:
        return list(self._require_player(user_id).hand)

    def active_players(self) -> list[PokerPlayer]:
        return [player for player in self.players if not player.finished and not player.eliminated_by_bomb]

    def playable_cards_for(self, user_id: int) -> list[int]:
        player = self._require_player(user_id)
        return [index for index, _card in enumerate(player.hand)]

    def play_cards(self, user_id: int, card_numbers: list[int]) -> PokerActionResult:
        self._ensure_turn(user_id)
        player = self.current_player
        if not card_numbers:
            raise PokerGameError("Pilih minimal 1 kartu.")
        if len(card_numbers) > 5:
            raise PokerGameError("Maksimal memainkan 5 kartu.")
        if len(set(card_numbers)) != len(card_numbers):
            raise PokerGameError("Nomor kartu tidak boleh duplikat.")
        if any(number < 1 or number > len(player.hand) for number in card_numbers):
            raise PokerGameError("Ada nomor kartu yang tidak ada di tanganmu.")

        cards = [player.hand[number - 1] for number in sorted(card_numbers)]
        combination = evaluate_combination(cards)
        self._validate_play(combination)

        previous_player_id = self.last_play_player_id
        for card in cards:
            player.hand.remove(card)

        self.last_play = combination
        self.last_play_player_id = player.user_id
        self.cleared_last_play = None
        self.cleared_last_play_player_id = None
        self.round_pattern = combination.pattern
        self.passed_user_ids.clear()

        messages = [f"{player.name} memainkan {combination.label}."]

        if combination.is_bomb and previous_player_id is not None and previous_player_id != player.user_id:
            loser = self._require_player(previous_player_id)
            loser.eliminated_by_bomb = True
            self.loser_id = loser.user_id
            self.status = PokerStatus.FINISHED
            self.winner_ids = [p.user_id for p in self.players if p.user_id != loser.user_id]
            messages.append(f"{loser.name} terkena bombcard dan kalah.")
            messages.append(self._winner_text())
            return PokerActionResult(messages, self.winner_ids, self.loser_id)

        if not player.hand:
            player.finished = True
            self.winner_ids.append(player.user_id)
            messages.append(f"{player.name} menghabiskan kartu dan aman sebagai winner.")

        if self._finish_if_only_one_loser_left(messages):
            return PokerActionResult(messages, self.winner_ids, self.loser_id)

        self._advance_to_next_contender(messages)
        return PokerActionResult(messages, self.winner_ids, self.loser_id)

    def pass_turn(self, user_id: int) -> PokerActionResult:
        self._ensure_turn(user_id)
        if self.last_play is None or self.last_play_player_id == user_id:
            raise PokerGameError("Kamu sedang membuka ronde, jadi belum bisa pass.")

        player = self.current_player
        self.passed_user_ids.add(player.user_id)
        messages = [f"{player.name} pass."]

        active_ids = {active.user_id for active in self.active_players()}
        expected_passers = active_ids - {self.last_play_player_id}
        if expected_passers and expected_passers.issubset(self.passed_user_ids):
            last_player = self._require_player(self.last_play_player_id)
            if last_player.user_id in active_ids:
                starter = last_player
                self.turn_index = self.players.index(starter)
            else:
                starter = self._set_turn_to_next_active_after(self.players.index(last_player))
            self.last_play = None
            self.last_play_player_id = None
            self.round_pattern = None
            self.passed_user_ids.clear()
            messages.append(f"Table clear. {starter.name} membuka ronde baru.")
        else:
            self._advance_to_next_contender(messages)

        return PokerActionResult(messages, self.winner_ids, self.loser_id)

    def timeout_current_player(self) -> PokerActionResult:
        self._ensure_playing()
        player = self.current_player
        if self.last_play is not None and self.last_play_player_id != player.user_id:
            result = self.pass_turn(player.user_id)
            result.public_messages[0] = f"{player.name} timeout dan otomatis pass."
            return result

        self._advance_to_next_active_player()
        return PokerActionResult(
            [
                f"{player.name} timeout dan otomatis pass.",
                f"{self.current_player.name} membuka ronde.",
            ],
            self.winner_ids,
            self.loser_id,
        )

    def public_state(self) -> dict[str, object]:
        self._ensure_playing_or_finished()
        current_player_id = None
        current_player_name = None
        if self.status == PokerStatus.PLAYING:
            current_player_id = self.current_player.user_id
            current_player_name = self.current_player.name

        return {
            "status": self.status.value,
            "current_player_id": current_player_id,
            "current_player_name": current_player_name,
            "round_pattern": self.round_pattern or "bebas",
            "last_play": self.visible_last_play.label if self.visible_last_play else "Belum ada",
            "last_play_player_id": self.visible_last_play_player_id,
            "table_cleared": self.last_play is None and self.cleared_last_play is not None,
            "hand_counts": [
                (player.user_id, player.name, len(player.hand), player.finished, player.eliminated_by_bomb)
                for player in self.players
            ],
            "pass_count": len(self.passed_user_ids),
            "winner_ids": list(self.winner_ids),
            "loser_id": self.loser_id,
            "discarded_start_cards": [card.label for card in self.discarded_start_cards],
        }

    def _validate_play(self, combination: PokerCombination) -> None:
        if self.last_play is None:
            return
        if self._is_single_two_bomb_override(combination):
            return
        if combination.pattern != self.round_pattern:
            raise PokerGameError(f"Pola ronde saat ini adalah {self.round_pattern}.")
        if combination.pattern != "five" and combination.kind != self.last_play.kind:
            raise PokerGameError(f"Kamu harus memainkan pola {self.last_play.kind}.")
        if compare_combinations(combination, self.last_play) <= 0:
            raise PokerGameError("Kombinasi itu belum lebih tinggi dari kartu terakhir.")

    def _finish_if_only_one_loser_left(self, messages: list[str]) -> bool:
        active_with_cards = [player for player in self.active_players() if player.hand]
        if len(active_with_cards) == 1:
            loser = active_with_cards[0]
            self.loser_id = loser.user_id
            self.status = PokerStatus.FINISHED
            self.winner_ids = [p.user_id for p in self.players if p.user_id != loser.user_id]
            messages.append(f"{loser.name} menjadi pemain terakhir yang masih memegang kartu dan kalah.")
            messages.append(self._winner_text())
            return True
        return False

    def _winner_text(self) -> str:
        winners = [player.name for player in self.players if player.user_id in self.winner_ids]
        return f"Winner: {', '.join(winners)}."

    def _advance_to_next_active_player(self) -> None:
        active_ids = {player.user_id for player in self.active_players()}
        if not active_ids:
            return
        for _ in range(len(self.players)):
            self.turn_index = (self.turn_index + 1) % len(self.players)
            if self.players[self.turn_index].user_id in active_ids:
                return

    def _advance_to_next_contender(self, messages: list[str]) -> None:
        if not self._should_auto_skip_check():
            self._advance_to_next_active_player()
            messages.append(f"Giliran berikutnya: {self.current_player.name}.")
            return

        last_player = self._require_player(self.last_play_player_id)
        active_ids = {player.user_id for player in self.active_players()}
        start_index = self.players.index(last_player)

        for step in range(1, len(self.players) + 1):
            index = (start_index + step) % len(self.players)
            candidate = self.players[index]
            if candidate.user_id not in active_ids:
                continue

            if candidate.user_id == self.last_play_player_id:
                self._clear_table_for_starter(candidate, messages)
                return

            if candidate.user_id in self.passed_user_ids:
                continue

            if self._player_can_beat_last_play(candidate):
                self.turn_index = index
                messages.append(f"Giliran berikutnya: {candidate.name}.")
                return

            self.passed_user_ids.add(candidate.user_id)
            messages.append(f"{candidate.name} auto-skip karena tidak punya kombinasi yang bisa mengalahkan.")

        starter = self._set_turn_to_next_active_after(start_index)
        self._clear_table_for_starter(starter, messages)

    def _clear_table_for_starter(self, starter: PokerPlayer, messages: list[str]) -> None:
        self.cleared_last_play = self.last_play
        self.cleared_last_play_player_id = self.last_play_player_id
        self.turn_index = self.players.index(starter)
        self.last_play = None
        self.last_play_player_id = None
        self.round_pattern = None
        self.passed_user_ids.clear()
        messages.append(f"Table clear. {starter.name} membuka ronde baru.")

    def _should_auto_skip_check(self) -> bool:
        if self.last_play is None:
            return False
        return self.last_play.pattern in {"pair", "three_of_a_kind"}

    @property
    def visible_last_play(self) -> PokerCombination | None:
        return self.last_play or self.cleared_last_play

    @property
    def visible_last_play_player_id(self) -> int | None:
        return self.last_play_player_id or self.cleared_last_play_player_id

    def _player_can_beat_last_play(self, player: PokerPlayer) -> bool:
        if self.last_play is None:
            return True

        candidate_sizes = {
            "pair": (2,),
            "three_of_a_kind": (3,),
        }.get(self.last_play.pattern, ())

        for size in candidate_sizes:
            if len(player.hand) < size:
                continue
            for cards in itertools.combinations(player.hand, size):
                try:
                    combination = evaluate_combination(list(cards))
                    if (
                        combination.pattern == self.last_play.pattern
                        and compare_combinations(combination, self.last_play) > 0
                    ):
                        return True
                except PokerGameError:
                    continue
        return False

    def _is_single_two_bomb_override(self, combination: PokerCombination) -> bool:
        if self.last_play is None:
            return False
        if self.last_play.kind != "single":
            return False
        if self.last_play.cards[0].rank != "2":
            return False
        return combination.kind == "four_of_a_kind"

    def _set_turn_to_next_active_after(self, start_index: int) -> PokerPlayer:
        active_ids = {player.user_id for player in self.active_players()}
        if not active_ids:
            raise PokerGameError("Tidak ada pemain aktif.")
        for step in range(1, len(self.players) + 1):
            index = (start_index + step) % len(self.players)
            if self.players[index].user_id in active_ids:
                self.turn_index = index
                return self.players[index]
        raise PokerGameError("Tidak ada pemain aktif.")

    def _ensure_turn(self, user_id: int) -> None:
        self._ensure_playing()
        if self.current_player.user_id != user_id:
            raise PokerGameError(f"Belum giliranmu. Sekarang giliran {self.current_player.name}.")

    def _ensure_playing(self) -> None:
        if self.status != PokerStatus.PLAYING:
            raise PokerGameError("Game belum berjalan.")

    def _ensure_playing_or_finished(self) -> None:
        if self.status not in {PokerStatus.PLAYING, PokerStatus.FINISHED}:
            raise PokerGameError("Game belum berjalan.")

    def _require_player(self, user_id: int) -> PokerPlayer:
        player = self.get_player(user_id)
        if player is None:
            raise PokerGameError("Kamu belum ikut game remi poker ini.")
        return player

    def _reset_round_state(self) -> None:
        self.turn_index = 0
        self.last_play = None
        self.last_play_player_id = None
        self.cleared_last_play = None
        self.cleared_last_play_player_id = None
        self.round_pattern = None
        self.passed_user_ids.clear()
        self.winner_ids.clear()
        self.loser_id = None
        self.discarded_start_cards.clear()
        for player in self.players:
            player.hand = []
            player.passed = False
            player.finished = False
            player.eliminated_by_bomb = False

    def _deal(self, deck: list[PokerCard]) -> None:
        if len(self.players) == 3:
            for _ in range(17):
                for player in self.players:
                    player.hand.append(deck.pop())
            extra_card = deck.pop()
            first_index = self._find_first_turn_index()
            self.players[first_index].hand.append(extra_card)
            return

        while deck:
            for player in self.players:
                if deck:
                    player.hand.append(deck.pop())

    def _find_first_turn_index(self) -> int:
        triple_three = {PokerCard("3", "diamonds"), PokerCard("3", "clubs"), PokerCard("3", "hearts")}
        for index, player in enumerate(self.players):
            if triple_three.issubset(set(player.hand)):
                return index
        for index, player in enumerate(self.players):
            if PokerCard("3", "spades") in player.hand:
                return index
        raise PokerGameError("Tidak ada kartu 3 penentu giliran. Deck kemungkinan tidak valid.")

    def _has_four_twos(self) -> bool:
        all_twos = {PokerCard("2", suit) for suit in SUITS}
        return any(all_twos.issubset(set(player.hand)) for player in self.players)

    def _discard_rank_threes(self) -> None:
        self.discarded_start_cards = []
        for player in self.players:
            kept_cards = []
            for card in player.hand:
                if card.rank == "3":
                    self.discarded_start_cards.append(card)
                else:
                    kept_cards.append(card)
            player.hand = kept_cards

    @staticmethod
    def _sort_cards(cards: list[PokerCard]) -> list[PokerCard]:
        return sorted(cards, key=lambda card: (card.playable_rank_value, card.suit_value))

    @staticmethod
    def _build_deck() -> list[PokerCard]:
        return [PokerCard(rank, suit) for rank in RANKS for suit in SUITS]


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
