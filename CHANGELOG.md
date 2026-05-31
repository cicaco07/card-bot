# Changelog

Format versi memakai `major.feature.patch`.

- `major`: update besar atau perubahan besar pada arah project.
- `feature`: penambahan fitur/mode baru.
- `patch`: update minor, balancing, atau bugfix.

## 1.1.0 - 2026-05-31

Mode Rummy regular dan tournament.

- Menambahkan mode Rummy dengan command `/rummy-start`, lobby interaktif, dan kartu tangan private.
- Menambahkan meld run dan set, dukungan dua joker, draw dari deck, serta pengambilan kartu buangan maksimal 7 kartu teratas.
- Menambahkan closed card dengan bonus angka +50, royal card +100, Ace +150, dan joker +250.
- Menambahkan perhitungan skor meld positif dan kartu sisa negatif saat ronde berakhir.
- Menambahkan mode Rummy Tournament dengan pilihan 3-20 ronde dan scoreboard akumulatif.
- Merapikan struktur internal CardBot menjadi modul engine, presentasi, UI, command, dan app yang terpisah.

## 1.0.1 - 2026-05-29

Poker Tournament dan penyempurnaan bombcard.

- Menambahkan mode Poker Tournament dengan pilihan 3-20 ronde.
- Menambahkan scoreboard tournament dengan point winner pertama +20, winner berikutnya +10, posisi tengah +0, dan loser -10.
- Menambahkan scoring khusus bombcard di tournament: bomber final +40, korban bomb -40, pemain lain 0.
- Menambahkan fase adu bomb untuk single kartu 2 yang masih menyisakan kartu di tangan.
- Menambahkan dropdown mode permainan di lobby poker: Regular atau Tournament.
- Mengurangi pesan ephemeral poker hand yang menumpuk setelah pemain menekan Mainkan Pilihan.
- Menambahkan dokumentasi deploy dan rules terbaru di README.

## 1.0.0 - 2026-05-28

Rilis awal CardBot.

- Menambahkan mode UNO reguler dengan tombol Discord, asset kartu, rules panel, tombol UNO, Challenge UNO, dan vote end game.
- Menambahkan mode Remi Poker regular dengan asset kartu remi, lobby, timer auto-pass, play/pass, auto-skip pair/triple, bombcard, dan vote end game.
- Menambahkan render kartu tangan private berbasis gambar untuk UNO dan Remi Poker.
- Menambahkan panel meja yang otomatis repost ke pesan terbaru agar pemain tidak perlu scroll ke atas.
