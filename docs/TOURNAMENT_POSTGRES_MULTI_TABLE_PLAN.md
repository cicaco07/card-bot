# Plan PostgreSQL / Supabase Multi-Table Tournament Poker dan Rummy

## 1. Tujuan

Mengubah bot agar satu server Discord dapat menjalankan lebih dari satu meja permainan dengan mode yang sama, sekaligus menyimpan progres tournament ke PostgreSQL. Database dapat dijalankan secara lokal atau memakai PostgreSQL terkelola dari Supabase.

Implementasi awal dibatasi untuk:

- Poker mode tournament.
- Rummy mode tournament.

Mode reguler Poker, mode reguler Rummy, dan UNO tetap memakai behavior saat ini. Pembatasan ini menjaga perubahan tetap terukur dan tidak membebani database dengan penyimpanan state setiap aksi kartu.

## 2. Keputusan Utama

### 2.1 Resume hanya dari akhir ronde

Progres tournament hanya disimpan setelah satu ronde selesai. Resume tidak tersedia ketika ronde masih berjalan.

Metadata lobby dan daftar pemain boleh dicatat sejak meja dibuat untuk kebutuhan multi-table. Namun, record tersebut belum dianggap sebagai checkpoint yang dapat di-resume sampai `completed_rounds >= 1`.

Checkpoint yang disimpan berisi:

- Identitas meja.
- Daftar pemain dan urutan kursi.
- Konfigurasi tournament.
- Jumlah ronde yang sudah selesai.
- Total skor masing-masing pemain.
- Detail hasil tiap ronde yang sudah selesai.
- Status tournament: menunggu ronde berikutnya atau sudah selesai.

Checkpoint tidak menyimpan:

- Susunan deck aktif.
- Kartu tangan saat ronde berjalan.
- Giliran pemain aktif.
- Kartu buangan aktif.
- Meld aktif dalam ronde berjalan.
- Timer aktif Poker.
- Tombol atau panel Discord sementara.

### 2.2 Konsekuensi jika bot restart di tengah ronde

Jika bot restart ketika ronde ke-N sedang berlangsung:

- Ronde ke-N yang belum selesai tidak dipulihkan.
- Tournament kembali ke checkpoint setelah ronde ke-(N-1).
- Pemain dapat memulai ulang ronde ke-N dengan deck baru.
- Jika restart terjadi pada ronde pertama sebelum ada checkpoint, tournament belum dapat di-resume. Pemain perlu membuat meja tournament baru.

Behavior ini perlu ditampilkan dengan jelas pada pesan resume agar pemain mengetahui bahwa hanya ronde yang sudah selesai yang tersimpan.

### 2.3 Multi-table memakai identitas meja

State permainan tidak lagi hanya dicari berdasarkan `channel_id`. Setiap meja tournament memiliki:

- `table_id`: UUID internal.
- `table_code`: kode pendek yang mudah dipakai dalam command.
- `table_name`: nama opsional agar mudah dibedakan.
- `guild_id`: server Discord pemilik meja.
- `channel_id`: channel tempat panel terakhir ditampilkan.

Dengan identitas ini, beberapa meja Poker tournament atau Rummy tournament dapat berjalan di server dan channel yang sama tanpa saling menimpa.

## 3. Scope Fitur

### Termasuk dalam implementasi

- PostgreSQL sebagai penyimpanan checkpoint tournament.
- Supabase sebagai opsi PostgreSQL terkelola untuk production.
- Multi-table Poker tournament dan Rummy tournament.
- Resume tournament dari checkpoint akhir ronde.
- Daftar meja tournament aktif milik server.
- Riwayat hasil ronde dan skor kumulatif.
- Statistik dasar pemain tournament.
- Migration database menggunakan Alembic.
- Docker Compose PostgreSQL untuk pengembangan lokal.
- Penanganan database tidak tersedia dengan pesan error yang jelas.

### Tidak termasuk dalam implementasi awal

- Resume di tengah ronde.
- Penyimpanan setiap aksi kartu ke database.
- Migrasi tournament in-memory lama yang sedang berjalan.
- Multi-table atau persistence untuk mode reguler.
- Persistence UNO.
- Sinkronisasi lintas beberapa instance bot secara bersamaan.

### Target deployment database

Implementasi mendukung dua target tanpa mengubah game engine:

- PostgreSQL lokal melalui Docker Compose untuk development dan test.
- Supabase Database untuk staging atau production.

Supabase dipakai sebagai PostgreSQL terkelola melalui connection string. Bot tidak memerlukan Supabase SDK, Supabase Auth, atau Data API untuk scope awal ini.

## 4. Arsitektur Target

### 4.1 Komponen baru

Tambahkan layer persistence terpisah dari game engine:

```text
Discord Commands / Views
          |
Tournament Service
          |
Repository Layer
          |
PostgreSQL
```

Game engine Poker dan Rummy tetap mengelola ronde aktif di memory. Database hanya menerima checkpoint setelah engine menyatakan ronde selesai.

### 4.2 Runtime registry

Registry tournament aktif di memory perlu memakai `table_id` sebagai key utama:

```text
tournament_tables_by_id[table_id]
```

Index tambahan dapat dipakai untuk pencarian cepat:

```text
table_ids_by_guild[guild_id]
table_id_by_guild_and_code[(guild_id, table_code)]
```

Mode lama yang belum memakai persistence dapat tetap menggunakan registry yang ada agar blast radius perubahan tidak terlalu besar.

### 4.3 Transaksi checkpoint akhir ronde

Setelah ronde selesai, simpan data dalam satu transaksi database:

1. Insert hasil ronde.
2. Update skor kumulatif pemain.
3. Update jumlah ronde selesai.
4. Ubah status meja menjadi `between_rounds` atau `finished`.
5. Update statistik pemain jika tournament selesai.

Gunakan unique constraint pada pasangan `(table_id, round_number)` agar callback Discord yang terpanggil dua kali tidak menghitung skor dua kali.

## 5. Desain Database

Semua tabel milik bot ditempatkan pada schema PostgreSQL `cardbot`, bukan schema `public`. Ini menjaga tabel internal tournament terpisah dari Data API Supabase.

### 5.1 Tabel `cardbot.tournament_tables`

| Kolom | Tipe | Keterangan |
| --- | --- | --- |
| `id` | `uuid` | Primary key internal |
| `table_code` | `varchar(12)` | Kode pendek meja |
| `table_name` | `varchar(100)` nullable | Nama opsional |
| `guild_id` | `bigint` | Discord server ID |
| `channel_id` | `bigint` | Channel panel terakhir |
| `owner_user_id` | `bigint` | Pembuat meja |
| `game_type` | enum | `poker` atau `rummy` |
| `status` | enum | `between_rounds`, `finished`, atau `archived` |
| `total_rounds` | `integer nullable` | Target jumlah ronde; `NULL` berarti tournament endless |
| `completed_rounds` | `integer` | Jumlah ronde yang sudah tersimpan |
| `settings_json` | `jsonb` | Konfigurasi mode yang stabil antar ronde |
| `version` | `integer` | Optimistic locking |
| `created_at` | `timestamptz` | Waktu dibuat |
| `updated_at` | `timestamptz` | Waktu update |

Constraint penting:

- Unique `(guild_id, table_code)`.
- `completed_rounds >= 0`.
- `completed_rounds <= total_rounds` jika `total_rounds` tidak `NULL`.

Tidak perlu status `in_round` di database. Ketika ronde aktif berjalan di memory, database tetap menyimpan checkpoint `between_rounds` terakhir.

### 5.2 Tabel `cardbot.tournament_players`

| Kolom | Tipe | Keterangan |
| --- | --- | --- |
| `id` | `uuid` | Primary key |
| `table_id` | `uuid` | Foreign key ke meja |
| `user_id` | `bigint` | Discord user ID |
| `display_name` | `varchar(100)` | Snapshot nama pemain |
| `seat_order` | `integer` | Urutan kursi |
| `cumulative_score` | `integer` | Total skor sampai checkpoint terakhir |
| `created_at` | `timestamptz` | Waktu join |
| `updated_at` | `timestamptz` | Waktu update |

Constraint penting:

- Unique `(table_id, user_id)`.
- Unique `(table_id, seat_order)`.

### 5.3 Tabel `cardbot.tournament_rounds`

| Kolom | Tipe | Keterangan |
| --- | --- | --- |
| `id` | `uuid` | Primary key |
| `table_id` | `uuid` | Foreign key ke meja |
| `round_number` | `integer` | Nomor ronde |
| `result_json` | `jsonb` | Detail skor, ranking, dan metadata hasil ronde |
| `completed_at` | `timestamptz` | Waktu ronde selesai |

