"""Remi poker text, embed, and visual presentation helpers."""

from __future__ import annotations

import discord

from poker.assets import render_play_image, render_poker_hand_image
from poker.game import PokerGame, PokerStatus

from ..sessions import PokerSession
from ..text_utils import mention


def tournament_scoreboard_text(session: PokerSession) -> str:
    if not session.is_tournament:
        return ""
    if not session.tournament_scores:
        return "Skor tournament: belum ada ronde selesai."

    sorted_scores = sorted(
        session.tournament_scores.items(),
        key=lambda item: (item[1], -item[0]),
        reverse=True,
    )
    rows = [f"- {mention(user_id)}: **{score} point**" for user_id, score in sorted_scores]
    return "Skor tournament:\n" + "\n".join(rows)


def poker_lobby_text(session: PokerSession) -> str:
    players = "\n".join(f"- {mention(player.user_id)}" for player in session.game.players)
    if not players:
        players = "Belum ada pemain."
    mode_text = "Tournament" if session.is_tournament else "Regular"
    tournament_text = ""
    if session.is_tournament:
        tournament_text = f"Jumlah ronde tournament: **{session.tournament_total_rounds} game**\n"
    return (
        "**Remi Poker: Lobby**\n"
        "Mode ini memakai rules Big Two style: habiskan kartu, jangan menjadi loser.\n\n"
        f"Owner: {mention(session.owner_id)}\n"
        f"Mode: **{mode_text}**\n"
        f"{tournament_text}"
        f"Timer auto-pass: **{session.timer_seconds} detik**\n"
        f"Pemain ({len(session.game.players)}/{session.game.max_players}):\n{players}"
    )


def poker_state_text(session: PokerSession) -> str:
    state = session.game.public_state()
    hand_counts = "\n".join(
        f"- {mention(user_id)}: {count} kartu"
        + (" (winner)" if finished else "")
        + (" (bombed)" if bombed else "")
        for user_id, _name, count, finished, bombed in state["hand_counts"]
    )
    winners = ", ".join(mention(user_id) for user_id in state["winner_ids"]) or "Belum ada"
    loser = mention(state["loser_id"]) if state["loser_id"] else "Belum ada"
    action_text = "\n".join(f"- {message}" for message in session.log[:4]) or "- Belum ada aksi."
    vote_text = f"{session.end_vote_count}/{session.end_vote_required} setuju"
    current_player = mention(state["current_player_id"]) if state["current_player_id"] else "-"
    last_player = mention(state["last_play_player_id"]) if state["last_play_player_id"] else "-"
    last_play_suffix = " (ronde sebelumnya, table sudah clear)" if state["table_cleared"] else ""
    bomb_duel_text = ""
    if state["bomb_duel_active"]:
        victim = mention(state["bomb_duel_current_victim_id"]) if state["bomb_duel_current_victim_id"] else "-"
        bomber = mention(state["bomb_duel_current_bomber_id"]) if state["bomb_duel_current_bomber_id"] else "-"
        original = mention(state["bomb_duel_original_target_id"]) if state["bomb_duel_original_target_id"] else "-"
        bomb_duel_text = (
            "\n"
            f"Adu bomb aktif: bomb terakhir dari {bomber}. Target saat ini: {victim}. "
            f"Target awal: {original}.\n"
        )
    tournament_header = ""
    tournament_scores = ""
    if session.is_tournament:
        tournament_header = f"Mode: **Tournament ronde {session.tournament_current_round}/{session.tournament_total_rounds}**\n"
        tournament_scores = f"\n\n{tournament_scoreboard_text(session)}"

    return (
        "**Remi Poker: Game Berjalan**\n"
        f"{tournament_header}"
        f"Gilirannya: {current_player}\n"
        f"Timer auto-pass: **{session.timer_seconds} detik**\n"
        f"Pola ronde: **{state['round_pattern']}**\n"
        f"Kombinasi terakhir: **{state['last_play']}**{last_play_suffix}\n"
        f"Dimainkan oleh: {last_player}\n"
        f"{bomb_duel_text}"
        f"Pass ronde ini: {state['pass_count']}\n\n"
        f"Jumlah kartu pemain:\n{hand_counts}\n\n"
        f"Winner sementara: {winners}\n"
        f"Loser: {loser}\n"
        f"Vote akhiri game: **{vote_text}**\n\n"
        f"Aksi terakhir:\n{action_text}"
        f"{tournament_scores}"
    )


