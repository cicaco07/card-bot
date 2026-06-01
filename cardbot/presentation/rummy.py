"""Rummy text, embed, and visual presentation helpers."""

from __future__ import annotations

import discord

from rummy.assets import render_discard_pile_image, render_rummy_hand_image
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
    visible_discards = "\n".join(
        f"- {index}. {label}{_discarded_by_text(user_id)}"
        for index, (label, user_id) in enumerate(zip(state["visible_discards"], state["visible_discard_user_ids"]), 1)
    ) or "- Belum ada"
    opened_melds = "\n".join(
        f"- {mention(user_id)}: {', '.join('[' + ', '.join(meld) + ']' for meld in melds)}"
        for user_id, _name, melds in state["opened_melds"]
        if melds
    ) or "- Belum ada meld yang diturunkan."
    actions = "\n".join(f"- {message}" for message in session.log[:4]) or "- Belum ada aksi."
    tournament = (
        f"Mode: **Tournament ronde {session.tournament_current_round}/{session.tournament_total_rounds}**\n"
        if session.is_tournament
        else ""
    )
    scores = f"\n\n{rummy_scoreboard_text(session)}" if session.is_tournament else ""
    required_meld = (
        f"minimal {state['required_discard_meld_size']} kartu memakai {state['required_discard_meld_card']}"
        if state["required_discard_meld_card"]
        else "Tidak ada"
    )
    top_discard_owner = state["visible_discard_user_ids"][0] if state["visible_discard_user_ids"] else None
    return (
        "**Rummy: Game Berjalan**\n"
        f"{tournament}Gilirannya: {mention(state['current_player_id'])}\n"
        f"Fase giliran: **{state['phase']}**\n"
        f"Kewajiban meld buangan: **{required_meld}**\n"
        f"Sisa deck: **{state['deck_count']} kartu**\n"
        f"Kartu buangan teratas: **{state['top_discard']}**{_discarded_by_text(top_discard_owner)}\n"
        f"Total buangan: {state['discard_count']}\n"
        f"3 buangan teratas:\n{visible_discards}\n\n"
        f"Meld terbuka dan terkunci:\n{opened_melds}\n\n"
        f"Jumlah kartu pemain:\n{hands}\n\n"
        f"Vote akhiri game: **{session.end_vote_count}/{session.end_vote_required} setuju**\n\n"
        f"Aksi terakhir:\n{actions}{scores}"
    )


def rummy_finished_text(session: RummySession) -> str:
    state = session.game.public_state()
    scores = "\n".join(
        _finished_score_text(user_id, score, state["score_breakdowns"].get(user_id))
        for user_id, score in sorted(state["scores"].items(), key=lambda item: (item[1], -item[0]), reverse=True)
    ) or "- Tidak ada skor."
    log = "\n".join(f"- {message}" for message in session.log[-3:]) or "- Game selesai."
    if session.is_tournament and not session.tournament_aborted and not session.tournament_finished:
        footer = "Tekan **Mulai Ronde Berikutnya** untuk lanjut."
    else:
        footer = "Tekan **Buat Lobby Baru** untuk main lagi."
    tournament = f"\n\n{rummy_scoreboard_text(session)}" if session.is_tournament else ""
    return f"**Rummy: Selesai**\n\nSkor ronde:\n{scores}{tournament}\n\nLog akhir:\n{log}\n\n{footer}"


