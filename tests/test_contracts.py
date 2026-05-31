from __future__ import annotations

import importlib
import inspect

import bot as root_bot
from cardbot import commands  # noqa: F401
from cardbot.app import main
from cardbot.client import tree
from poker import PokerCard, PokerGame, PokerGameError
from poker.assets import render_play_image, render_poker_hand_image
from poker.game import compare_combinations, evaluate_combination
from rummy import RummyCard, RummyGame, RummyGameError
from uno import Card, UnoGame, UnoGameError
from uno.card_assets import render_card_image, render_hand_image


def test_package_exports_are_stable() -> None:
    assert all((Card, UnoGame, UnoGameError, PokerCard, PokerGame, PokerGameError, RummyCard, RummyGame, RummyGameError))
    assert callable(evaluate_combination)
    assert callable(compare_combinations)


def test_refactored_modules_import_without_cycles() -> None:
    for module_name in [
        "cardbot.changelog",
        "cardbot.client",
        "cardbot.commands",
        "cardbot.constants",
        "cardbot.app",
        "cardbot.sessions",
        "cardbot.state",
        "cardbot.text_utils",
        "cardbot.presentation.uno",
        "cardbot.presentation.poker",
        "cardbot.presentation.rummy",
        "cardbot.timer",
        "cardbot.ui.common",
        "cardbot.ui.log_utils",
        "cardbot.ui.uno",
        "cardbot.ui.poker",
        "cardbot.ui.rummy",
        "poker.cards",
        "poker.combinations",
        "poker.game",
        "poker.assets",
        "rummy.cards",
        "rummy.game",
        "rummy.assets",
        "uno.game",
        "uno.card_assets",
    ]:
        importlib.import_module(module_name)


def test_public_render_signatures_are_stable() -> None:
    assert str(inspect.signature(render_card_image)) == "(card: 'Card', filename: 'str' = 'uno_card.jpg') -> 'tuple[BytesIO, str]'"
    assert str(inspect.signature(render_hand_image)) == "(cards: 'list[Card]', playable_indices: 'set[int]', page: 'int', page_size: 'int' = 25, filename: 'str' = 'uno_hand.jpg') -> 'tuple[BytesIO, str]'"
    assert str(inspect.signature(render_poker_hand_image)) == "(cards: 'list[PokerCard]', page: 'int', selected_numbers: 'set[int] | None' = None, page_size: 'int' = 25, filename: 'str' = 'poker_hand.jpg') -> 'tuple[BytesIO, str]'"
    assert str(inspect.signature(render_play_image)) == "(cards: 'list[PokerCard]', filename: 'str' = 'poker_table.jpg') -> 'tuple[BytesIO, str]'"


def test_slash_command_snapshot() -> None:
    snapshot = [
        (command.name, command.description, [(parameter.name, parameter.required) for parameter in command.parameters])
        for command in tree.get_commands()
    ]
    assert snapshot == [
        ("uno_start", "Tampilkan meja UNO interaktif di channel ini.", []),
        ("changelog", "Cek changelog terbaru CardBot.", []),
        ("publish-changelog", "Kirim changelog terbaru ke channel sebagai bot.", [("channel", False), ("mention_everyone", False)]),
        ("uno_hand", "Fallback: lihat kartu tanganmu secara private.", []),
        ("uno_status", "Fallback: refresh status meja UNO.", []),
        ("uno_play", "Fallback: mainkan kartu berdasarkan nomor di /uno_hand.", [("card_number", True), ("color", False)]),
        ("poker-start", "Tampilkan meja Remi Poker interaktif di channel ini.", [("mode", False), ("rounds", False)]),
        ("poker-hand", "Fallback: lihat kartu Remi Poker tanganmu secara private.", []),
        ("poker-status", "Fallback: refresh status meja Remi Poker.", []),
        ("rummy-start", "Tampilkan meja Rummy interaktif di channel ini.", [("mode", False), ("rounds", False)]),
        ("rummy-hand", "Fallback: lihat kartu Rummy tanganmu secara private.", []),
        ("rummy-status", "Fallback: refresh status meja Rummy.", []),
    ]


def test_app_entry_point_is_callable() -> None:
    assert callable(main)
    assert root_bot.main is main
