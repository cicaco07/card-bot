"""Versioned changelog data and formatting helpers."""

from __future__ import annotations


CHANGELOG_ENTRIES = [
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


def semver_tuple(version: str) -> tuple[int, int, int]:
    major, feature, patch = version.split(".")
    return int(major), int(feature), int(patch)


def latest_changelog_entry() -> dict[str, object]:
    return max(CHANGELOG_ENTRIES, key=lambda entry: semver_tuple(str(entry["version"])))


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
