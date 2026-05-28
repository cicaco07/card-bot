from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import random
from typing import Literal


Color = Literal["red", "yellow", "green", "blue"]
WildColor = Literal["red", "yellow", "green", "blue"]

COLORS: tuple[Color, ...] = ("red", "yellow", "green", "blue")
COLOR_LABELS: dict[str, str] = {
    "red": "Merah",
    "yellow": "Kuning",
    "green": "Hijau",
    "blue": "Biru",
}


class UnoGameError(Exception):
    """Raised when a player tries to perform an invalid UNO action."""


class GameStatus(str, Enum):
    WAITING = "waiting"
    PLAYING = "playing"
    FINISHED = "finished"


@dataclass(frozen=True)
class Card:
    color: Color | None
    value: str

    @property
    def is_wild(self) -> bool:
        return self.color is None

    @property
    def label(self) -> str:
        if self.is_wild:
            return "Change Color +4" if self.value == "wild_draw4" else "Change Color"

        value_labels = {
            "skip": "Stop",
            "reverse": "Reverse",
            "draw2": "+2",
        }
        color_label = COLOR_LABELS[self.color]
        return f"{color_label} {value_labels.get(self.value, self.value)}"


@dataclass
class Player:
    user_id: int
    name: str
    hand: list[Card] = field(default_factory=list)


@dataclass
class PlayResult:
    public_messages: list[str]
    winner_id: int | None = None


