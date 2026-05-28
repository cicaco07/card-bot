# Plan Implementasi Mode Remi Poker

Dokumen ini adalah rencana implementasi sebelum eksekusi kode untuk mode kartu remi dengan command `/poker-start`.

## Ringkasan Mode

Mode ini bukan Texas Hold'em atau poker betting. Berdasarkan rules yang diberikan dan referensi pembanding, mode ini paling dekat dengan keluarga game **Big Two / Pusoy Dos / Da Lao Er**, yaitu game shedding/climbing: pemain berusaha menghabiskan kartu lebih dulu dengan memainkan kombinasi yang lebih tinggi dari kombinasi terakhir.

Command publik tetap:

```text
/poker-start
```

Nama pada rules panel bisa ditulis sebagai **Remi Poker** agar sesuai istilah user.

## Referensi Pembanding

- Big Two/Pusoy Dos memakai deck 52 kartu tanpa joker, 2 sebagai rank tertinggi, dan kombinasi single, pair, triple, straight, flush, full house, four of a kind, dan straight flush.
- Beberapa varian Big Two memakai suit order rendah ke tinggi `diamonds < clubs < hearts < spades`, cocok dengan rules user.
- Ranking kombinasi 5 kartu memakai struktur poker-hand, tetapi game flow adalah shedding/climbing.

## Asset

Asset tersedia di:

```text
assets/playing-cards/png
assets/playing-cards/svg-cards
```

Implementasi saat ini memakai SVG-first dari `assets/playing-cards/svg-cards`, lalu meraster SVG menjadi gambar grid menggunakan `CairoSVG` sebelum dikirim ke Discord. Jika native Cairo belum tersedia di Windows, renderer fallback ke PNG dari `assets/playing-cards/png` agar bot tidak crash.

Contoh filename:

```text
3_of_spades.svg
ace_of_hearts.svg
10_of_diamonds.svg
king_of_clubs.svg
black_joker.svg
red_joker.svg
```

Joker tidak dipakai.

## Scope MVP

Fitur MVP:

- Slash command `/poker-start`.
- Lobby dengan panel rules.
- Pemain 2-4 orang.
- Tombol `Ikut Main`, `Mulai Game`, `Lihat / Mainkan Kartu`, `Pass`, `Refresh Meja`, `Vote End Game`.
- Select timer auto-pass saat lobby: 30, 45, atau 60 detik.
- Deck 52 kartu tanpa joker.
- Kartu rank `3` hanya dipakai untuk menentukan first turn, lalu dibuang dari semua hand.
- Angka terendah yang bisa dimainkan adalah `4`.
- Kartu `2` adalah rank tertinggi/poker.
- Restart/redeal otomatis jika ada pemain memegang empat kartu `2`.
- Kartu tangan private berupa gambar grid dari asset remi.
- Pemilihan kartu lewat Discord select menu.
- Validasi kombinasi.
- Sistem turn, pass, dan clear table.
- Sistem winner/loser: bisa ada 1-3 pemenang.
- Panel utama repost ke bawah dan menghapus panel lama seperti mode UNO.

Tidak masuk MVP:

- Taruhan/chip.
- Scoring multi-round.
- Bot AI.
- Persist game setelah bot restart.

## Struktur File

Rekomendasi struktur:

```text
poker/
  __init__.py
  game.py
  assets.py

bot.py
```

Alasan: mode UNO sudah stabil, jadi mode poker/remi dibuat modular tanpa refactor besar.

## Model Data

### `PlayingCard`

Field:

- `rank`: `3,4,5,6,7,8,9,10,J,Q,K,A,2`
- `suit`: `diamonds, clubs, hearts, spades`

Derived:

- `rank_value`: untuk playable card dimulai dari `4`, lalu naik sampai `2`.
- `suit_value`: diamonds < clubs < hearts < spades.
- `label`: contoh `3 Spades`, `Ace Hearts`.
- `asset_filename`: contoh `3_of_spades.png`, `ace_of_hearts.png`.

### `PokerPlayer`

Field:

- `user_id`
- `name`
- `hand`
- `passed`
- `finished`
- `eliminated_by_bomb`

### `PokerGame`

Field:

- `status`: waiting, playing, finished
- `players`
- `turn_index`
- `last_play`
- `last_play_player_id`
- `round_pattern`
- `passed_user_ids`
- `winner_ids`
- `loser_id`
- `round_starter_user_id`
- `discarded_start_cards`
- `active_player_ids`

