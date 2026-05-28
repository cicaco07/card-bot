# Discord Card Bot: UNO Reguler

Contoh implementasi custom bot Discord untuk memainkan UNO sederhana bersama anggota server.

Saat ini bot hanya mendukung mode UNO reguler:

- 4 warna: merah, kuning, hijau, biru
- kartu angka 0-9
- kartu special: Stop, Reverse, +2, Change Color, Change Color +4
- game berjalan per channel dan disimpan di memory
- meja game memakai tombol dan dropdown Discord
- kartu tangan dikirim private lewat ephemeral message

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

- **Ikut Main** untuk masuk lobby.
- **Mulai Game** untuk membagikan kartu dan memulai permainan.
- **Lihat / Mainkan Kartu** untuk membuka kartu tanganmu secara private.
- Di panel private kartu tangan, pilih kartu dari dropdown untuk memainkannya.
- Jika memilih kartu **Change Color**, bot akan menampilkan tombol pilihan warna.
- **Ambil Kartu** untuk draw 1 kartu.
- **Pass** untuk melewati giliran jika tidak ada kartu yang bisa dimainkan.
- **Refresh Meja** untuk memperbarui tampilan meja.
- **Akhiri Game** untuk menyelesaikan game.

Isi kartu pemain tidak muncul di channel publik. Setiap pemain melihat kartunya sendiri lewat ephemeral message, yaitu pesan Discord yang hanya terlihat oleh pemain tersebut.

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
- Tidak ada tombol "UNO" ketika sisa 1 kartu.
- Reverse pada 2 pemain dianggap seperti Stop.
- State game masih in-memory, jadi game hilang jika bot restart.
- Tombol pada pesan lama tidak bisa dipakai lagi setelah bot restart karena state game juga hilang.

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