def poker_finished_text(session: PokerSession) -> str:
    state = session.game.public_state()
    winners = ", ".join(mention(user_id) for user_id in state["winner_ids"]) or "Tidak ada"
    loser = mention(state["loser_id"]) if state["loser_id"] else "Tidak ada"
    log_text = "\n".join(f"- {message}" for message in session.log[-3:]) or "- Game selesai."
    if session.is_tournament:
        if session.tournament_aborted:
            return (
                "**Remi Poker Tournament: Dihentikan**\n"
                f"Ronde terakhir: {session.tournament_current_round}/{session.tournament_total_rounds}\n\n"
                f"{tournament_scoreboard_text(session)}\n\n"
                f"Log akhir:\n{log_text}\n\n"
                "Tekan **Buat Lobby Baru** untuk main lagi."
            )
        if not session.tournament_finished:
            return (
                "**Remi Poker Tournament: Ronde Selesai**\n"
                f"Ronde selesai: {session.tournament_current_round}/{session.tournament_total_rounds}\n"
                f"Winner ronde: {winners}\n"
                f"Loser ronde: {loser}\n\n"
                f"{tournament_scoreboard_text(session)}\n\n"
                f"Log akhir:\n{log_text}\n\n"
                "Tekan **Mulai Ronde Berikutnya** untuk lanjut."
            )
        champion = next(iter(sorted(session.tournament_scores.items(), key=lambda item: item[1], reverse=True)), None)
        champion_text = mention(champion[0]) if champion else "Tidak ada"
        return (
            "**Remi Poker Tournament: Selesai**\n"
            f"Total ronde: {session.tournament_total_rounds}\n"
            f"Champion: {champion_text}\n\n"
            f"{tournament_scoreboard_text(session)}\n\n"
            f"Log akhir:\n{log_text}\n\n"
            "Tekan **Buat Lobby Baru** untuk main lagi."
        )
    return (
        "**Remi Poker: Selesai**\n"
        f"Winner: {winners}\n"
        f"Loser: {loser}\n\n"
        f"Log akhir:\n{log_text}\n\n"
        "Tekan **Buat Lobby Baru** untuk main lagi."
    )


def poker_table_text(session: PokerSession) -> str:
    if session.game.status == PokerStatus.WAITING:
        return poker_lobby_text(session)
    if session.game.status == PokerStatus.FINISHED:
        return poker_finished_text(session)
    return poker_state_text(session)


def poker_rules_embed() -> discord.Embed:
    embed = discord.Embed(
        title="Rules Remi Poker",
        description="Mode shedding/climbing kartu remi. Habiskan kartu dan jangan menjadi loser.",
        color=discord.Color.dark_gold(),
    )
    embed.add_field(
        name="Setup",
        value=(
            "- Pemain 2-4 orang.\n"
            "- Joker tidak dipakai.\n"
            "- Kartu 3 hanya menentukan first turn, lalu dibuang.\n"
            "- Rank playable terendah adalah 4, tertinggi adalah 2.\n"
            "- Timer auto-pass bisa dipilih di lobby: 45 atau 60 detik."
        ),
        inline=False,
    )
    embed.add_field(
        name="Mode Tournament",
        value=(
            "Regular bermain 1 game. Tournament bermain 3-20 ronde dengan akumulasi point: "
            "winner pertama +20, winner berikutnya +10, posisi tengah +0, loser terakhir -10. "
            "Jika ronde selesai karena bombcard, bomber final +40 dan korban bomb -40."
        ),
        inline=False,
    )
    embed.add_field(
        name="First Turn",
        value="Pemilik 3 diamonds + 3 clubs + 3 hearts mulai dulu. Jika tidak ada, pemilik 3 spades mulai.",
        inline=False,
    )
    embed.add_field(
        name="Kombinasi",
        value=(
            "Single, pair, three of a kind, straight, flush, full house, four of a kind, "
            "straight flush, royal flush."
        ),
        inline=False,
    )
    embed.add_field(
        name="Pola Ronde",
        value=(
            "Pola mengikuti pembuka ronde sampai table clear. Jika semua pemain lain pass, pemain terakhir "
            "yang memainkan kartu membuka ronde baru dengan pola bebas."
        ),
        inline=False,
    )
    embed.add_field(
        name="Bombcard",
        value=(
            "Four of a kind, straight flush, dan royal flush adalah bombcard. Bomb bisa menantang single 2 "
            "jika pemain yang mengeluarkan 2 masih punya sisa kartu. Bomb tidak bisa memotong pair/triple 2. "
            "Jika bomb dibalas bomb lebih besar, target kalah berpindah ke pemain bomb sebelumnya."
        ),
        inline=False,
    )
    return embed


def poker_table_visuals(session: PokerSession) -> tuple[discord.Embed | None, list[discord.File]]:
    if session.game.status == PokerStatus.WAITING:
        return poker_rules_embed(), []
    if session.game.status != PokerStatus.PLAYING or session.game.visible_last_play is None:
        return None, []

    visible_last_play = session.game.visible_last_play
    buffer, filename = render_play_image(list(visible_last_play.cards), "poker_last_play.jpg")
    file = discord.File(buffer, filename=filename)
    embed = discord.Embed(title="Kombinasi Terakhir", description=visible_last_play.label)
    embed.set_image(url=f"attachment://{filename}")
    return embed, [file]


def poker_hand_text(
    game: PokerGame,
    user_id: int,
    page: int = 0,
    page_size: int = 25,
    selected_numbers: set[int] | None = None,
) -> str:
    cards = game.hand_for(user_id)
    total_pages = max(1, (len(cards) + page_size - 1) // page_size)
    selected = ", ".join(str(number) for number in sorted(selected_numbers or set())) or "belum ada"
    return (
        "**Kartu Remi Tanganmu**\n"
        f"Halaman {page + 1}/{total_pages}. Pilih 1-5 kartu dari dropdown, lalu tekan **Mainkan Pilihan**.\n"
        f"Pilihan saat ini: {selected}"
    )


def poker_hand_visuals(
    game: PokerGame,
    user_id: int,
    page: int = 0,
    page_size: int = 25,
    selected_numbers: set[int] | None = None,
) -> tuple[discord.Embed, list[discord.File]]:
    buffer, filename = render_poker_hand_image(game.hand_for(user_id), page, selected_numbers, page_size)
    file = discord.File(buffer, filename=filename)
    embed = discord.Embed(title="Kartu Remi")
    embed.set_image(url=f"attachment://{filename}")
    return embed, [file]