## Rank dan Suit

Rank playable rendah ke tinggi:

```text
4, 5, 6, 7, 8, 9, 10, J, Q, K, A, 2
```

Suit rendah ke tinggi:

```text
diamonds, clubs, hearts, spades
```

Kartu rank `3` tidak dipakai untuk pertarungan kombinasi. Kartu `3` hanya menentukan giliran pertama, lalu langsung dibuang/discard dari semua hand.

## Pembagian Kartu

Deck awal:

- 52 kartu standar.
- Joker tidak dipakai.

Jumlah pemain:

- Minimal 2.
- Maksimal 4.

Pembagian awal:

- 2 pemain: 26 kartu per pemain.
- 4 pemain: 13 kartu per pemain.
- 3 pemain: 17 kartu per pemain dan 1 kartu sisa diberikan ke pemain first turn.

Alur pembagian:

1. Shuffle deck.
2. Bagikan kartu sesuai jumlah pemain.
3. Untuk 3 pemain, simpan 1 kartu sisa sementara.
4. Tentukan first turn dari kartu `3`.
5. Jika 3 pemain, berikan kartu sisa ke pemain first turn.
6. Cek apakah ada pemain memegang empat kartu `2`.
7. Jika ada, restart/redeal.
8. Buang semua kartu rank `3` dari seluruh hand.
9. Sort hand semua pemain.

## Restart Otomatis Karena 4 Poker

Jika setelah pembagian ada pemain yang memiliki semua empat kartu `2`, game langsung restart/redeal.

Rencana implementasi:

- Saat `start()`, lakukan shuffle dan deal.
- Cek apakah ada hand yang memiliki `2 diamonds`, `2 clubs`, `2 hearts`, dan `2 spades`.
- Jika ada, ulangi shuffle dan deal.
- Batasi percobaan redeal, misalnya maksimal 20 kali sebagai guard teknis.
- Tampilkan log publik jika redeal terjadi: `Redeal karena ada pemain memegang 4 poker.`

## Penentuan Giliran Pertama

Prioritas:

1. Pemain yang memiliki `3 diamonds + 3 clubs + 3 hearts` menjadi first turn.
2. Jika tidak ada, pemain yang memiliki `3 spades` menjadi first turn.

Keputusan final user:

- Triple `3` non-spade benar-benar mengalahkan prioritas pemilik `3 spades`.
- Setelah first turn ditentukan, semua kartu rank `3` langsung dibuang.
- First player memulai round pertama dengan kombinasi bebas dari kartu `4` ke atas.

## Kombinasi Valid

### Single

- 1 kartu.
- Dibandingkan dengan rank lalu suit.

### Pair

- 2 kartu rank sama.
- Dibandingkan dengan rank pair, lalu suit tertinggi dalam pair.

### Three of a Kind

- 3 kartu rank sama.
- Dibandingkan dengan rank triple.

### Lima Kartu

Urutan kombinasi lima kartu dari kecil ke besar:

```text
straight
flush
full_house
four_of_a_kind
straight_flush
royal_flush
```

Catatan:

- `four_of_a_kind` adalah 4 kartu rank sama.
- `royal_flush` adalah `10-J-Q-K-A` satu suit.
- `four_of_a_kind`, `straight_flush`, dan `royal_flush` adalah bombcard.

## Aturan Straight

Keputusan final user:

- Straight hanya boleh sampai maksimal Ace.
- Straight tidak boleh memakai `2`.
- `A-2-3-4-5` tidak valid.
- `J-Q-K-A-2` tidak valid.
- Straight yang memakai `3` tidak valid karena semua kartu `3` dibuang saat start.

Straight valid:

```text
4-5-6-7-8
5-6-7-8-9
...
10-J-Q-K-A
```

## Pola Ronde

Kombinasi yang dikeluarkan selalu mengikuti pola kartu di awal ronde.

Contoh:

- Jika ronde dibuka dengan single, semua pemain hanya boleh melawan dengan single.
- Jika ronde dibuka dengan pair, semua pemain hanya boleh melawan dengan pair.
- Jika ronde dibuka dengan three of a kind, semua pemain hanya boleh melawan dengan three of a kind.
- Jika ronde dibuka dengan kombinasi 5 kartu, semua pemain hanya boleh melawan dengan kombinasi 5 kartu yang lebih tinggi.

Jika dalam satu putaran tidak ada pemain yang bisa memberi kartu lebih besar, table clear. Pemain yang terakhir memainkan kartu berhak membuka ronde baru dengan pola apa pun.

