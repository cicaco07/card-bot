"""Versioned changelog data and formatting helpers."""

from __future__ import annotations

import re


CHANGELOG_ENTRIES = [
    {
        "version": "1.2.0",
        "title": "Multi-table tournament dan checkpoint PostgreSQL",
        "date": "2026-06-02",
        "changes": [
            "Menambahkan multi-table untuk Poker Tournament dan Rummy Tournament dengan kode meja unik.",
            "Menyimpan checkpoint PostgreSQL setelah ronde tournament selesai dan mendukung resume manual dari ronde berikutnya.",
            "Menambahkan command /tournament-list, /tournament-resume, dan /tournament-archive.",
            "Mendukung PostgreSQL lokal melalui Docker Compose serta connection string Supabase untuk deployment.",
            "Mempertahankan tombol Mulai Ronde Berikutnya pada panel akhir ronde setelah checkpoint berhasil tersimpan.",
        ],
    },
    {
        "version": "1.1.12",
        "title": "Skor normal dan rincian closed card Rummy",
        "date": "2026-06-02",
        "changes": [
            "Menghapus multiplier Go Rummy agar seluruh skor ronde dihitung normal.",
            "Menghitung penalti tanda flip berdasarkan kartu closed card, bukan kartu buangan yang dijadikan meld.",
            "Menampilkan rincian kartu untuk meld terbuka, meld tertutup, deadwood, dan penalti flip pada hasil akhir.",
        ],
    },
    {
        "version": "1.1.11",
        "title": "Rule Ace dan konfirmasi ambil buangan Rummy",
        "date": "2026-06-01",
        "changes": [
            "Melarang mengambil Ace dari buangan dan membuang Ace sebelum pemain membuka meld miliknya sendiri yang tidak memakai Ace.",
            "Menerapkan larangan juga saat Ace ikut terambil di atas target buangan atau dipakai sebagai closed card.",
            "Mengubah panel Ambil Buangan menjadi pilihan target dengan tombol Konfirmasi Ambil.",
        ],
    },
    {
        "version": "1.1.10",
        "title": "Closed card terakhir dan penalti flip Rummy",
        "date": "2026-06-01",
        "changes": [
            "Mengizinkan kartu terakhir dipakai sebagai closed card untuk langsung menutup ronde.",
            "Mengganti bonus closed card menjadi penalti flip bagi pemain yang kartu buangannya dijadikan target meld bukti.",
            "Menampilkan kartu penalti flip pada meja dan rincian pengurangannya pada skor akhir.",
        ],
    },
    {
        "version": "1.1.9",
        "title": "Emoji suit dan meld joker panjang Rummy",
        "date": "2026-06-01",
        "changes": [
            "Mengganti seluruh label kartu publik Rummy menjadi simbol suit ringkas seperti 6 ♦️.",
            "Mengizinkan meld bukti buangan berisi lebih dari 3 kartu selama tetap valid.",
            "Memastikan run seperti 4-5-Joker-7-8 diterima.",
        ],
    },
    {
        "version": "1.1.8",
        "title": "Koreksi meld bukti ambil tiga buangan Rummy",
        "date": "2026-06-01",
        "changes": [
            "Mengubah meld bukti saat mengambil 3 kartu buangan menjadi tepat 3 kartu bersama minimal 2 kartu tangan sebelumnya.",
            "Membebaskan dua kartu di atas target untuk disimpan atau dibuang kembali.",
        ],
    },
    {
        "version": "1.1.7",
        "title": "Publikasi changelog berurutan",
        "date": "2026-06-01",
        "changes": [
            "Mendeteksi versi changelog yang terlewati pada histori channel.",
            "Mengirim seluruh changelog publik yang belum diposting secara berurutan.",
            "Menyelaraskan versi aplikasi dengan changelog terbaru.",
        ],
    },
    {
        "version": "1.1.6",
        "title": "Detail skor dan log suit Rummy",
        "date": "2026-06-01",
        "changes": [
            "Menampilkan rincian meld terbuka, meld tangan, deadwood, bonus closed card, subtotal, dan multiplier Go Rummy pada hasil akhir ronde.",
            "Meringkas kartu pada log aktivitas dengan simbol suit, misalnya 8 ♥️.",
        ],
    },
    {
        "version": "1.1.5",
        "title": "Koreksi meld bukti ambil dua buangan Rummy",
        "date": "2026-06-01",
        "changes": [
            "Mengubah meld bukti saat mengambil 2 kartu buangan menjadi tepat 3 kartu bersama minimal 2 kartu tangan sebelumnya.",
            "Membebaskan kartu teratas yang ikut terambil untuk disimpan atau dibuang kembali.",
            "Mempertahankan meld bukti tepat 4 kartu saat mengambil 3 kartu buangan.",
        ],
    },
    {
        "version": "1.1.4",
        "title": "Informasi pembuang kartu Rummy",
        "date": "2026-06-01",
        "changes": [
            "Menampilkan pemain yang membuang setiap kartu pada panel 3 buangan teratas.",
            "Menampilkan pemain pembuang kartu pada pilihan draw dari buangan.",
        ],
    },
    {
        "version": "1.1.3",
        "title": "Penegasan meld bukti buangan Rummy",
        "date": "2026-06-01",
        "changes": [
            "Mewajibkan meld bukti tepat 3 kartu saat mengambil 1 kartu buangan.",
            "Mewajibkan meld bukti tepat 4 kartu saat mengambil 2-3 kartu buangan.",
            "Menampilkan jumlah kartu meld bukti yang diwajibkan pada meja dan panel kartu pemain.",
        ],
    },
    {
        "version": "1.1.2",
        "title": "Perbaikan alur giliran Rummy",
        "date": "2026-06-01",
        "changes": [
            "Mengubah meld bukti setelah mengambil buangan menjadi pilihan manual pemain sambil tetap mewajibkan kartu target dipakai sebelum discard.",
            "Melanjutkan ronde setelah pemain menghabiskan tangan melalui meld atau discard biasa selama deck belum habis dan belum ada closed card.",
            "Melewati pemain yang sudah tidak memiliki kartu saat menentukan giliran berikutnya.",
        ],
    },
    {
        "version": "1.1.1",
        "title": "Penyempurnaan rules Rummy",
        "date": "2026-06-01",
        "changes": [
            "Membatasi pengambilan kartu buangan menjadi maksimal 3 kartu teratas.",
            "Mewajibkan kartu target dari buangan langsung menjadi meld bukti publik yang terkunci.",
            "Menampilkan 3 kartu buangan teratas dan meld terbuka kepada seluruh pemain.",
            "Menambahkan tombol Turunkan Meld dan Gabungkan Meld serta larangan membuang Ace sebelum pemain membuka minimal satu meld.",
            "Menambah joker Rummy menjadi 4 kartu: 2 joker merah dan 2 joker hitam tanpa mengubah deck standar.",
            "Menambahkan rule Go Rummy yang menggandakan seluruh poin ronde.",
        ],
    },
    {
        "version": "1.1.0",
        "title": "Mode Rummy regular dan tournament",
        "date": "2026-05-31",
        "changes": [
            "Menambahkan mode Rummy dengan command /rummy-start, lobby interaktif, dan kartu tangan private.",
            "Menambahkan meld run dan set, dukungan dua joker, draw dari deck, serta pengambilan kartu buangan maksimal 7 kartu teratas.",
            "Menambahkan closed card dengan bonus angka +50, royal card +100, dan Ace +150.",
            "Menambahkan perhitungan skor meld positif dan kartu sisa negatif saat ronde berakhir.",
            "Menambahkan mode Rummy Tournament dengan pilihan 3-20 ronde dan scoreboard akumulatif.",
            "Merapikan struktur internal CardBot menjadi modul engine, presentasi, UI, command, dan app yang terpisah.",
        ],
    },
    {
        "version": "1.0.1",
        "title": "Poker Tournament dan penyempurnaan bombcard",
        "date": "2026-05-29",
        "changes": [
            "Menambahkan mode Poker Tournament dengan pilihan 3-20 ronde.",
            "Menambahkan scoreboard tournament dengan point winner pertama +20, winner berikutnya +10, posisi tengah +0, dan loser -10.",
            "Menambahkan scoring khusus bombcard di tournament: bomber final +40, korban bomb -40, pemain lain 0.",
            "Menambahkan fase adu bomb untuk single kartu 2 yang masih menyisakan kartu di tangan.",
            "Menambahkan dropdown mode permainan di lobby poker: Regular atau Tournament.",
            "Mengurangi pesan ephemeral poker hand yang menumpuk setelah pemain menekan Mainkan Pilihan.",
            "Menambahkan dokumentasi deploy dan rules terbaru di README.",
        ],
    },
    {
        "version": "1.0.0",
        "title": "Rilis awal CardBot",
        "date": "2026-05-28",
        "changes": [
            "Menambahkan mode UNO reguler dengan tombol Discord, asset kartu, rules panel, tombol UNO, Challenge UNO, dan vote end game.",
            "Menambahkan mode Remi Poker regular dengan asset kartu remi, lobby, timer auto-pass, play/pass, auto-skip pair/triple, bombcard, dan vote end game.",
            "Menambahkan render kartu tangan private berbasis gambar untuk UNO dan Remi Poker.",
            "Menambahkan panel meja yang otomatis repost ke pesan terbaru agar pemain tidak perlu scroll ke atas.",
        ],
    },
]