def _finished_score_text(user_id: int, score: int, details: dict[str, int] | None) -> str:
    summary = f"- {mention(user_id)}: **{score:+d} point**"
    if details is None:
        return summary
    calculation = (
        f"meld terbuka {details['opened_meld_points']:+d}, "
        f"meld tangan {details['hand_meld_points']:+d}, "
        f"deadwood {-details['deadwood_points']:+d}, "
        f"bonus closed {details['closed_bonus']:+d} = subtotal {details['subtotal']:+d}"
    )
    if details["go_rummy_multiplier"] > 1:
        calculation += f", Go Rummy x{details['go_rummy_multiplier']} = total {details['total']:+d}"
    return f"{summary}\n  {calculation}"


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
    embed.add_field(name="Setup", value="2-4 pemain. Setiap pemain mendapat 7 kartu. Deck memakai 52 kartu standar dan 4 joker: 2 merah dan 2 hitam.", inline=False)
    embed.add_field(name="Giliran", value="Ambil satu kartu dari deck atau buangan, lalu wajib buang satu kartu non-joker.", inline=False)
    embed.add_field(name="Meld", value="Run: minimal 3 kartu berurutan dengan suit sama. Set: minimal 3 kartu rank sama. Joker boleh menggantikan kartu apa pun. Meld yang sudah dibuka bisa ditambah lewat Gabungkan Meld jika hasilnya tetap valid.", inline=False)
    embed.add_field(name="Ambil Buangan", value="Boleh mengambil maksimal 3 kartu buangan teratas. Ambil 1-3 wajib meld bukti minimal 3 kartu: kartu target dan minimal 2 kartu tangan sebelumnya. Kartu di atas target bebas disimpan atau dibuang lagi.", inline=False)
    embed.add_field(name="Discard Ace", value="Ace belum boleh dibuang sebelum pemain tersebut menurunkan minimal satu meld.", inline=False)
    embed.add_field(name="Skor", value="Kartu angka +5, J/Q/K +10, Ace +15. Meld bernilai positif dan kartu tersisa bernilai negatif. Go Rummy menggandakan seluruh poin ronde.", inline=False)
    return embed


def rummy_table_visuals(session: RummySession) -> tuple[discord.Embed | None, list[discord.File]]:
    if session.game.status == RummyStatus.WAITING:
        return rummy_rules_embed(), []
    if not session.game.discard_pile:
        return None, []
    buffer, filename = render_discard_pile_image(session.game.visible_discards())
    file = discord.File(buffer, filename=filename)
    labels = "\n".join(
        f"{index}. {card.activity_label}{_discarded_by_text(user_id)}"
        for index, (card, user_id) in enumerate(session.game.visible_discard_details(), 1)
    )
    embed = discord.Embed(title="3 Buangan Teratas", description=labels)
    embed.set_image(url=f"attachment://{filename}")
    return embed, [file]


def _discarded_by_text(user_id: int | None) -> str:
    return f" - dibuang oleh {mention(user_id)}" if user_id is not None else ""


def rummy_hand_text(game: RummyGame, user_id: int, page: int = 0, page_size: int = 25, selected_numbers: set[int] | None = None) -> str:
    total_pages = max(1, (len(game.hand_for(user_id)) + page_size - 1) // page_size)
    selected = ", ".join(str(number) for number in sorted(selected_numbers or set())) or "belum ada"
    required_meld = (
        f"\nWajib turunkan meld bukti **minimal {game.required_discard_meld_size} kartu** yang memakai "
        f"**{game.required_discard_meld_card.activity_label}** sebelum membuang kartu."
        if game.required_discard_meld_card
        else ""
    )
    return f"**Kartu Rummy Tanganmu**\nHalaman {page + 1}/{total_pages}. Pilih 1 kartu untuk dibuang atau minimal 3 kartu untuk diturunkan sebagai meld.{required_meld}\nPilihan saat ini: {selected}"


def rummy_hand_visuals(game: RummyGame, user_id: int, page: int = 0, page_size: int = 25, selected_numbers: set[int] | None = None) -> tuple[discord.Embed, list[discord.File]]:
    buffer, filename = render_rummy_hand_image(game.hand_for(user_id), page, selected_numbers, page_size)
    file = discord.File(buffer, filename=filename)
    embed = discord.Embed(title="Kartu Rummy")
    embed.set_image(url=f"attachment://{filename}")
    return embed, [file]
