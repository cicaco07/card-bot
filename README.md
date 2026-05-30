# Discord Card Bot: UNO Reguler dan Remi Poker

Contoh implementasi custom bot Discord untuk memainkan game kartu sederhana bersama anggota server.

Versi saat ini: `1.0.1`

Command changelog:

```text
/changelog
/publish-changelog
```

Command ini menampilkan changelog terbaru jika user tersebut belum melihat versi terbaru selama bot berjalan. Jika sudah pernah dilihat, bot hanya memberi info bahwa belum ada changelog baru.

`/publish-changelog` mengirim changelog terbaru ke channel sebagai pesan publik dari bot. Command ini hanya bisa dipakai user dengan permission **Manage Server**. Pilih `mention_everyone: True` jika ingin tampilan highlight seperti pesan yang melakukan ping `@everyone`.

Mode yang tersedia:

- UNO reguler dengan tombol dan asset kartu.
- Remi Poker / Big Two style dengan kartu remi.

## Mode UNO Reguler

Bot mendukung:

- 4 warna: merah, kuning, hijau, biru
- kartu angka 0-9
- kartu special: Stop, Reverse, +2, Change Color, Change Color +4
- game berjalan per channel dan disimpan di memory
- meja game memakai tombol dan dropdown Discord
- gambar kartu diambil dari `assets/uno_regular`
- kartu tangan dikirim sebagai gambar private lewat ephemeral message

## Membuat Bot di Discord Developer Portal

1. Buka <https://discord.com/developers/applications>.
2. Klik **New Application**.
3. Isi nama aplikasi, misalnya `Card Bot`, lalu klik **Create**.
4. Buka menu **Bot**.
5. Klik **Reset Token** atau **View Token**, lalu salin token bot.
6. Simpan token itu ke file `.env`. Jangan commit, screenshot, atau membagikan token ini.

Bot ini memakai slash command dan tidak membaca isi chat biasa, jadi untuk versi saat ini kamu tidak perlu menyalakan privileged intent seperti **Message Content Intent**.

## Mengundang Bot ke Server

Kamu harus punya permission **Manage Server** di server Discord tujuan.

Cara paling umum:

1. Di Discord Developer Portal, buka aplikasi bot kamu.
2. Buka menu **OAuth2** lalu **URL Generator**.
3. Pada bagian **Scopes**, centang:
   - `bot`
   - `applications.commands`
4. Pada bagian **Bot Permissions**, centang permission minimal:
   - `View Channels`
   - `Send Messages`
   - `Read Message History`
   - `Add Reactions`
   - `Mention Everyone` jika `/publish-changelog mention_everyone: True` akan dipakai
5. Salin URL yang muncul di bagian bawah.
6. Buka URL tersebut di browser.
7. Pilih server tujuan.
8. Klik **Authorize** dan selesaikan captcha jika diminta.

Untuk development cepat, kamu bisa mencentang **Administrator**, tapi jangan jadikan ini default untuk bot publik. Permission minimal lebih aman.

## Menjalankan Project

1. Install dependency:

```bash
pip install -r requirements.txt
```

2. Salin `.env.example` menjadi `.env`, lalu isi token:

```env
DISCORD_TOKEN=token_bot_kamu
DISCORD_GUILD_ID=id_server_opsional
```

`DISCORD_GUILD_ID` opsional, tapi direkomendasikan saat development karena slash command biasanya muncul lebih cepat di server tersebut.

Untuk mengambil `DISCORD_GUILD_ID`, aktifkan **Developer Mode** di Discord, klik kanan server kamu, lalu pilih **Copy Server ID**.

3. Jalankan bot:

```bash
python bot.py
```

Jika terminal menampilkan `Bot logged in as ...`, bot sudah online. Coba command `/uno_start` di channel server.

## Cara Main Dengan Tombol

Slash command hanya dipakai sekali untuk membuat meja:

```text
/uno_start
```

Setelah itu bot akan mengirim panel **UNO Table** di channel. Semua aksi utama bisa dilakukan lewat tombol:

- Panel awal menampilkan **Rules UNO Reguler** yang harus dibaca sebelum ikut bermain.
- **Ikut Main** untuk masuk lobby.
- **Mulai Game** untuk membagikan kartu dan memulai permainan.
- **Lihat / Mainkan Kartu** untuk membuka kartu tanganmu secara private.
- Di panel private kartu tangan, bot menampilkan gambar grid kartu dari asset asli.
- Nomor kecil di gambar kartu dipakai untuk memilih kartu dari dropdown.
- Border hijau pada gambar kartu berarti kartu tersebut bisa dimainkan.
- Jika memilih kartu **Change Color**, bot akan menampilkan tombol pilihan warna.
- **Ambil Kartu** untuk draw 1 kartu.
- **Pass** untuk melewati giliran jika tidak ada kartu yang bisa dimainkan.
- **UNO!** wajib ditekan saat kartumu tersisa tepat 1 kartu.
- **Challenge UNO** untuk menghukum pemain lain yang tersisa 1 kartu tetapi belum menekan **UNO!**.
- **Refresh Meja** untuk memperbarui tampilan meja.
- **Vote End Game** untuk mengusulkan game selesai lebih awal.

