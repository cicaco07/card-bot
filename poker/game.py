from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import itertools
import random

from .cards import (
    PLAYABLE_RANKS,
    PLAYABLE_RANK_VALUES,
    RANKS,
    RANK_LABELS,
    RANK_VALUES,
    START_THREE_PRIORITY,
    STRAIGHT_RANKS,
    STRAIGHT_RANK_VALUES,
    SUITS,
    SUIT_LABELS,
    SUIT_VALUES,
    PokerCard,
    PokerGameError,
    Rank,
    Suit,
)
from .combinations import PokerCombination, compare_combinations, evaluate_combination


class PokerStatus(str, Enum):
    WAITING = "waiting"
    PLAYING = "playing"
    FINISHED = "finished"


@dataclass
class PokerPlayer:
    user_id: int
    name: str
    hand: list[PokerCard] = field(default_factory=list)
    passed: bool = False
    finished: bool = False
    eliminated_by_bomb: bool = False


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
        self.bomb_duel_original_target_id: int | None = None
        self.bomb_duel_current_victim_id: int | None = None
        self.bomb_duel_current_bomber_id: int | None = None
        self.bomb_duel_passed_user_ids: set[int] = set()
        self.bomb_finish_bomber_id: int | None = None
        self.bomb_finish_loser_id: int | None = None
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

        start_card_messages = self._start_card_messages()
        self._reorder_players_by_start_cards()
        self.turn_index = 0
        self._discard_rank_threes()
        for player in self.players:
            player.hand = self._sort_cards(player.hand)

        self.status = PokerStatus.PLAYING
        first_player = self.current_player
        messages.extend(
            [
                f"Game Remi Poker dimulai dengan {len(self.players)} pemain.",
                *start_card_messages,
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
        previous_combination = self.last_play
        for card in cards:
            player.hand.remove(card)

        self.last_play = combination
        self.last_play_player_id = player.user_id
        self.cleared_last_play = None
        self.cleared_last_play_player_id = None
        self.round_pattern = "bomb" if self.bomb_duel_active else combination.pattern
        self.passed_user_ids.clear()

        messages = [f"{player.name} memainkan {combination.label}."]

        if combination.is_bomb and self.bomb_duel_active:
            previous_bomber_id = self.bomb_duel_current_bomber_id
            self.bomb_duel_current_victim_id = previous_bomber_id
            self.bomb_duel_current_bomber_id = player.user_id
            self.bomb_duel_passed_user_ids.clear()
            victim = self._require_player(previous_bomber_id)
            messages.append(
                f"{player.name} membalas bomb. Target bomb berpindah ke {victim.name}."
            )
            self._advance_to_next_bomb_contender(messages)
            return PokerActionResult(messages, self.winner_ids, self.loser_id)

        if self._should_start_bomb_duel(combination, previous_player_id, previous_combination):
            self.bomb_duel_original_target_id = previous_player_id
            self.bomb_duel_current_victim_id = previous_player_id
            self.bomb_duel_current_bomber_id = player.user_id
            self.bomb_duel_passed_user_ids.clear()
            self.round_pattern = "bomb"
            target = self._require_player(previous_player_id)
            messages.append(
                f"{player.name} membuka adu bomb. Jika tidak ada bomb lebih tinggi, {target.name} terkena bomb."
            )
            self._advance_to_next_bomb_contender(messages)
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
        if self.bomb_duel_active:
            return self._pass_bomb_duel(user_id)

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
            "bomb_duel_active": self.bomb_duel_active,
            "bomb_duel_original_target_id": self.bomb_duel_original_target_id,
            "bomb_duel_current_victim_id": self.bomb_duel_current_victim_id,
            "bomb_duel_current_bomber_id": self.bomb_duel_current_bomber_id,
            "bomb_finish_bomber_id": self.bomb_finish_bomber_id,
            "bomb_finish_loser_id": self.bomb_finish_loser_id,
            "hand_counts": [
                (player.user_id, player.name, len(player.hand), player.finished, player.eliminated_by_bomb)
                for player in self.players
            ],
            "pass_count": len(self.bomb_duel_passed_user_ids if self.bomb_duel_active else self.passed_user_ids),
            "winner_ids": list(self.winner_ids),
            "loser_id": self.loser_id,
            "discarded_start_cards": [card.label for card in self.discarded_start_cards],
        }

    def _validate_play(self, combination: PokerCombination) -> None:
        if self.last_play is None:
            return
        if self.bomb_duel_active:
            if not combination.is_bomb:
                raise PokerGameError("Adu bomb hanya bisa dilawan dengan bombcard yang lebih besar.")
            if compare_combinations(combination, self.last_play) <= 0:
                raise PokerGameError("Bombcard itu belum lebih tinggi dari bomb terakhir.")
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
            self.winner_ids.extend(
                p.user_id
                for p in self.players
                if p.user_id not in self.winner_ids and p.user_id != loser.user_id
            )
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

    def _advance_to_next_bomb_contender(self, messages: list[str]) -> None:
        if self.bomb_duel_current_bomber_id is None:
            return

        active_ids = {player.user_id for player in self.active_players()}
        contender_ids = active_ids - {self.bomb_duel_current_bomber_id}
        remaining_ids = contender_ids - self.bomb_duel_passed_user_ids
        if not remaining_ids:
            self._finish_bomb_duel(messages)
            return

        start_index = self.players.index(self._require_player(self.bomb_duel_current_bomber_id))
        for step in range(1, len(self.players) + 1):
            index = (start_index + step) % len(self.players)
            candidate = self.players[index]
            if candidate.user_id in remaining_ids:
                self.turn_index = index
                messages.append(f"Giliran berikutnya: {candidate.name}.")
                return

        self._finish_bomb_duel(messages)

    def _pass_bomb_duel(self, user_id: int) -> PokerActionResult:
        player = self.current_player
        self.bomb_duel_passed_user_ids.add(user_id)
        messages = [f"{player.name} pass adu bomb."]
        self._advance_to_next_bomb_contender(messages)
        return PokerActionResult(messages, self.winner_ids, self.loser_id)

    def _finish_bomb_duel(self, messages: list[str]) -> None:
        if self.bomb_duel_current_victim_id is None or self.bomb_duel_current_bomber_id is None:
            raise PokerGameError("State adu bomb tidak valid.")

        loser = self._require_player(self.bomb_duel_current_victim_id)
        bomber = self._require_player(self.bomb_duel_current_bomber_id)
        loser.eliminated_by_bomb = True
        self.loser_id = loser.user_id
        self.bomb_finish_loser_id = loser.user_id
        self.bomb_finish_bomber_id = bomber.user_id
        self.status = PokerStatus.FINISHED

        ordered_winners = list(self.winner_ids)
        if bomber.user_id not in ordered_winners and bomber.user_id != loser.user_id:
            ordered_winners.append(bomber.user_id)
        ordered_winners.extend(
            player.user_id
            for player in self.players
            if player.user_id not in ordered_winners and player.user_id != loser.user_id
        )
        self.winner_ids = ordered_winners
        messages.append(f"{loser.name} terkena bombcard dari {bomber.name} dan kalah.")
        messages.append(self._winner_text())

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
        if self.last_play_player_id is None:
            return False
        last_player = self._require_player(self.last_play_player_id)
        if not last_player.hand:
            return False
        return combination.is_bomb

    def _should_start_bomb_duel(
        self,
        combination: PokerCombination,
        previous_player_id: int | None,
        previous_combination: PokerCombination | None,
    ) -> bool:
        if not combination.is_bomb or previous_player_id is None or previous_player_id == self.current_player.user_id:
            return False
        if previous_combination is None:
            return False
        previous_player = self._require_player(previous_player_id)
        if not previous_player.hand:
            return False
        if self._is_single_two_play(previous_combination):
            return True
        return previous_combination.pattern == "five"

    @staticmethod
    def _is_single_two_play(combination: PokerCombination) -> bool:
        return combination.kind == "single" and combination.cards[0].rank == "2"

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
        self.bomb_duel_original_target_id = None
        self.bomb_duel_current_victim_id = None
        self.bomb_duel_current_bomber_id = None
        self.bomb_duel_passed_user_ids.clear()
        self.bomb_finish_bomber_id = None
        self.bomb_finish_loser_id = None
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
        best_index: int | None = None
        best_priority: tuple[int, int] | None = None
        for index, player in enumerate(self.players):
            priority = self._start_card_priority(player)
            if priority is None:
                continue
            if best_priority is None or priority > best_priority:
                best_index = index
                best_priority = priority
        if best_index is not None:
            return best_index
        raise PokerGameError("Tidak ada kartu 3 penentu giliran. Deck kemungkinan tidak valid.")

    def _reorder_players_by_start_cards(self) -> None:
        original_order = {player.user_id: index for index, player in enumerate(self.players)}
        self.players.sort(
            key=lambda player: (
                self._start_card_priority(player) or (-1, -1),
                -original_order[player.user_id],
            ),
            reverse=True,
        )

    def _start_card_messages(self) -> list[str]:
        rows = []
        for player in self.players:
            threes = self._rank_three_cards(player)
            labels = ", ".join(card.label for card in threes) if threes else "Tidak ada"
            rows.append(f"{player.name}: {labels}")
        order = sorted(
            self.players,
            key=lambda player: self._start_card_priority(player) or (-1, -1),
            reverse=True,
        )
        return [
            "Kartu 3 penentu giliran: " + " | ".join(rows) + ".",
            "Urutan awal berdasarkan kartu 3: " + " -> ".join(player.name for player in order) + ".",
        ]

    @staticmethod
    def _rank_three_cards(player: PokerPlayer) -> list[PokerCard]:
        return sorted(
            [card for card in player.hand if card.rank == "3"],
            key=lambda card: card.suit_value,
            reverse=True,
        )

    def _start_card_priority(self, player: PokerPlayer) -> tuple[int, int] | None:
        threes = self._rank_three_cards(player)
        if not threes:
            return None
        triple_three = {PokerCard("3", "diamonds"), PokerCard("3", "clubs"), PokerCard("3", "hearts")}
        if triple_three.issubset(set(player.hand)):
            return 4, len(threes)
        highest_three = threes[0]
        return START_THREE_PRIORITY[highest_three.suit], len(threes)

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

    @property
    def bomb_duel_active(self) -> bool:
        return (
            self.status == PokerStatus.PLAYING
            and self.bomb_duel_current_bomber_id is not None
            and self.bomb_duel_current_victim_id is not None
        )
