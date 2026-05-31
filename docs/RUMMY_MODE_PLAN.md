# Plan Implementasi Mode Rummy

Dokumen ini menjadi referensi eksekusi mode kartu Rummy dengan command `/rummy-start`.

Status implementasi: **selesai untuk scope MVP**.

## Ringkasan Mode

Mode Rummy memakai 52 kartu standar dan 2 joker. Pemain mengambil satu kartu lalu membuang satu kartu pada setiap giliran. Tujuannya adalah membentuk meld, memperoleh skor tertinggi, dan menutup ronde dengan **closed card** jika seluruh kartu selain satu kartu penutup sudah menjadi meld.

Command publik:

```text
/rummy-start
/rummy-hand
/rummy-status
```

Tournament:

```text
/rummy-start mode:tournament rounds:3
```

## Keputusan Rule MVP

Brief awal memiliki beberapa bagian yang dapat ditafsirkan berbeda. Implementasi mengunci keputusan berikut:

- Pemain: 2-4 orang.
- Hand awal: 7 kartu per pemain.
- Deck: 52 kartu standar dan 2 joker.
- Setiap giliran dimulai pada fase draw lalu wajib diakhiri dengan discard.
- Kartu buangan dapat dipilih dari maksimal 7 kartu teratas.
- Kartu buangan hanya dapat diambil jika langsung membentuk meld bersama minimal 2 kartu yang sudah ada di tangan.
- Joker boleh menggantikan kartu dalam meld.
- Joker tidak boleh dibuang sebagai discard biasa.
- Joker boleh dipakai sebagai closed card.
- Closed card valid jika seluruh kartu yang tersisa di tangan dapat dipartisi menjadi meld.
- Bonus closed card hanya diberikan jika draw terakhir berasal dari deck, sesuai brief awal.
- Run memakai rank `2, 3, ..., 10, J, Q, K, A`; Ace tinggi dan tidak wrap.

## Meld Valid

### Run

Minimal 3 kartu berurutan dengan suit yang sama.

Contoh:

```text
2 hearts, 3 hearts, 4 hearts
J clubs, Q clubs, K clubs
```

### Set

Minimal 3 kartu dengan rank sama.

Contoh:

```text
8 diamonds, 8 clubs, 8 spades
K diamonds, K hearts, K spades
```

### Joker

Joker menggantikan kartu yang hilang.

Contoh:

```text
2 hearts, Joker, 4 hearts
```

## Scoring

Nilai kartu:

```text
2-10  = 5
J/Q/K = 10
Ace   = 15
Joker = 20
```

Saat ronde selesai:

- Kartu yang masuk meld bernilai positif.
- Kartu tersisa atau deadwood bernilai negatif.
- Engine mencari kombinasi meld terbaik secara otomatis.

Bonus closed card setelah draw dari deck:

```text
angka biasa = +50
J/Q/K       = +100
Ace         = +150
Joker       = +250
```

## Regular dan Tournament

Regular memainkan satu ronde.

Tournament memainkan 3-20 ronde:

- Score tiap ronde diakumulasikan.
- Setelah ronde selesai muncul tombol **Mulai Ronde Berikutnya**.
- Scoreboard diurutkan dari point tertinggi.

## Asset

Mode ini memakai asset remi yang sama dengan Poker:

```text
assets/playing-cards/svg-cards
assets/playing-cards/png
```

Renderer memakai SVG terlebih dahulu dan fallback ke PNG jika native Cairo tidak tersedia. Joker memakai:

```text
black_joker.svg
red_joker.svg
```

## Struktur File

```text
rummy/
  __init__.py
  cards.py
  game.py
  assets.py

cardbot/
  presentation/rummy.py
  ui/rummy.py
```

Integrasi tambahan berada di:

```text
cardbot/state.py
cardbot/sessions.py
cardbot/constants.py
cardbot/commands.py
cardbot/changelog.py
```

## UI Discord

Panel lobby:

- **Ikut Main**
- **Mulai Game**
- **Tutup Lobby**
- dropdown Regular atau Tournament
- dropdown jumlah ronde untuk Tournament

Panel game:

- **Lihat / Buang Kartu**
- **Ambil Deck**
- **Ambil Buangan**
- **Refresh Meja**
- **Vote End Game**

Panel private:

- Gambar hand bernomor.
- Dropdown kartu yang akan dibuang.
- Tombol **Buang Kartu**.
- Tombol **Closed Card**.
- Dropdown maksimal 7 kartu buangan teratas.

## Test Coverage

Coverage otomatis:

- Deck berisi 54 kartu termasuk 2 joker.
- Deal awal 7 kartu.
- Validasi run, set, joker, dan partisi meld.
- Validasi ambil discard yang langsung membentuk meld.
- Joker ditolak sebagai discard biasa tetapi diterima sebagai closed card.
- Scoring meld, deadwood, dan bonus closed card.
- Akumulasi skor tournament.
- Renderer hand Rummy mendukung joker.
- Import contract modul Rummy.
- Snapshot slash command Rummy.

## Checklist Eksekusi

- [x] Buat engine dan model kartu Rummy.
- [x] Tambahkan renderer asset termasuk joker.
- [x] Tambahkan registry dan session regular/tournament.
- [x] Tambahkan presentasi dan rules embed.
- [x] Tambahkan UI lobby, draw, discard, closed card, dan scoreboard.
- [x] Tambahkan slash command dan fallback.
- [x] Tambahkan test engine, render, import, dan command snapshot.
- [x] Update changelog ke versi `1.1.0`.