Isi kartu pemain tidak muncul di channel publik. Setiap pemain melihat kartunya sendiri lewat ephemeral message, yaitu pesan Discord yang hanya terlihat oleh pemain tersebut.

Jika setelah memainkan kartu kamu tersisa 1 kartu, meja akan menampilkan status bahwa kamu wajib menekan **UNO!**. Kamu tidak bisa memainkan kartu terakhir sebelum tombol **UNO!** ditekan. Jika pemain lain menekan **Challenge UNO** lebih dulu, kamu mengambil 2 kartu penalti.

Panel meja hanya menampilkan **Aksi terakhir** agar tidak penuh log lama. Aksi tombol seperti draw, pass, UNO, dan challenge langsung memperbarui panel meja tanpa mengirim popup sukses tambahan yang harus di-dismiss.

Setiap kali state meja berubah, bot mengirim ulang panel utama sebagai pesan terbaru lalu menghapus panel lama. Ini membuat pemain tidak perlu scroll ke atas untuk melihat kartu aktif, giliran saat ini, dan jumlah kartu pemain.

Game hanya selesai lebih awal jika vote **lebih dari 50% pemain** menyetujui. Contoh: 2 pemain butuh 2 vote, 3 pemain butuh 2 vote, 4 pemain butuh 3 vote. Vote akan di-reset jika game berjalan lagi lewat aksi normal seperti draw, pass, play card, UNO, atau challenge.

## Asset Kartu

Bot membaca gambar kartu dari folder:

```text
assets/uno_regular
```

Format nama file yang dipakai:

- `Red_0.jpg` sampai `Red_9.jpg`
- `Red_Skip.jpg`
- `Red_Reverse.jpg`
- `Red_Draw_2.jpg`
- format yang sama untuk `Yellow`, `Green`, dan `Blue`
- `Wild.jpg`
- `Wild_Draw_4.jpg`

Renderer otomatis toleran terhadap beda huruf besar/kecil pada filename, misalnya `RED_Reverse.jpg`.

Gambar current card di meja ditampilkan sebagai attachment embed Discord. Gambar kartu tangan dibuat sebagai grid sementara dari asset asli, lalu dikirim private ke pemain.

## Command Fallback

Command berikut masih tersedia sebagai cadangan jika tombol Discord bermasalah:

- `/uno_start` membuat panel meja UNO interaktif.
- `/uno_hand` melihat kartu tangan sendiri secara private.
- `/uno_status` refresh status meja.
- `/uno_play card_number color` memainkan kartu berdasarkan nomor dari `/uno_hand`.

## Catatan Rule

Implementasi ini sengaja dibuat sederhana supaya enak dikembangkan:

- Tidak ada challenge untuk Change Color +4.
- Tidak ada stacking +2/+4.
- Tombol **UNO!** wajib ditekan saat pemain tersisa 1 kartu.
- **Challenge UNO** memberi penalti +2 kepada pemain yang tersisa 1 kartu tetapi belum menekan **UNO!**.
- Reverse pada 2 pemain dianggap seperti Stop.
- State game masih in-memory, jadi game hilang jika bot restart.
- Tombol pada pesan lama tidak bisa dipakai lagi setelah bot restart karena state game juga hilang.
- Tombol **Tutup Lobby** hanya bisa dipakai oleh pemain yang ikut lobby.
- Tombol **Vote End Game** hanya mencatat suara pemain yang ikut game.

Saat `/uno_start` dijalankan, bot menampilkan panel rules di lobby. Rules ini otomatis diganti menjadi gambar kartu aktif saat game dimulai.

## Arah Pengembangan

Struktur saat ini memisahkan engine game dari Discord command:

- `uno/game.py` berisi aturan UNO reguler.
- `bot.py` berisi slash command Discord.

Untuk mode lain seperti UNO Flip atau UNO Wild, kamu bisa membuat engine baru, misalnya:

- `uno/modes/regular.py`
- `uno/modes/flip.py`
- `uno/modes/wild.py`

Lalu bot memilih engine berdasarkan parameter command, misalnya `/uno_start mode:regular`.

Fitur berikutnya yang paling masuk akal:

