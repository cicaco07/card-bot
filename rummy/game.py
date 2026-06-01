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
        self.discarded_by_user_ids: list[int | None] = []
        self.turn_index = 0
        self.awaiting_discard_user_id: int | None = None
        self.last_draw_source: str | None = None
        self.required_discard_meld_card: RummyCard | None = None
        self.required_discard_meld_hand_cards: tuple[RummyCard, ...] = ()
        self.required_discard_meld_size: int | None = None
        self.scores: dict[int, int] = {}
        self.score_breakdowns: dict[int, dict[str, int]] = {}
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
        self.discarded_by_user_ids = []
        self.turn_index = 0
        self.awaiting_discard_user_id = None
        self.last_draw_source = None
        self.required_discard_meld_card = None
        self.required_discard_meld_hand_cards = ()
        self.required_discard_meld_size = None
        self.scores = {}
        self.score_breakdowns = {}
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

    def visible_discard_details(self) -> list[tuple[RummyCard, int | None]]:
        discards = self.visible_discards()
        user_ids = list(reversed(self.discarded_by_user_ids[-self.max_discard_depth :]))
        return list(zip(discards, [*user_ids, *([None] * (len(discards) - len(user_ids)))]))

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
        picked_cards = self.discard_pile[-depth:]
        required_meld_size = 4 if depth == 3 else 3
        if self._discard_draw_meld(player.hand, target_card, picked_cards[1:], required_meld_size) is None:
            raise RummyGameError(
                f"Kartu buangan hanya boleh diambil jika bisa membentuk meld bukti {required_meld_size} kartu "
                "dengan minimal 2 kartu dari tangan."
            )
        player.had_opened_meld_before_turn = bool(player.opened_melds)
        original_hand = tuple(player.hand)
        del self.discard_pile[-depth:]
        del self.discarded_by_user_ids[-depth:]
        player.hand.extend(picked_cards)
        player.hand = self._sort_cards(player.hand)
        self.awaiting_discard_user_id = user_id
        self.last_draw_source = "discard"
        self.required_discard_meld_card = target_card
        self.required_discard_meld_hand_cards = original_hand
        self.required_discard_meld_size = required_meld_size
        return RummyActionResult(
            [
                f"{player.name} mengambil {depth} kartu dari buangan dengan target {target_card.activity_label}.",
                f"{player.name} wajib menurunkan meld bukti {required_meld_size} kartu yang memakai "
                f"{target_card.activity_label} sebelum membuang kartu.",
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
        required_card = self.required_discard_meld_card
        if required_card is not None:
            if len(meld) != self.required_discard_meld_size:
                raise RummyGameError(f"Meld bukti buangan wajib terdiri dari {self.required_discard_meld_size} kartu.")
            if not any(card is required_card for card in meld):
                raise RummyGameError(f"Turunkan meld bukti yang memakai {required_card.label} terlebih dahulu.")
            original_support_count = sum(
                any(card is original_card for original_card in self.required_discard_meld_hand_cards)
                for card in meld
            )
            if original_support_count < 2:
                raise RummyGameError("Meld bukti buangan wajib memakai minimal 2 kartu dari tangan sebelumnya.")
        for card in meld:
            player.hand.remove(card)
        player.opened_melds.append(tuple(meld))
        meld_text = ", ".join(card.activity_label for card in meld)
        if required_card is not None:
            self.required_discard_meld_card = None
            self.required_discard_meld_hand_cards = ()
            self.required_discard_meld_size = None
            messages = [f"{player.name} menurunkan meld bukti dan menguncinya: {meld_text}."]
        else:
            messages = [f"{player.name} menurunkan meld dan menguncinya: {meld_text}."]
        if not player.hand:
            return self._complete_empty_hand_turn(
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
        self._ensure_required_discard_meld_completed()
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
        cards_text = ", ".join(card.activity_label for card in selected_cards)
        messages = [f"{player.name} menggabungkan {cards_text} ke meld terbuka {target_player.name}."]
        if not player.hand:
            return self._complete_empty_hand_turn(
                f"{player.name} menghabiskan seluruh kartu melalui gabungan meld.",
                go_rummy=not player.had_opened_meld_before_turn,
            )
        return RummyActionResult(messages)

    def discard_card(self, user_id: int, card_number: int, close: bool = False) -> RummyActionResult:
        self._ensure_discard_turn(user_id)
        player = self.current_player
        self._ensure_required_discard_meld_completed()
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
        self.discarded_by_user_ids.append(user_id)
        self.awaiting_discard_user_id = None
        source = self.last_draw_source
        self.last_draw_source = None

        if close:
            self.closed_user_id = user_id
            self.closed_card = card
            bonus = closed_card_bonus(card) if source == "deck" else 0
            return self._finish(
                f"{player.name} closed card dengan {card.activity_label} dan mendapat bonus {bonus} poin.",
                bonus,
                go_rummy=not player.had_opened_meld_before_turn,
            )
        if not player.hand:
            return self._complete_empty_hand_turn(
                f"{player.name} menghabiskan seluruh kartu dengan membuang {card.activity_label}.",
                go_rummy=not player.had_opened_meld_before_turn,
            )
        if not self.deck:
            return self._finish(f"{player.name} membuang {card.activity_label}. Deck habis. Perhitungan skor dimulai.")

        next_player = self._advance_to_next_player_with_cards()
        return RummyActionResult(
            [
                f"{player.name} membuang {card.activity_label} setelah mengambil dari {source}.",
                f"Giliran berikutnya: {next_player.name}.",
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
            "required_discard_meld_card": self.required_discard_meld_card.label if self.required_discard_meld_card else None,
            "required_discard_meld_size": self.required_discard_meld_size,
            "deck_count": len(self.deck),
            "top_discard": self.discard_pile[-1].label if self.discard_pile else "Belum ada",
            "visible_discards": [card.label for card in self.visible_discards()],
            "visible_discard_user_ids": [user_id for _card, user_id in self.visible_discard_details()],
            "discard_count": len(self.discard_pile),
            "hand_counts": [(player.user_id, player.name, len(player.hand)) for player in self.players],
            "opened_melds": [
                (player.user_id, player.name, [[card.label for card in meld] for meld in player.opened_melds])
                for player in self.players
            ],
            "scores": dict(self.scores),
            "score_breakdowns": {user_id: dict(details) for user_id, details in self.score_breakdowns.items()},
            "closed_user_id": self.closed_user_id,
            "closed_card": self.closed_card.label if self.closed_card else None,
            "go_rummy_user_id": self.go_rummy_user_id,
        }

    def _finish(self, message: str, closed_bonus: int = 0, go_rummy: bool = False) -> RummyActionResult:
        self.status = RummyStatus.FINISHED
        self.awaiting_discard_user_id = None
        self.last_draw_source = None
        self.required_discard_meld_card = None
        self.required_discard_meld_hand_cards = ()
        self.required_discard_meld_size = None
        self.score_breakdowns = {}
        for player in self.players:
            hand_meld_points, deadwood_points = score_hand_breakdown(player.hand)
            opened_meld_points = sum(card.point_value for meld in player.opened_melds for card in meld)
            player_closed_bonus = closed_bonus if player.user_id == self.closed_user_id else 0
            subtotal = opened_meld_points + hand_meld_points - deadwood_points + player_closed_bonus
            self.score_breakdowns[player.user_id] = {
                "opened_meld_points": opened_meld_points,
                "hand_meld_points": hand_meld_points,
                "deadwood_points": deadwood_points,
                "closed_bonus": player_closed_bonus,
                "subtotal": subtotal,
                "go_rummy_multiplier": 1,
                "total": subtotal,
            }
        if go_rummy:
            self.go_rummy_user_id = self.closed_user_id or next((player.user_id for player in self.players if not player.hand), None)
        if self.go_rummy_user_id is not None:
            for details in self.score_breakdowns.values():
                details["go_rummy_multiplier"] = 2
                details["total"] = details["subtotal"] * 2
            message += " Go Rummy aktif: seluruh poin ronde dikalikan 2."
        self.scores = {user_id: details["total"] for user_id, details in self.score_breakdowns.items()}
        score_text = ", ".join(f"{player.name} {self.scores[player.user_id]:+d}" for player in self.players)
        return RummyActionResult([message, f"Skor ronde: {score_text}."], dict(self.scores), self.closed_user_id)

    def _complete_empty_hand_turn(self, message: str, go_rummy: bool = False) -> RummyActionResult:
        player = self.current_player
        self.awaiting_discard_user_id = None
        self.last_draw_source = None
        if go_rummy and self.go_rummy_user_id is None:
            self.go_rummy_user_id = player.user_id
            message += " Go Rummy aktif untuk perhitungan skor akhir."
        if not self.deck:
            return self._finish(f"{message} Deck habis. Perhitungan skor dimulai.")
        if not any(other.hand for other in self.players):
            return self._finish(f"{message} Seluruh pemain telah menghabiskan kartu. Perhitungan skor dimulai.")
        next_player = self._advance_to_next_player_with_cards()
        return RummyActionResult([message, f"Giliran berikutnya: {next_player.name}."])

    def _advance_to_next_player_with_cards(self) -> RummyPlayer:
        for offset in range(1, len(self.players) + 1):
            next_index = (self.turn_index + offset) % len(self.players)
            if self.players[next_index].hand:
                self.turn_index = next_index
                return self.players[next_index]
        raise RummyGameError("Tidak ada pemain dengan kartu tersisa.")

    def _ensure_required_discard_meld_completed(self) -> None:
        if self.required_discard_meld_card is not None:
            raise RummyGameError(
                f"Turunkan meld bukti yang memakai {self.required_discard_meld_card.label} terlebih dahulu."
            )

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
    def _discard_draw_meld(
        hand: list[RummyCard],
        discard: RummyCard,
        additional_cards: list[RummyCard],
        meld_size: int,
    ) -> list[RummyCard] | None:
        for selected in combinations([*hand, *additional_cards], meld_size - 1):
            if sum(any(card is hand_card for hand_card in hand) for card in selected) < 2:
                continue
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
    meld_points, deadwood_points = score_hand_breakdown(cards)
    return meld_points - deadwood_points


def score_hand_breakdown(cards: list[RummyCard]) -> tuple[int, int]:
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
    return meld_points, total - meld_points


def closed_card_bonus(card: RummyCard) -> int:
    if card.is_joker:
        return 250
    if card.rank == "A":
        return 150
    if card.rank in {"J", "Q", "K"}:
        return 100
    return 50