class UnoGame:
    """Small regular UNO engine designed to be independent from Discord."""

    min_players = 2
    max_players = 10
    starting_hand_size = 7

    def __init__(self) -> None:
        self.status = GameStatus.WAITING
        self.players: list[Player] = []
        self.deck: list[Card] = []
        self.discard_pile: list[Card] = []
        self.current_color: Color | None = None
        self.turn_index = 0
        self.direction = 1
        self.pending_uno_user_ids: set[int] = set()

    def add_player(self, user_id: int, name: str) -> None:
        if self.status != GameStatus.WAITING:
            raise UnoGameError("Game sudah dimulai, pemain baru belum bisa masuk.")
        if self.get_player(user_id) is not None:
            raise UnoGameError("Kamu sudah masuk lobby UNO.")
        if len(self.players) >= self.max_players:
            raise UnoGameError(f"Lobby penuh. Maksimal {self.max_players} pemain.")
        self.players.append(Player(user_id=user_id, name=name))

    def start(self) -> list[str]:
        if self.status != GameStatus.WAITING:
            raise UnoGameError("Game ini sudah dimulai.")
        if len(self.players) < self.min_players:
            raise UnoGameError(f"Butuh minimal {self.min_players} pemain untuk mulai.")

        self.deck = self._build_deck()
        random.shuffle(self.deck)

        for player in self.players:
            player.hand = [self._draw_one() for _ in range(self.starting_hand_size)]

        first_card = self._draw_initial_card()
        self.discard_pile.append(first_card)
        self.current_color = first_card.color
        self.turn_index = 0
        self.direction = 1
        self.pending_uno_user_ids.clear()
        self.status = GameStatus.PLAYING

        return [
            f"Game UNO dimulai dengan {len(self.players)} pemain.",
            f"Kartu pertama: {first_card.label}.",
            f"Giliran pertama: {self.current_player.name}.",
        ]

    @property
    def current_player(self) -> Player:
        self._ensure_playing()
        return self.players[self.turn_index]

    @property
    def top_card(self) -> Card:
        self._ensure_playing()
        return self.discard_pile[-1]

    def get_player(self, user_id: int) -> Player | None:
        return next((player for player in self.players if player.user_id == user_id), None)

    def hand_for(self, user_id: int) -> list[Card]:
        player = self._require_player(user_id)
        return list(player.hand)

    def can_play(self, card: Card) -> bool:
        top = self.top_card
        if card.is_wild:
            return True
        return card.color == self.current_color or card.value == top.value

    def playable_cards_for(self, user_id: int) -> list[int]:
        player = self._require_player(user_id)
        return [index for index, card in enumerate(player.hand) if self.can_play(card)]

    def play_card(
        self,
        user_id: int,
        card_number: int,
        chosen_color: WildColor | None = None,
    ) -> PlayResult:
        self._ensure_turn(user_id)
        player = self.current_player

        if card_number < 1 or card_number > len(player.hand):
            raise UnoGameError("Nomor kartu tidak ada di tanganmu.")

        card = player.hand[card_number - 1]
        if not self.can_play(card):
            raise UnoGameError(
                f"Kartu {card.label} tidak bisa dimainkan. Cocokkan warna, angka/aksi, atau gunakan Change Color."
            )
        if card.is_wild and chosen_color not in COLORS:
            raise UnoGameError("Kartu Change Color butuh pilihan warna: red, yellow, green, atau blue.")
        if not card.is_wild and chosen_color is not None:
            raise UnoGameError("Pilihan warna hanya dipakai untuk kartu Change Color.")
        if len(player.hand) == 1 and player.user_id in self.pending_uno_user_ids:
            raise UnoGameError("Kamu harus menekan tombol UNO! dulu sebelum memainkan kartu terakhir.")

        player.hand.pop(card_number - 1)
        self.discard_pile.append(card)
        self.current_color = chosen_color if card.is_wild else card.color

        messages = [f"{player.name} memainkan {card.label}."]
        if card.is_wild:
            messages.append(f"Warna diganti menjadi {COLOR_LABELS[self.current_color]}.")

        if not player.hand:
            self.pending_uno_user_ids.discard(player.user_id)
            self.status = GameStatus.FINISHED
            messages.append(f"{player.name} menang. GG, meja virtual bergetar.")
            return PlayResult(messages, winner_id=player.user_id)

        if len(player.hand) == 1:
            self.pending_uno_user_ids.add(player.user_id)
            messages.append(f"{player.name} tersisa 1 kartu dan harus menekan tombol UNO!")
        else:
            self.pending_uno_user_ids.discard(player.user_id)

        messages.extend(self._apply_card_effect(card))
        if self.status == GameStatus.PLAYING:
            messages.append(f"Giliran berikutnya: {self.current_player.name}.")
        return PlayResult(messages)

    def draw_card(self, user_id: int) -> PlayResult:
        self._ensure_turn(user_id)
        player = self.current_player
        card = self._draw_one()
        player.hand.append(card)
        self.pending_uno_user_ids.discard(player.user_id)

        messages = [f"{player.name} mengambil 1 kartu."]
        if self.can_play(card):
            messages.append("Kartu yang baru diambil bisa dimainkan. Buka kartu tanganmu jika ingin memainkannya.")
        else:
            self._advance_turn()
            messages.append(f"Kartu belum cocok. Giliran berpindah ke {self.current_player.name}.")
        return PlayResult(messages)

    def pass_turn(self, user_id: int) -> PlayResult:
        self._ensure_turn(user_id)
        player = self.current_player
        if self.playable_cards_for(user_id):
            raise UnoGameError("Kamu masih punya kartu yang bisa dimainkan, jadi belum bisa pass.")
        self._advance_turn()
        return PlayResult([f"{player.name} pass.", f"Giliran berikutnya: {self.current_player.name}."])

    def call_uno(self, user_id: int) -> PlayResult:
        self._ensure_playing()
        player = self._require_player(user_id)
        if len(player.hand) != 1:
            raise UnoGameError("Tombol UNO! hanya bisa ditekan saat kamu tersisa tepat 1 kartu.")
        if player.user_id not in self.pending_uno_user_ids:
            raise UnoGameError("Kamu sudah menekan UNO! untuk kartu terakhir ini.")

        self.pending_uno_user_ids.discard(player.user_id)
        return PlayResult([f"{player.name} menekan tombol UNO!"])

    def challenge_uno(self, challenger_user_id: int, target_user_id: int | None = None) -> PlayResult:
        self._ensure_playing()
        challenger = self._require_player(challenger_user_id)
        pending_players = [
            player
            for player in self.players
            if player.user_id in self.pending_uno_user_ids and len(player.hand) == 1
        ]
        if not pending_players:
            raise UnoGameError("Tidak ada pemain yang bisa di-challenge. Semua aman, meja tenang.")

        if target_user_id is None:
            if len(pending_players) > 1:
                raise UnoGameError("Ada lebih dari satu pemain yang belum UNO. Pilih target challenge.")
            target = pending_players[0]
        else:
            target = self._require_player(target_user_id)
            if target not in pending_players:
                raise UnoGameError("Target itu tidak sedang lupa menekan UNO.")

        if challenger.user_id == target.user_id:
            raise UnoGameError("Kamu tidak bisa challenge diri sendiri. Tekan UNO! saja, lebih elegan.")

        penalty_cards = [self._draw_one() for _ in range(2)]
        target.hand.extend(penalty_cards)
        self.pending_uno_user_ids.discard(target.user_id)
        return PlayResult(
            [
                f"{challenger.name} berhasil challenge UNO terhadap {target.name}.",
                f"{target.name} lupa menekan UNO! dan mengambil 2 kartu penalti.",
            ]
        )

    def public_state(self) -> dict[str, object]:
        self._ensure_playing()
        return {
            "status": self.status.value,
            "top_card": self.top_card.label,
            "current_color": COLOR_LABELS[self.current_color],
            "current_player_id": self.current_player.user_id,
            "direction": "searah jarum jam" if self.direction == 1 else "berlawanan jarum jam",
            "hand_counts": [(player.user_id, player.name, len(player.hand)) for player in self.players],
            "uno_pending": [
                (player.user_id, player.name)
                for player in self.players
                if player.user_id in self.pending_uno_user_ids and len(player.hand) == 1
            ],
            "deck_count": len(self.deck),
        }

    def _apply_card_effect(self, card: Card) -> list[str]:
        messages: list[str] = []

        if card.value == "skip":
            skipped = self._peek_next_player()
            self._advance_turn(2)
            messages.append(f"{skipped.name} kena Stop dan dilewati.")
        elif card.value == "reverse":
            if len(self.players) == 2:
                skipped = self._peek_next_player()
                self._advance_turn(2)
                messages.append(f"Reverse dalam 2 pemain bertindak seperti Stop. {skipped.name} dilewati.")
            else:
                self.direction *= -1
                self._advance_turn()
                messages.append("Arah permainan dibalik.")
        elif card.value == "draw2":
            target = self._peek_next_player()
            drawn_cards = [self._draw_one() for _ in range(2)]
            target.hand.extend(drawn_cards)
            self.pending_uno_user_ids.discard(target.user_id)
            self._advance_turn(2)
            messages.append(f"{target.name} mengambil 2 kartu dan dilewati.")
        elif card.value == "wild_draw4":
            target = self._peek_next_player()
            drawn_cards = [self._draw_one() for _ in range(4)]
            target.hand.extend(drawn_cards)
            self.pending_uno_user_ids.discard(target.user_id)
            self._advance_turn(2)
            messages.append(f"{target.name} mengambil 4 kartu dan dilewati.")
        else:
            self._advance_turn()

        return messages

    def _advance_turn(self, steps: int = 1) -> None:
        self.turn_index = (self.turn_index + (self.direction * steps)) % len(self.players)

    def _peek_next_player(self) -> Player:
        return self.players[(self.turn_index + self.direction) % len(self.players)]

    def _require_player(self, user_id: int) -> Player:
        player = self.get_player(user_id)
        if player is None:
            raise UnoGameError("Kamu belum ikut game UNO ini.")
        return player

    def _ensure_playing(self) -> None:
        if self.status != GameStatus.PLAYING:
            raise UnoGameError("Game belum berjalan.")

    def _ensure_turn(self, user_id: int) -> None:
        self._ensure_playing()
        if self.current_player.user_id != user_id:
            raise UnoGameError(f"Belum giliranmu. Sekarang giliran {self.current_player.name}.")

    def _draw_one(self) -> Card:
        if not self.deck:
            self._reshuffle_discard_into_deck()
        if not self.deck:
            raise UnoGameError("Deck habis dan tidak ada discard yang bisa dikocok ulang.")
        return self.deck.pop()

    def _draw_initial_card(self) -> Card:
        for index, card in enumerate(self.deck):
            if card.color is not None and card.value.isdigit():
                return self.deck.pop(index)
        return self._draw_one()

    def _reshuffle_discard_into_deck(self) -> None:
        if len(self.discard_pile) <= 1:
            return
        top_card = self.discard_pile[-1]
        self.deck = self.discard_pile[:-1]
        random.shuffle(self.deck)
        self.discard_pile = [top_card]

    @staticmethod
    def _build_deck() -> list[Card]:
        deck: list[Card] = []
        for color in COLORS:
            deck.append(Card(color, "0"))
            for value in range(1, 10):
                deck.extend([Card(color, str(value)), Card(color, str(value))])
            for action in ("skip", "reverse", "draw2"):
                deck.extend([Card(color, action), Card(color, action)])

        for _ in range(4):
            deck.append(Card(None, "wild"))
            deck.append(Card(None, "wild_draw4"))

        return deck
