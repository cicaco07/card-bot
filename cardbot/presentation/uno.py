"""UNO text, embed, and visual presentation helpers."""

from __future__ import annotations

import discord

from uno.card_assets import render_card_image, render_hand_image
from uno.game import COLOR_LABELS, GameStatus, UnoGame

from ..sessions import UnoSession
from ..text_utils import mention


def lobby_text(session: UnoSession) -> str:
    players = "\n".join(f"- {mention(player.user_id)}" for player in session.game.players)
    if not players:
        players = "Belum ada pemain."
    return (
        "**UNO Table: Lobby**\n"
        "Tekan tombol di bawah untuk ikut bermain. Setelah minimal 2 pemain masuk, tekan **Mulai Game**.\n\n"
        f"Owner: {mention(session.owner_id)}\n"
        f"Pemain ({len(session.game.players)}/{session.game.max_players}):\n{players}"
    )


def public_state_text(session: UnoSession) -> str:
    game = session.game
    state = game.public_state()
    hand_counts = "\n".join(
        f"- {mention(user_id)}: {count} kartu"
        for user_id, _name, count in state["hand_counts"]
    )
    uno_pending = "\n".join(
        f"- {mention(user_id)} wajib tekan **UNO!**. Pemain lain bisa menekan **Challenge UNO**."
        for user_id, _name in state["uno_pending"]
    )
    if not uno_pending:
        uno_pending = "- Tidak ada."
    action_text = "\n".join(f"- {message}" for message in session.log[:2]) or "- Belum ada aksi."
    vote_text = f"{session.end_vote_count}/{session.end_vote_required} setuju"
    return (
        "**UNO Table: Game Berjalan**\n"
        "Kartu aktif ada pada gambar di bawah.\n"
        f"Warna aktif: **{state['current_color']}**\n"
        f"Gilirannya: {mention(state['current_player_id'])}\n"
        f"Arah: {state['direction']}\n"
        f"Sisa deck: {state['deck_count']} kartu\n\n"
        f"Jumlah kartu pemain:\n{hand_counts}\n\n"
        f"Status UNO:\n{uno_pending}\n\n"
        f"Vote akhiri game: **{vote_text}**\n\n"
        f"Aksi terakhir:\n{action_text}"
    )


def finished_text(session: UnoSession) -> str:
    log_text = "\n".join(f"- {message}" for message in session.log[-8:]) or "- Game selesai."
    return f"**UNO Table: Selesai**\n\nLog akhir:\n{log_text}\n\nTekan **Buat Lobby Baru** untuk main lagi."


def table_text(session: UnoSession) -> str:
    if session.game.status == GameStatus.WAITING:
        return lobby_text(session)
    if session.game.status == GameStatus.FINISHED:
        return finished_text(session)
    return public_state_text(session)


def hand_text(game: UnoGame, user_id: int, page: int = 0, page_size: int = 25) -> str:
    cards = game.hand_for(user_id)
    total_pages = max(1, (len(cards) + page_size - 1) // page_size)
    return (
        "**Kartu tanganmu**\n"
        f"Halaman {page + 1}/{total_pages}. Lihat gambar kartu di bawah, lalu pilih nomor kartu dari dropdown.\n"
        "Border hijau berarti kartu tersebut bisa dimainkan."
    )


def rules_embed() -> discord.Embed:
    embed = discord.Embed(
        title="Rules UNO Reguler",
        description="Baca dulu sebelum ikut bermain. Versi ini dibuat sederhana agar ritme game tetap cepat.",
        color=discord.Color.gold(),
    )
    embed.add_field(
        name="Tujuan",
        value="Habiskan semua kartu di tanganmu. Pemain yang kartunya habis pertama menang.",
        inline=False,
    )
    embed.add_field(
        name="Yang Harus Dilakukan",
        value=(
            "- Mainkan kartu yang cocok dengan warna aktif atau angka/aksi kartu aktif.\n"
            "- Gunakan kartu Change Color untuk mengganti warna.\n"
            "- Ambil kartu jika tidak ada kartu yang bisa dimainkan.\n"
            "- Pass hanya jika tidak punya kartu yang bisa dimainkan.\n"
            "- Tekan tombol UNO! saat kartumu tersisa tepat 1.\n"
            "- Challenge pemain lain yang lupa menekan UNO sebelum mereka sempat menekannya."
        ),
        inline=False,
    )
    embed.add_field(
        name="Yang Tidak Boleh Dilakukan",
        value=(
            "- Jangan melihat atau meminta screenshot kartu pemain lain.\n"
            "- Jangan spam tombol draw/pass/refresh.\n"
            "- Jangan sengaja memperlambat giliran terlalu lama.\n"
            "- Jangan memulai lobby baru saat game di channel masih berjalan."
        ),
        inline=False,
    )
    embed.add_field(
        name="Kartu Special",
        value=(
            "**Stop/Skip** melewati pemain berikutnya.\n"
            "**Reverse** membalik arah permainan. Pada 2 pemain, Reverse bertindak seperti Stop.\n"
            "**+2** membuat pemain berikutnya mengambil 2 kartu dan dilewati.\n"
            "**Change Color** memilih warna baru.\n"
            "**Change Color +4** memilih warna baru, pemain berikutnya mengambil 4 kartu dan dilewati."
        ),
        inline=False,
    )
    embed.add_field(
        name="Rule Tombol UNO!",
        value=(
            "Jika setelah memainkan kartu kamu tersisa 1 kartu, kamu wajib menekan tombol **UNO!**. "
            "Kamu tidak bisa memainkan kartu terakhir sebelum tombol UNO! ditekan. Jika pemain lain menekan "
            "**Challenge UNO** lebih dulu, kamu mengambil 2 kartu penalti."
        ),
        inline=False,
    )
    embed.add_field(
        name="Batasan Versi Ini",
        value=(
            "Belum ada stacking +2/+4 dan belum ada challenge +4. Challenge UNO hanya berlaku untuk pemain "
            "yang sedang tersisa 1 kartu dan belum menekan UNO."
        ),
        inline=False,
    )
    embed.set_footer(text="Klik Ikut Main jika setuju mengikuti rules meja ini.")
    return embed


def table_visuals(session: UnoSession) -> tuple[discord.Embed | None, list[discord.File]]:
    if session.game.status == GameStatus.WAITING:
        return rules_embed(), []

    if session.game.status != GameStatus.PLAYING:
        return None, []

    buffer, filename = render_card_image(session.game.top_card, "current_card.jpg")
    file = discord.File(buffer, filename=filename)
    embed = discord.Embed(
        title="Kartu Aktif",
        description=f"Warna aktif: **{COLOR_LABELS[session.game.current_color]}**",
    )
    embed.set_image(url=f"attachment://{filename}")
    return embed, [file]


def hand_visuals(
    game: UnoGame,
    user_id: int,
    page: int = 0,
    page_size: int = 25,
) -> tuple[discord.Embed, list[discord.File]]:
    cards = game.hand_for(user_id)
    playable = set(game.playable_cards_for(user_id))
    buffer, filename = render_hand_image(cards, playable, page, page_size, "your_hand.jpg")
    file = discord.File(buffer, filename=filename)
    embed = discord.Embed(title="Kartu Tangan")
    embed.set_image(url=f"attachment://{filename}")
    return embed, [file]