- persist game ke SQLite/Redis agar tidak hilang saat restart
- lobby owner/admin permission untuk `/uno_begin` dan `/uno_end`
- timer auto-pass jika pemain terlalu lama
- mode plugin agar game lain selain UNO bisa dipasang ke bot yang sama

## Mode Remi Poker

Slash command:

```text
/poker-start
```

Untuk tournament:

```text
/poker-start mode:tournament rounds:3
```

`rounds` bisa diisi dari 3 sampai 20. Jika tidak memilih mode, bot memakai mode regular seperti sebelumnya.

Mode ini memakai kartu remi SVG dari:

```text
assets/playing-cards/svg-cards
```

Renderer akan mencoba meraster SVG menjadi gambar grid sebelum dikirim ke Discord. Jika native Cairo belum tersedia di Windows, bot otomatis fallback ke PNG dari `assets/playing-cards/png` agar game tetap berjalan.

Rules utama:

- Pemain 2-4 orang.
- Mode regular bermain 1 game.
- Mode tournament bermain 3-20 game dengan skor akumulasi.
- Skor tournament per ronde: winner pertama +20, winner berikutnya +10, posisi tengah +0, loser terakhir -10.
- Joker tidak dipakai.
- Kartu `3` hanya menentukan first turn lalu dibuang.
- Saat game dimulai, bot menampilkan kartu `3` yang dimiliki setiap pemain sebelum kartu tersebut dibuang.
- Urutan awal ditentukan dari kartu `3`: prioritas khusus `3 diamonds + 3 clubs + 3 hearts`, lalu `3 spades`, `3 hearts`, `3 clubs`, dan `3 diamonds`.
- Rank playable dari kecil ke besar: `4, 5, 6, 7, 8, 9, 10, J, Q, K, A, 2`.
- Suit dari kecil ke besar: diamonds, clubs, hearts, spades.
- Straight tidak boleh memakai `2`; `A-2-3-4-5` tidak valid.
- Pola ronde mengikuti pembuka ronde sampai table clear.
- Untuk pair dan three of a kind, bot otomatis skip pemain yang tidak punya kombinasi lebih tinggi.
- Kombinasi 5 kartu dari kecil ke besar: straight, flush, full house, four of a kind, straight flush, royal flush.
- Four of a kind adalah 4 kartu rank sama dan bisa mengalahkan full house.
- Four of a kind, straight flush, dan royal flush dianggap bombcard pada ladder kombinasi besar.
- Bombcard bisa dipakai untuk menantang single kartu `2` jika pemain yang mengeluarkan `2` masih punya sisa kartu.
- Bombcard tidak bisa memotong pair `2` atau three of a kind `2`.
- Saat adu bomb, pemain lain bisa membalas dengan bombcard yang lebih besar. Jika bomb yang lebih besar keluar, target kalah berpindah ke pemain yang mengeluarkan bomb sebelumnya.
- Jika ronde tournament selesai karena bombcard, bomber mendapat +40 point, korban bomb mendapat -40 point, dan pemain lain mendapat 0 point untuk ronde tersebut.
- Game bisa memiliki 1-3 winner; loser adalah pemain terakhir yang masih punya kartu atau pemain yang terkena bombcard.
- Jika ada pemain mendapat empat kartu `2`, game otomatis redeal.

Panel Remi Poker memakai tombol:

- **Ikut Main** untuk masuk lobby.
- Dropdown **Pilih timer auto-pass** untuk memilih 45 atau 60 detik sebelum game mulai.
- **Mulai Game** untuk deal dan mulai.
- **Lihat / Mainkan Kartu** untuk melihat kartu private dan memilih 1-5 kartu.
- **Pass** untuk melewati giliran.
- **Refresh Meja** untuk mengirim ulang panel terbaru.
- **Vote End Game** untuk mengakhiri game jika mayoritas setuju.
- Pada mode tournament, setelah satu ronde selesai akan muncul tombol **Mulai Ronde Berikutnya** sampai jumlah ronde terpenuhi.

Jika pemain tidak beraksi sampai timer habis, bot akan menjalankan auto-pass. Jika pemain sedang membuka ronde baru dan belum ada kartu di meja, giliran pembuka akan dilewati ke pemain aktif berikutnya agar game tidak macet.

Setelah pemain menekan **Mainkan Pilihan**, panel private kartu tidak lagi dirender ulang otomatis. Ini sengaja dibuat agar Discord tidak menumpuk pesan ephemeral yang harus sering di-dismiss. Untuk melihat sisa kartu, tekan lagi tombol **Lihat / Mainkan Kartu** di panel meja.

Dokumen plan lengkap ada di:

```text
docs/POKER_MODE_PLAN.md
```