PUBLIC_CHANGELOG_VERSION_PATTERN = re.compile(r"^## UPDATE v(\d+\.\d+\.\d+)\s*$", re.MULTILINE)


def semver_tuple(version: str) -> tuple[int, int, int]:
    major, feature, patch = version.split(".")
    return int(major), int(feature), int(patch)


def latest_changelog_entry() -> dict[str, object]:
    return max(CHANGELOG_ENTRIES, key=lambda entry: semver_tuple(str(entry["version"])))


def public_changelog_version(content: str) -> str | None:
    match = PUBLIC_CHANGELOG_VERSION_PATTERN.search(content)
    return match.group(1) if match else None


def unpublished_public_changelog_entries(published_versions: set[str]) -> list[dict[str, object]]:
    ordered_entries = sorted(CHANGELOG_ENTRIES, key=lambda entry: semver_tuple(str(entry["version"])))
    if not published_versions:
        return [ordered_entries[-1]]
    first_published = min(published_versions, key=semver_tuple)
    return [
        entry
        for entry in ordered_entries
        if semver_tuple(str(entry["version"])) > semver_tuple(first_published)
        and str(entry["version"]) not in published_versions
    ]


def format_changelog_entry(entry: dict[str, object]) -> str:
    changes = "\n".join(f"- {change}" for change in entry["changes"])
    return (
        f"**CardBot v{entry['version']} - {entry['title']}**\n"
        f"Tanggal: {entry['date']}\n\n"
        f"{changes}\n\n"
        "Format versi: `major.feature.patch`, contoh `1.2.30` berarti major `1`, fitur baru `2`, "
        "dan minor/bugfix `30`."
    )


def format_public_changelog_entry(entry: dict[str, object], mention_everyone: bool) -> str:
    mention_text = "@everyone\n\n" if mention_everyone else ""
    changes = "\n".join(f"- {change}" for change in entry["changes"])
    return (
        f"{mention_text}"
        f"## UPDATE v{entry['version']}\n\n"
        f"- {entry['title']}\n"
        f"{changes}"
    )
