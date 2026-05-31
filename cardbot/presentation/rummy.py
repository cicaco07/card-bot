"""Rummy text, embed, and visual presentation helpers."""

from __future__ import annotations

import discord

from rummy.assets import render_discard_image, render_rummy_hand_image
from rummy.game import RummyGame, RummyStatus

from ..sessions import RummySession
from ..text_utils import mention


def rummy_scoreboard_text(session: RummySession) -> str:
    if not session.is_tournament:
        return ""
    if not session.tournament_scores:
        return "Skor tournament: belum ada ronde selesai."
    rows = [
        f"- {mention(user_id)}: **{score} point**"
        for user_id, score in sorted(session.tournament_scores.items(), key=lambda item: (item[1], -item[0]), reverse=True)
    ]
    return "Skor tournament:\n" + "\n".join(rows)


def rummy_lobby_text(session: RummySession) -> str:
    players = "\n".join(f"- {mention(player.user_id)}" for player in session.game.players) or "Belum ada pemain."
    mode = "Tournament" if session.is_tournament else "Regular"
    rounds = f"Jumlah ronde tournament: **{session.tournament_total_rounds} game**\n" if session.is_tournament else ""
    return (
        "**Rummy: Lobby**\n"
        "Buat meld run atau set, lalu raih skor tertinggi.\n\n"
        f"Owner: {mention(session.owner_id)}\nMode: **{mode}**\n{rounds}"
        f"Pemain ({len(session.game.players)}/{session.game.max_players}):\n{players}"
    )


def rummy_state_text(session: RummySession) -> str:
    state = session.game.public_state()
    hands = "\n".join(f"- {mention(user_id)}: {count} kartu" for user_id, _name, count in state["hand_counts"])
    actions = "\n".join(f"- {message}" for message in session.log[:4]) or "- Belum ada aksi."
    tournament = (
        f"Mode: **Tournament ronde {session.tournament_current_round}/{session.tournament_total_rounds}**\n"
        if session.is_tournament
        else ""
    )
    scores = f"\n\n{rummy_scoreboard_text(session)}" if session.is_tournament else ""
    return (
        "**Rummy: Game Berjalan**\n"
        f"{tournament}Gilirannya: {mention(state['current_player_id'])}\n"
        f"Fase giliran: **{state['phase']}**\n"
        f"Sisa deck: **{state['deck_count']} kartu**\n"
        f"Kartu buangan teratas: **{state['top_discard']}**\n"
        f"Total buangan: {state['discard_count']}\n\n"
        f"Jumlah kartu pemain:\n{hands}\n\n"
        f"Vote akhiri game: **{session.end_vote_count}/{session.end_vote_required} setuju**\n\n"
        f"Aksi terakhir:\n{actions}{scores}"
    )


def rummy_finished_text(session: RummySession) -> str:
    state = session.game.public_state()
    scores = "\n".join(
        f"- {mention(user_id)}: **{score:+d} point**"
        for user_id, score in sorted(state["scores"].items(), key=lambda item: (item[1], -item[0]), reverse=True)
    ) or "- Tidak ada skor."
    log = "\n".join(f"- {message}" for message in session.log[-3:]) or "- Game selesai."
    if session.is_tournament and not session.tournament_aborted and not session.tournament_finished:
        footer = "Tekan **Mulai Ronde Berikutnya** untuk lanjut."
    else:
        footer = "Tekan **Buat Lobby Baru** untuk main lagi."
    tournament = f"\n\n{rummy_scoreboard_text(session)}" if session.is_tournament else ""
    return f"**Rummy: Selesai**\n\nSkor ronde:\n{scores}{tournament}\n\nLog akhir:\n{log}\n\n{footer}"


def rummy_table_text(session: RummySession) -> str:
    if session.game.status == RummyStatus.WAITING:
        return rummy_lobby_text(session)
    if session.game.status == RummyStatus.FINISHED:
        return rummy_finished_text(session)
    return rummy_state_text(session)


def rummy_rules_embed() -> discord.Embed:
    embed = discord.Embed(
        title="Rules Rummy",
        description="Buat kombinasi meld dan tutup ronde dengan closed card.",
        color=discord.Color.dark_teal(),
    )
    embed.add_field(name="Setup", value="2-4 pemain. Setiap pemain mendapat 7 kartu. Deck memakai 52 kartu standar dan 2 joker.", inline=False)
    embed.add_field(name="Giliran", value="Ambil satu kartu dari deck atau buangan, lalu wajib buang satu kartu non-joker.", inline=False)
    embed.add_field(name="Meld", value="Run: minimal 3 kartu berurutan dengan suit sama. Set: minimal 3 kartu rank sama. Joker boleh menggantikan kartu apa pun.", inline=False)
    embed.add_field(name="Ambil Buangan", value="Boleh memilih salah satu dari maksimal 7 kartu buangan teratas jika kartu itu langsung melengkapi meld dari minimal 2 kartu tangan.", inline=False)
    embed.add_field(name="Skor", value="Kartu angka +5, J/Q/K +10, Ace +15. Meld bernilai positif dan kartu tersisa bernilai negatif. Closed card memberi bonus +50/+100/+150.", inline=False)
    return embed


def rummy_table_visuals(session: RummySession) -> tuple[discord.Embed | None, list[discord.File]]:
    if session.game.status == RummyStatus.WAITING:
        return rummy_rules_embed(), []
    if not session.game.discard_pile:
        return None, []
    buffer, filename = render_discard_image(session.game.discard_pile[-1])
    file = discord.File(buffer, filename=filename)
    embed = discord.Embed(title="Buangan Teratas", description=session.game.discard_pile[-1].label)
    embed.set_image(url=f"attachment://{filename}")
    return embed, [file]


def rummy_hand_text(game: RummyGame, user_id: int, page: int = 0, page_size: int = 25, selected_number: int | None = None) -> str:
    total_pages = max(1, (len(game.hand_for(user_id)) + page_size - 1) // page_size)
    selected = str(selected_number) if selected_number is not None else "belum ada"
    return f"**Kartu Rummy Tanganmu**\nHalaman {page + 1}/{total_pages}. Pilih kartu untuk dibuang.\nPilihan saat ini: {selected}"


def rummy_hand_visuals(game: RummyGame, user_id: int, page: int = 0, page_size: int = 25, selected_number: int | None = None) -> tuple[discord.Embed, list[discord.File]]:
    buffer, filename = render_rummy_hand_image(game.hand_for(user_id), page, selected_number, page_size)
    file = discord.File(buffer, filename=filename)
    embed = discord.Embed(title="Kartu Rummy")
    embed.set_image(url=f"attachment://{filename}")
    return embed, [file]