Constraint penting:

- Unique `(table_id, round_number)`.

`result_json` harus cukup detail untuk menampilkan ulang log skor akhir ronde tanpa menghitung ulang state kartu yang sudah tidak tersedia.

### 5.4 Tabel `cardbot.tournament_player_stats`

| Kolom | Tipe | Keterangan |
| --- | --- | --- |
| `id` | `uuid` | Primary key |
| `guild_id` | `bigint` | Discord server ID |
| `user_id` | `bigint` | Discord user ID |
| `game_type` | enum | `poker` atau `rummy` |
| `tournaments_played` | `integer` | Total tournament selesai |
| `tournaments_won` | `integer` | Total kemenangan |
| `total_score` | `integer` | Akumulasi skor tournament |
| `updated_at` | `timestamptz` | Waktu update |

Constraint penting:

- Unique `(guild_id, user_id, game_type)`.

Statistik ini hanya di-update ketika tournament selesai agar proses checkpoint antar ronde tetap ringan.

### 5.5 Koneksi Supabase

Supabase menyediakan beberapa jenis connection string. Pilihan untuk bot:

| Kebutuhan | Pilihan utama | Fallback |
| --- | --- | --- |
| Runtime bot pada VM atau container persisten | Direct connection | Supavisor session pooler jika host hanya mendukung IPv4 |
| Alembic migration dan maintenance | Direct connection | Supavisor session pooler |
| Serverless atau koneksi sangat singkat | Tidak dipakai pada scope awal | Supavisor transaction pooler |

Gunakan dua environment variable agar kredensial runtime dan migration dapat dipisahkan:

```text
DATABASE_URL=<runtime connection string>
DATABASE_MIGRATION_URL=<migration connection string>
```

Catatan implementasi:

- Ambil connection string dari tombol `Connect` pada dashboard Supabase.
- Gunakan `postgresql+asyncpg://` untuk koneksi runtime SQLAlchemy async.
- Aktifkan SSL untuk koneksi production.
- Simpan connection string hanya sebagai secret environment variable.
- Gunakan role database khusus runtime dengan hak akses minimum ke schema `cardbot` jika environment production sudah siap.
- Gunakan role migration yang boleh membuat schema, tabel, index, enum, dan constraint.
- Jangan memakai transaction pooler sebagai default runtime. Mode tersebut tidak mendukung prepared statement dan membutuhkan konfigurasi driver tambahan.

Contoh pemisahan koneksi:

```text
# Runtime persisten: direct connection atau session pooler
DATABASE_URL=postgresql+asyncpg://<runtime-user>:<password>@<host>:5432/postgres

# Migration: direct connection atau session pooler
DATABASE_MIGRATION_URL=postgresql+asyncpg://<migration-user>:<password>@<host>:5432/postgres
```

Password pada URL harus di-encode dengan benar jika mengandung karakter khusus. Nilai asli tidak boleh ditulis ke repository.

## 6. Alur Pengguna

### 6.1 Membuat tournament

Command Poker dan Rummy yang sudah ada tetap dipakai. Ketika mode yang dipilih adalah `tournament`:

1. Buat `table_id` dan `table_code`.
2. Simpan metadata meja ke database.
3. Tampilkan kode meja pada lobby Discord.
4. Simpan pemain yang join sebelum ronde pertama dimulai.
5. Mulai ronde pertama di memory.

Mode reguler tidak membuat record database.

### 6.2 Menyelesaikan ronde

Ketika engine menutup ronde:

1. Hitung skor ronde menggunakan logic mode yang sudah ada.
2. Simpan checkpoint dalam satu transaksi.
3. Tampilkan hasil ronde dan skor kumulatif.
4. Tampilkan tombol `Mulai Ronde Berikutnya` jika masih ada ronde.
5. Tampilkan hasil tournament akhir jika semua ronde selesai.

### 6.3 Resume setelah restart

Tambahkan command:

```text
/tournament-list
/tournament-resume table_code:<kode>
```

Alur `/tournament-resume`:

1. Cari meja berdasarkan `guild_id` dan `table_code`.
2. Tolak meja dari server lain.
3. Tolak meja berstatus `finished` atau `archived`.
4. Tolak resume jika `completed_rounds = 0` karena belum ada checkpoint akhir ronde.
5. Muat daftar pemain, skor kumulatif, dan ronde terakhir.
6. Tampilkan panel checkpoint.
7. Beri informasi bahwa ronde aktif yang belum selesai tidak tersimpan.
8. Sediakan tombol `Mulai Ronde Berikutnya`.

Resume tidak langsung membagikan kartu. Pemain tetap memiliki momen konfirmasi sebelum ronde baru dimulai.

### 6.4 Mengarsipkan meja

Tambahkan command:

```text
/tournament-archive table_code:<kode>
```

Command ini mengubah status meja menjadi `archived`. Data riwayat tetap disimpan untuk audit dan statistik.

## 7. Aturan Akses

- Semua pencarian meja harus selalu memakai `guild_id` dan `table_code`.
- Pemain yang terdaftar di meja atau user dengan permission `Manage Server` dapat menjalankan `/tournament-resume`.
- Pemilik meja atau user dengan permission `Manage Server` dapat menjalankan `/tournament-archive`.
- Tombol panel harus membawa `table_id` pada custom ID atau context internal.
- Callback wajib memverifikasi bahwa user adalah pemain meja yang benar.

## 8. Penanganan Database Tidak Tersedia

Jika PostgreSQL tidak tersedia:

- Pembuatan Poker tournament dan Rummy tournament baru ditolak dengan pesan yang jelas.
- Resume dan list checkpoint ditolak dengan pesan yang jelas.
- Mode reguler dan UNO tetap dapat berjalan memakai behavior lama.
- Ronde tournament aktif yang sedang berjalan di memory tidak dihentikan paksa.
- Jika penyimpanan checkpoint akhir ronde gagal, hasil ronde jangan dianggap tersimpan. Tampilkan pesan error dan sediakan retry checkpoint sebelum ronde berikutnya dapat dimulai.

Ini mencegah tournament lanjut ke ronde berikutnya tanpa checkpoint yang valid.

## 9. Tahapan Implementasi

### Tahap 1: Fondasi PostgreSQL

- Tambahkan dependency `SQLAlchemy`, `asyncpg`, dan `Alembic`.
- Tambahkan `DATABASE_URL` ke konfigurasi environment.
- Tambahkan `DATABASE_MIGRATION_URL` untuk menjalankan Alembic.
- Tambahkan placeholder kedua variable tersebut ke `.env.example` tanpa kredensial asli.
- Tambahkan Docker Compose PostgreSQL untuk lokal.
- Dokumentasikan connection string Supabase untuk staging atau production.
- Buat migration awal untuk schema `cardbot` dan empat tabel tournament.
- Tambahkan repository async dan health check database.

### Tahap 2: Registry multi-table

- Pisahkan registry tournament dari registry mode reguler.
- Ubah lookup tournament agar memakai `table_id`.
- Tambahkan generator `table_code`.
- Pastikan view dan callback membawa identitas meja yang tepat.

### Tahap 3: Checkpoint akhir ronde

- Tambahkan service untuk transaksi penyimpanan hasil ronde.
- Hubungkan lifecycle akhir ronde Poker tournament.
- Hubungkan lifecycle akhir ronde Rummy tournament.
- Blokir tombol ronde berikutnya sebelum checkpoint berhasil.
- Pastikan finalize ronde idempotent.

### Tahap 4: Resume dan pengelolaan meja

- Tambahkan `/tournament-list`.
- Tambahkan `/tournament-resume`.
- Tambahkan `/tournament-archive`.
- Tampilkan skor kumulatif, ronde terakhir tersimpan, dan peringatan batas resume.

### Tahap 5: Statistik dan hardening

- Update statistik ketika tournament selesai.
- Tambahkan logging error persistence.
- Tambahkan retry checkpoint.
- Tambahkan cleanup registry memory setelah meja selesai atau diarsipkan.
- Update changelog sebagai release fitur baru.

## 10. Test Plan

### Database dan migration

- `alembic upgrade head` berhasil pada database kosong.
- `alembic upgrade head` berhasil memakai `DATABASE_MIGRATION_URL` Supabase.
- Repository dapat melakukan health check melalui `DATABASE_URL` Supabase.
- Constraint meja, pemain, dan ronde bekerja.
- Insert hasil ronde ganda tidak menambah skor dua kali.

