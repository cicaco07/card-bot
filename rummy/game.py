"""Pure rummy engine independent from Discord."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from itertools import combinations
import random

from .cards import RANKS, SUITS, RummyCard


class RummyGameError(Exception):
    """Raised when a player tries to perform an invalid rummy action."""


class RummyStatus(str, Enum):
    WAITING = "waiting"
    PLAYING = "playing"
    FINISHED = "finished"


@dataclass
class RummyPlayer:
    user_id: int
    name: str
    hand: list[RummyCard] = field(default_factory=list)
    opened_melds: list[tuple[RummyCard, ...]] = field(default_factory=list)
    had_opened_meld_before_turn: bool = False


@dataclass
class RummyActionResult:
    public_messages: list[str]
    scores: dict[int, int] = field(default_factory=dict)
    closed_user_id: int | None = None


class RummyGame:
    min_players = 2
    max_players = 4
    starting_hand_size = 7
    max_discard_depth = 3

    def __init__(self) -> None:
        self.status = RummyStatus.WAITING
        self.players: list[RummyPlayer] = []
        self.deck: list[RummyCard] = []
        self.discard_pile: list[RummyCard] = []
        self.turn_index = 0
        self.awaiting_discard_user_id: int | None = None
        self.last_draw_source: str | None = None
        self.scores: dict[int, int] = {}
        self.closed_user_id: int | None = None
        self.closed_card: RummyCard | None = None
        self.go_rummy_user_id: int | None = None

    def add_player(self, user_id: int, name: str) -> None:
        if self.status != RummyStatus.WAITING:
            raise RummyGameError("Game sudah dimulai, pemain baru belum bisa masuk.")
        if self.get_player(user_id) is not None:
            raise RummyGameError("Kamu sudah masuk lobby rummy.")
        if len(self.players) >= self.max_players:
            raise RummyGameError(f"Lobby penuh. Maksimal {self.max_players} pemain.")
        self.players.append(RummyPlayer(user_id, name))

    def start(self) -> list[str]:
        if self.status != RummyStatus.WAITING:
            raise RummyGameError("Game ini sudah dimulai.")
        if len(self.players) < self.min_players:
            raise RummyGameError(f"Butuh minimal {self.min_players} pemain untuk mulai.")

        self.deck = self._build_deck()
        random.shuffle(self.deck)
        for player in self.players:
            player.hand = [self.deck.pop() for _ in range(self.starting_hand_size)]
            player.hand = self._sort_cards(player.hand)
            player.opened_melds = []
            player.had_opened_meld_before_turn = False
        self.discard_pile = []
        self.turn_index = 0
        self.awaiting_discard_user_id = None
        self.last_draw_source = None
        self.scores = {}
        self.closed_user_id = None
        self.closed_card = None
        self.go_rummy_user_id = None
        self.status = RummyStatus.PLAYING
        return [
            f"Game Rummy dimulai dengan {len(self.players)} pemain.",
            f"Setiap pemain mendapat {self.starting_hand_size} kartu.",
            f"Giliran pertama: {self.current_player.name}. Ambil kartu dari deck.",
        ]

    @property
    def current_player(self) -> RummyPlayer:
        self._ensure_playing()
        return self.players[self.turn_index]

    def get_player(self, user_id: int) -> RummyPlayer | None:
        return next((player for player in self.players if player.user_id == user_id), None)

    def hand_for(self, user_id: int) -> list[RummyCard]:
        return list(self._require_player(user_id).hand)

    def visible_discards(self) -> list[RummyCard]:
        return list(reversed(self.discard_pile[-self.max_discard_depth :]))

    def draw_from_deck(self, user_id: int) -> RummyActionResult:
        self._ensure_draw_turn(user_id)
        if not self.deck:
            return self._finish("Deck habis. Perhitungan skor dimulai.")
        player = self.current_player
        player.had_opened_meld_before_turn = bool(player.opened_melds)
        player.hand.append(self.deck.pop())
        player.hand = self._sort_cards(player.hand)
        self.awaiting_discard_user_id = user_id
        self.last_draw_source = "deck"
        return RummyActionResult([f"{player.name} mengambil 1 kartu dari deck."])

    def draw_from_discard(self, user_id: int, depth: int) -> RummyActionResult:
        self._ensure_draw_turn(user_id)
        discards = self.visible_discards()
        if depth < 1 or depth > len(discards):
            raise RummyGameError("Kartu buangan itu tidak tersedia dalam batas 3 kartu teratas.")
        player = self.current_player
        target_card = discards[depth - 1]
        supporting_cards = self._discard_draw_meld(player.hand, target_card)
        if supporting_cards is None:
            raise RummyGameError("Kartu buangan hanya boleh diambil jika langsung melengkapi meld dari minimal 2 kartu tangan.")
        player.had_opened_meld_before_turn = bool(player.opened_melds)
        picked_cards = self.discard_pile[-depth:]
        del self.discard_pile[-depth:]
        for card in supporting_cards:
            player.hand.remove(card)
        opened_meld = (*supporting_cards, target_card)
        player.opened_melds.append(tuple(opened_meld))
        player.hand.extend(picked_cards[1:])
        player.hand = self._sort_cards(player.hand)
        self.awaiting_discard_user_id = user_id
        self.last_draw_source = "discard"
        meld_text = ", ".join(card.label for card in opened_meld)
        return RummyActionResult(
            [
                f"{player.name} mengambil {depth} kartu dari buangan dengan target {target_card.label}.",
                f"Meld bukti {player.name} dibuka dan dikunci: {meld_text}.",
            ]
        )

    def lay_down_meld(self, user_id: int, card_numbers: list[int]) -> RummyActionResult:
        self._ensure_discard_turn(user_id)
        player = self.current_player
        if len(card_numbers) < 3:
            raise RummyGameError("Pilih minimal 3 kartu untuk menurunkan meld.")
        if len(set(card_numbers)) != len(card_numbers):
            raise RummyGameError("Nomor kartu meld tidak boleh duplikat.")
        if any(number < 1 or number > len(player.hand) for number in card_numbers):
            raise RummyGameError("Ada nomor kartu meld yang tidak tersedia di tanganmu.")
        meld = [player.hand[number - 1] for number in sorted(card_numbers)]
        if not is_valid_meld(meld):
            raise RummyGameError("Kartu pilihan belum membentuk run atau set yang valid.")
        for card in meld:
            player.hand.remove(card)
        player.opened_melds.append(tuple(meld))
        meld_text = ", ".join(card.label for card in meld)
        messages = [f"{player.name} menurunkan meld dan menguncinya: {meld_text}."]
        if not player.hand:
            return self._finish(
                f"{player.name} menghabiskan seluruh kartu melalui meld.",
                go_rummy=not player.had_opened_meld_before_turn,
            )
        return RummyActionResult(messages)

    def lay_off_cards(
        self,
        user_id: int,
        target_user_id: int,
        meld_index: int,
        card_numbers: list[int],
    ) -> RummyActionResult:
        self._ensure_discard_turn(user_id)
        player = self.current_player
        if not card_numbers:
            raise RummyGameError("Pilih minimal 1 kartu untuk digabungkan ke meld.")
        if len(set(card_numbers)) != len(card_numbers):
            raise RummyGameError("Nomor kartu gabungan tidak boleh duplikat.")
        if any(number < 1 or number > len(player.hand) for number in card_numbers):
            raise RummyGameError("Ada nomor kartu gabungan yang tidak tersedia di tanganmu.")
        target_player = self._require_player(target_user_id)
        if meld_index < 0 or meld_index >= len(target_player.opened_melds):
            raise RummyGameError("Meld target tidak tersedia.")
        selected_cards = [player.hand[number - 1] for number in sorted(card_numbers)]
        combined_meld = [*target_player.opened_melds[meld_index], *selected_cards]
        if not is_valid_meld(combined_meld):
            raise RummyGameError("Kartu pilihan belum bisa digabungkan ke meld target.")
        for card in selected_cards:
            player.hand.remove(card)
        target_player.opened_melds[meld_index] = tuple(combined_meld)
        cards_text = ", ".join(card.label for card in selected_cards)
        messages = [f"{player.name} menggabungkan {cards_text} ke meld terbuka {target_player.name}."]
        if not player.hand:
            return self._finish(
                f"{player.name} menghabiskan seluruh kartu melalui gabungan meld.",
                go_rummy=not player.had_opened_meld_before_turn,
            )
        return RummyActionResult(messages)

    def discard_card(self, user_id: int, card_number: int, close: bool = False) -> RummyActionResult:
        self._ensure_discard_turn(user_id)
        player = self.current_player
        if card_number < 1 or card_number > len(player.hand):
            raise RummyGameError("Nomor kartu tidak ada di tanganmu.")
        card = player.hand[card_number - 1]
        if card.is_joker and not close:
            raise RummyGameError("Joker tidak boleh dibuang karena akan mengakhiri sesi permainan.")
        if card.rank == "A" and not close and not player.opened_melds:
            raise RummyGameError("Ace belum boleh dibuang sebelum kamu menurunkan minimal satu meld.")

        remaining = player.hand[: card_number - 1] + player.hand[card_number:]
        if close and (not remaining or not can_partition_into_melds(remaining)):
            raise RummyGameError("Closed card hanya valid jika seluruh kartu tersisa sudah menjadi meld.")

        player.hand = remaining
        self.discard_pile.append(card)
        self.awaiting_discard_user_id = None
        source = self.last_draw_source
        self.last_draw_source = None

        if close:
            self.closed_user_id = user_id
            self.closed_card = card
            bonus = closed_card_bonus(card) if source == "deck" else 0
            return self._finish(
                f"{player.name} closed card dengan {card.label} dan mendapat bonus {bonus} poin.",
                bonus,
                go_rummy=not player.had_opened_meld_before_turn,
            )
        if not player.hand:
            return self._finish(
                f"{player.name} menghabiskan seluruh kartu dengan membuang {card.label}.",
                go_rummy=not player.had_opened_meld_before_turn,
            )
        if not self.deck:
            return self._finish(f"{player.name} membuang {card.label}. Deck habis. Perhitungan skor dimulai.")

        self.turn_index = (self.turn_index + 1) % len(self.players)
        return RummyActionResult(
            [
                f"{player.name} membuang {card.label} setelah mengambil dari {source}.",
                f"Giliran berikutnya: {self.current_player.name}.",
            ]
        )

    def public_state(self) -> dict[str, object]:
        if self.status == RummyStatus.WAITING:
            raise RummyGameError("Game belum berjalan.")
        current_player_id = self.current_player.user_id if self.status == RummyStatus.PLAYING else None
        return {
            "status": self.status.value,
            "current_player_id": current_player_id,
            "phase": "buang kartu" if self.awaiting_discard_user_id is not None else "ambil kartu",
            "deck_count": len(self.deck),
            "top_discard": self.discard_pile[-1].label if self.discard_pile else "Belum ada",
            "visible_discards": [card.label for card in self.visible_discards()],
            "discard_count": len(self.discard_pile),
            "hand_counts": [(player.user_id, player.name, len(player.hand)) for player in self.players],
            "opened_melds": [
                (player.user_id, player.name, [[card.label for card in meld] for meld in player.opened_melds])
                for player in self.players
            ],
            "scores": dict(self.scores),
            "closed_user_id": self.closed_user_id,
            "closed_card": self.closed_card.label if self.closed_card else None,
            "go_rummy_user_id": self.go_rummy_user_id,
        }

    def _finish(self, message: str, closed_bonus: int = 0, go_rummy: bool = False) -> RummyActionResult:
        self.status = RummyStatus.FINISHED
        self.awaiting_discard_user_id = None
        self.last_draw_source = None
        self.scores = {
            player.user_id: score_hand(player.hand) + sum(card.point_value for meld in player.opened_melds for card in meld)
            for player in self.players
        }
        if self.closed_user_id is not None:
            self.scores[self.closed_user_id] += closed_bonus
        if go_rummy and self.closed_user_id is not None:
            self.go_rummy_user_id = self.closed_user_id
        elif go_rummy:
            self.go_rummy_user_id = next((player.user_id for player in self.players if not player.hand), None)
        if self.go_rummy_user_id is not None:
            self.scores = {user_id: score * 2 for user_id, score in self.scores.items()}
            message += " Go Rummy aktif: seluruh poin ronde dikalikan 2."
        score_text = ", ".join(f"{player.name} {self.scores[player.user_id]:+d}" for player in self.players)
        return RummyActionResult([message, f"Skor ronde: {score_text}."], dict(self.scores), self.closed_user_id)

    def _ensure_draw_turn(self, user_id: int) -> None:
        self._ensure_playing()
        if self.current_player.user_id != user_id:
            raise RummyGameError(f"Belum giliranmu. Sekarang giliran {self.current_player.name}.")
        if self.awaiting_discard_user_id is not None:
            raise RummyGameError("Kamu sudah mengambil kartu. Buang satu kartu terlebih dahulu.")

    def _ensure_discard_turn(self, user_id: int) -> None:
        self._ensure_playing()
        if self.current_player.user_id != user_id:
            raise RummyGameError(f"Belum giliranmu. Sekarang giliran {self.current_player.name}.")
        if self.awaiting_discard_user_id != user_id:
            raise RummyGameError("Ambil satu kartu terlebih dahulu sebelum membuang.")

    def _ensure_playing(self) -> None:
        if self.status != RummyStatus.PLAYING:
            raise RummyGameError("Game belum berjalan.")

    def _require_player(self, user_id: int) -> RummyPlayer:
        player = self.get_player(user_id)
        if player is None:
            raise RummyGameError("Kamu belum ikut game rummy ini.")
        return player

    @staticmethod
    def _discard_draw_meld(hand: list[RummyCard], discard: RummyCard) -> list[RummyCard] | None:
        for size in range(2, len(hand) + 1):
            for selected in combinations(hand, size):
                if is_valid_meld([*selected, discard]):
                    return list(selected)
        return None

    @staticmethod
    def _sort_cards(cards: list[RummyCard]) -> list[RummyCard]:
        return sorted(cards, key=lambda card: (card.is_joker, card.suit_value, card.rank_value if not card.is_joker else 99))

    @staticmethod
    def _build_deck() -> list[RummyCard]:
        return [
            *[RummyCard(rank, suit) for suit in SUITS for rank in RANKS],
            RummyCard("JOKER", joker_color="black"),
            RummyCard("JOKER", joker_color="black"),
            RummyCard("JOKER", joker_color="red"),
            RummyCard("JOKER", joker_color="red"),
        ]


def is_valid_meld(cards: list[RummyCard]) -> bool:
    if len(cards) < 3:
        return False
    normal_cards = [card for card in cards if not card.is_joker]
    jokers = len(cards) - len(normal_cards)
    if not normal_cards:
        return False
    if len({card.rank for card in normal_cards}) == 1:
        return True
    if len({card.suit for card in normal_cards}) != 1:
        return False
    ranks = sorted(card.rank_value for card in normal_cards)
    if len(set(ranks)) != len(ranks):
        return False
    missing = sum(right - left - 1 for left, right in zip(ranks, ranks[1:]))
    return missing <= jokers


def can_partition_into_melds(cards: list[RummyCard]) -> bool:
    frozen = tuple(cards)

    @lru_cache(maxsize=None)
    def solve(remaining: tuple[RummyCard, ...]) -> bool:
        if not remaining:
            return True
        first = remaining[0]
        rest = remaining[1:]
        for size in range(2, len(rest) + 1):
            for selected in combinations(rest, size):
                meld = (first, *selected)
                if not is_valid_meld(list(meld)):
                    continue
                leftovers = list(remaining)
                for card in meld:
                    leftovers.remove(card)
                if solve(tuple(leftovers)):
                    return True
        return False

    return solve(frozen)


def score_hand(cards: list[RummyCard]) -> int:
    @lru_cache(maxsize=None)
    def best_meld_points(remaining: tuple[RummyCard, ...]) -> int:
        best = 0
        for size in range(3, len(remaining) + 1):
            for selected in combinations(remaining, size):
                if not is_valid_meld(list(selected)):
                    continue
                leftovers = list(remaining)
                for card in selected:
                    leftovers.remove(card)
                best = max(best, sum(card.point_value for card in selected) + best_meld_points(tuple(leftovers)))
        return best

    total = sum(card.point_value for card in cards)
    meld_points = best_meld_points(tuple(cards))
    return meld_points - (total - meld_points)


def closed_card_bonus(card: RummyCard) -> int:
    if card.is_joker:
        return 250
    if card.rank == "A":
        return 150
    if card.rank in {"J", "Q", "K"}:
        return 100
    return 50