## Perbandingan Kombinasi

General:

- Kombinasi harus mengikuti pola ronde.
- Kombinasi baru harus lebih tinggi dari kombinasi terakhir.
- Setelah table clear, pemain pembuka boleh memainkan pola apa pun.

Jika tipe dan jumlah kartu sama:

- Single: rank, lalu suit.
- Pair: rank pair, lalu suit tertinggi.
- Three of a kind: rank triple.
- Straight: rank tertinggi, lalu suit kartu tertinggi.
- Flush: rank kartu tertinggi, lalu suit kartu tertinggi, lalu kicker turun.
- Full house: rank three of a kind.
- Four of a kind: rank four of a kind.
- Straight flush: rank tertinggi, lalu suit.
- Royal flush: suit.

Jika kombinasi sejenis memiliki rank tertinggi yang sama, tie-break berikutnya memakai suit tertinggi dengan urutan:

```text
diamonds < clubs < hearts < spades
```

Jika sama-sama 5 kartu tetapi tipe berbeda, ranking tipe menentukan.

## Bombcard

Bombcard:

- `four_of_a_kind`
- `straight_flush`
- `royal_flush`

User rule:

- Pemain yang kalah adalah pemain yang tersisa terakhir dengan kartu tidak habis atau terkena bombcard.
- Karena itu, bisa terdapat 1-3 pemenang.

Interpretasi MVP yang disarankan:

- Bombcard `four_of_a_kind` dimainkan dengan 4 kartu rank sama, tetapi tetap masuk ladder kombinasi besar dan bisa mengalahkan full house.
- Bombcard `straight_flush` dan `royal_flush` dimainkan dengan 5 kartu.
- Jika bombcard berhasil dimainkan untuk mengalahkan kombinasi pemain sebelumnya, pemain pemilik kombinasi sebelumnya menjadi loser.
- Game langsung selesai.
- Semua pemain lain yang belum kalah menjadi winner.

Open question sebelum implementasi bombcard final:

- Apakah bombcard boleh memotong pola single/pair/three seperti "bomb" di beberapa game climbing?
- Jika bombcard dimainkan sebagai pembuka ronde, apakah ada target yang terkena atau hanya menjadi kombinasi biasa?

Rekomendasi MVP: bombcard tidak memotong single/pair/three dulu, agar engine konsisten dan mudah diuji.

## Flow Game

1. `/poker-start` membuat lobby.
2. Pemain klik `Ikut Main`.
3. Setelah 2-4 pemain, klik `Mulai Game`.
4. Bot shuffle dan deal.
5. Bot menentukan first turn dari kartu `3`.
6. Jika perlu, bot redeal karena pemain memegang 4 poker.
7. Bot membuang semua kartu rank `3`.
8. Pemain first turn membuka ronde pertama dengan kombinasi bebas dari kartu `4` ke atas.
9. Pemain berikutnya harus memainkan kombinasi yang mengikuti pola ronde dan lebih tinggi, atau `Pass`.
10. Jika semua pemain lain pass, table clear dan pemain terakhir yang memainkan kartu membuka ronde baru.
11. Pemain yang menghabiskan kartu masuk `winner_ids` dan keluar dari active turn.
12. Game selesai jika hanya tersisa satu pemain aktif dengan kartu, atau jika ada pemain terkena bombcard.
13. Pemain terakhir yang masih memegang kartu menjadi loser. Pemain lain menjadi winner.

## UI Discord

### Panel Publik

Menampilkan:

- Nama mode: Remi Poker.
- Pemain dan jumlah kartu.
- Giliran saat ini.
- Pola ronde saat ini.
- Kombinasi terakhir.
- Pemain yang memainkan kombinasi terakhir.
- Jumlah pass pada ronde.
- Winner sementara.
- Loser jika game selesai.
- Aksi terakhir.

Panel akan repost ke bawah dan menghapus panel lama, sama seperti UNO terbaru.

### Panel Private Hand

Saat pemain klik `Lihat / Mainkan Kartu`:

- Bot mengirim gambar grid kartu tangan private.
- Setiap kartu diberi nomor.
- Pemain memilih 1-5 kartu dari dropdown multi-select.
- Tombol `Mainkan Pilihan`.
- Tombol pagination jika kartu banyak.

Catatan Discord:

- Select menu maksimal 25 option.
- Untuk 2 pemain, hand awal bisa 26 kartu sebelum kartu `3` dibuang.
- Setelah kartu `3` dibuang, hand biasanya turun, tetapi pagination tetap dibutuhkan.
- Jika kombinasi lintas halaman dibutuhkan, versi lanjutan perlu selection basket.

## Command Baru

Minimal:

```text
/poker-start
```

Fallback opsional:

```text
/poker-hand
/poker-status
/poker-play
```

Rekomendasi MVP:

- Implement `/poker-start`.
- Buat play utama lewat tombol.
- Tambahkan `/poker-status` dan `/poker-hand` hanya jika perlu fallback.

## Vote End Game

Gunakan pola dari UNO:

- Tombol `Vote End Game`.
- Hanya pemain yang ikut game bisa vote.
- Perlu lebih dari 50% pemain.
- Vote reset jika game berjalan lagi lewat play/pass.

## Rules Panel

Saat `/poker-start`, tampilkan panel rules:

- 2-4 pemain.
- Joker tidak dipakai.
- 2 adalah rank tertinggi/poker.
- Kartu 3 hanya menentukan first turn lalu dibuang.
- Suit order diamonds < clubs < hearts < spades.
- Objective: jangan menjadi pemain terakhir yang masih memegang kartu.
- Winner adalah pemain yang habis kartu sebelum loser ditentukan.
- Loser adalah pemain terakhir yang masih punya kartu atau pemain yang terkena bombcard.
- Kombinasi valid.
- Bombcard: four of a kind, straight flush, royal flush.
- Cara pass dan clear table.
- Penentuan giliran pertama.

## Test Plan

Unit/smoke test engine:

- Deck berisi 52 kartu tanpa joker.
- Asset path semua kartu non-joker ditemukan.
- Deal 2 pemain menghasilkan pembagian awal 26/26.
- Deal 4 pemain menghasilkan pembagian awal 13/13.
- Deal 3 pemain menghasilkan 18/17/17 setelah extra card ke first player.
- Start player berdasarkan triple `3 diamonds + 3 clubs + 3 hearts`.
- Start player fallback berdasarkan `3_of_spades`.
- Semua kartu rank `3` dibuang setelah first player ditentukan.
- Rank terendah playable adalah `4`.
- Jika pemain memegang empat kartu `2`, deal diulang/restart.
- Validasi single/pair/three of a kind.
- Validasi straight, flush, full house, four of a kind, straight flush, royal flush.
- Straight memakai `2` ditolak.
- `A-2-3-4-5` ditolak.
- Straight memakai kartu `3` ditolak.
- Kombinasi lebih rendah ditolak.
- Kombinasi beda pola ronde ditolak sampai table clear.
- Pass flow clear table setelah semua pemain lain pass.
- Player masuk winner saat hand kosong.
- Loser ditentukan saat tinggal satu pemain aktif dengan kartu.
- Bombcard membuat target menjadi loser dan game selesai sesuai interpretasi MVP.

Manual Discord test:

- `/poker-start` menampilkan lobby.
- 2, 3, 4 pemain bisa join dan start.
- Hand image private muncul.
- Multi-select kartu bisa memainkan kombinasi.
- Panel publik repost ke bawah.
- Timer auto-pass berjalan setelah game dimulai dan berpindah setiap giliran.
- Vote end game bekerja.
- Non-player tidak bisa vote/play/pass.

## Risiko dan Keputusan yang Masih Perlu Dikunci

1. Nama mode tetap `/poker-start`, walau rule lebih mirip Big Two style.
2. Detail bombcard masih perlu dikunci: apakah bisa memotong single/pair/three, dan siapa target jika bombcard dimainkan sebagai pembuka ronde.
3. UI multi-select untuk banyak kartu bisa terbatas oleh limit 25 option Discord.
4. Jika ingin pengalaman terbaik, perlu selection basket agar pemain bisa memilih kartu lintas halaman.

## Urutan Implementasi yang Disarankan

1. Buat `poker/game.py` untuk engine murni.
2. Buat `poker/assets.py` untuk render kartu remi.
3. Tambahkan session poker terpisah di `bot.py`.
4. Tambahkan `/poker-start`.
5. Tambahkan lobby dan rules panel.
6. Tambahkan hand private grid dan dropdown selection.
7. Tambahkan play/pass/clear-table flow.
8. Tambahkan bombcard sesuai interpretasi MVP.
9. Tambahkan vote end game.
10. Tambahkan unit/smoke tests.
11. Playtest 2-4 pemain di Discord.