### Multi-table

- Dua Poker tournament dapat berjalan bersamaan di server yang sama.
- Dua Rummy tournament dapat berjalan bersamaan di channel yang sama.
- Callback meja A tidak dapat mengubah state meja B.
- `table_code` dari server lain tidak dapat dipakai.

### Checkpoint dan resume

- Akhir ronde menyimpan skor pemain dan detail ronde.
- Restart setelah akhir ronde dapat me-resume skor dan pemain dengan benar.
- Resume memulai ronde berikutnya dengan deck baru.
- Restart di tengah ronde membuang ronde yang belum selesai dan kembali ke checkpoint terakhir.
- Restart pada ronde pertama sebelum checkpoint tidak menawarkan resume.
- Meja selesai tidak dapat di-resume sebagai meja aktif.

### Kompatibilitas

- Poker reguler tetap berjalan seperti sebelumnya.
- Rummy reguler tetap berjalan seperti sebelumnya.
- UNO tetap berjalan seperti sebelumnya.
- Tournament baru ditolak dengan pesan jelas ketika database mati.
- Mode lama tetap dapat dipakai ketika database mati.

## 11. Deployment

### Deployment lokal

Urutan deployment lokal yang disarankan:

1. Jalankan PostgreSQL melalui Docker Compose.
2. Tambahkan `DATABASE_URL` ke environment bot.
3. Tambahkan `DATABASE_MIGRATION_URL` ke environment migration.
4. Jalankan `alembic upgrade head`.
5. Jalankan automated tests.

### Deployment Supabase

Urutan deployment Supabase yang disarankan:

1. Buat Supabase project dan pilih region yang dekat dengan host bot.
2. Ambil direct connection string dari tombol `Connect`.
3. Jika host bot tidak mendukung IPv6, gunakan Supavisor session pooler sebagai runtime fallback.
4. Buat role runtime dengan hak akses minimum ke schema `cardbot` jika production sudah siap.
5. Simpan `DATABASE_URL` dan `DATABASE_MIGRATION_URL` sebagai secret environment variable.
6. Jalankan `alembic upgrade head` memakai `DATABASE_MIGRATION_URL`.
7. Jalankan health check dan automated tests.
8. Deploy versi bot baru.
9. Mulai tournament baru setelah deploy.

Tournament in-memory dari versi lama tidak dimigrasikan. Sebaiknya deployment dilakukan ketika tidak ada tournament aktif.

## 12. Versi Release

Karena perubahan menambahkan persistence, multi-table, migration database, dan command baru, release disarankan memakai versi fitur baru:

```text
v1.2.0
```

## 13. Poin Konfirmasi Sebelum Eksekusi

Mohon pastikan keputusan berikut sudah sesuai:

1. Multi-table dan resume hanya berlaku untuk Poker tournament dan Rummy tournament. // Ya, benar
2. Ronde aktif yang terputus karena restart boleh diulang dari checkpoint akhir ronde sebelumnya. // Ya, boleh
3. Resume dilakukan manual memakai `/tournament-resume`, bukan otomatis mengirim panel ke channel saat bot startup. // Ya. Tombol Mulai Ronde Berikutnya tetap ditampilkan saat checkpoint akhir ronde berhasil tersimpan.
4. Tournament yang belum pernah menyelesaikan ronde tidak memiliki checkpoint resume. // Ya benar
5. Data tournament lama tetap disimpan ketika meja diarsipkan. // Ya benar
6. PostgreSQL lokal dipakai untuk development, sedangkan Supabase menjadi opsi database staging atau production. // Benar

## 14. Pengembangan Lanjutan Opsional

Setelah implementasi awal stabil, pengembangan berikut dapat dipertimbangkan secara terpisah:

- Resume di tengah ronde dengan snapshot game engine.
- Persistence dan multi-table untuk mode reguler.
- Persistence UNO.
- Dashboard admin.
- Dukungan beberapa instance bot dengan locking terdistribusi.

## 15. Referensi Supabase

- [Supabase Database overview](https://supabase.com/docs/guides/database/overview)
- [Supabase connection strings](https://supabase.com/docs/reference/postgres/connection-strings)
- [Supabase connection management](https://supabase.com/docs/guides/database/connection-management)
- [Supabase database security](https://supabase.com/docs/guides/database/secure-data/)
