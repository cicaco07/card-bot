# Changelog

Format versi memakai `major.feature.patch`.

- `major`: update besar atau perubahan besar pada arah project.
- `feature`: penambahan fitur/mode baru.
- `patch`: update minor, balancing, atau bugfix.

## 1.2.0 - 2026-06-02

Multi-table tournament dan checkpoint PostgreSQL.

- Menambahkan multi-table untuk Poker Tournament dan Rummy Tournament dengan kode meja unik.
- Menyimpan checkpoint PostgreSQL setelah ronde tournament selesai dan mendukung resume manual dari ronde berikutnya.
- Menambahkan command `/tournament-list`, `/tournament-resume`, dan `/tournament-archive`.
- Mendukung PostgreSQL lokal melalui Docker Compose serta connection string Supabase untuk deployment.
- Mempertahankan tombol **Mulai Ronde Berikutnya** pada panel akhir ronde setelah checkpoint berhasil tersimpan.

## 1.1.16 - 2026-06-03

Transfer bonus flip card Rummy.

- Memberikan bonus kepada pemain yang melakukan flip card sebesar total penalti yang diterapkan kepada pemain terdampak.
- Menampilkan rincian bonus flip dan pemain yang membayar penalti pada hasil akhir ronde.
- Mempertahankan penalti maksimal satu kali per pemain terdampak berdasarkan nilai kartu flip.

## 1.1.15 - 2026-06-02

Koreksi pemicu penalti flip card Rummy.

- Membatasi flip card hanya saat pemain mengambil buangan, menurunkan meld bukti, lalu memakai satu kartu terakhirnya sebagai **Closed Card** pada giliran yang sama.
- Menghapus penalti flip dari closed card mandiri dan dari histori meld bukti pada giliran sebelumnya.
- Menerapkan penalti kepada pemilik kartu target serta pemilik kartu di atas target yang ikut terambil saat flip card.

## 1.1.14 - 2026-06-02

Urutan giliran tournament Rummy.

- Mengacak pemain awal ronde pertama tournament Rummy dengan arah searah jarum jam.
- Memulai ronde tournament berikutnya dari pemain dengan skor kumulatif terendah.
- Mengubah arah ronde tournament berikutnya menjadi berlawanan arah jarum jam jika ronde sebelumnya menghasilkan penalti flip.

## 1.1.13 - 2026-06-02

Penalti flip tunggal dan batas joker Rummy.

- Menerapkan penalti flip maksimal satu kali per pemain terdampak saat **Closed Card**, bukan setiap kali kartu buangan dijadikan meld bukti.
- Menyembunyikan kandidat penalti flip selama ronde masih berjalan dan menampilkannya pada hasil akhir.
- Membatasi joker agar hanya dapat menggantikan kartu angka `2-10`, bukan `J`, `Q`, `K`, atau Ace.

## 1.1.12 - 2026-06-02

Skor normal dan rincian closed card Rummy.

- Menghapus multiplier Go Rummy agar seluruh skor ronde dihitung normal.
- Menghitung penalti tanda flip berdasarkan kartu **Closed Card**, bukan kartu buangan yang dijadikan meld.
- Menampilkan rincian kartu untuk meld terbuka, meld tertutup, deadwood, dan penalti flip pada hasil akhir.

## 1.1.11 - 2026-06-01

Rule Ace dan konfirmasi ambil buangan Rummy.

- Melarang mengambil Ace dari buangan dan membuang Ace sebelum pemain membuka meld miliknya sendiri yang tidak memakai Ace.
- Menerapkan larangan juga saat Ace ikut terambil di atas target buangan atau dipakai sebagai closed card.
- Mengubah panel **Ambil Buangan** menjadi pilihan target dengan tombol **Konfirmasi Ambil**.

## 1.1.10 - 2026-06-01

Closed card terakhir dan penalti flip Rummy.

- Mengizinkan kartu terakhir dipakai sebagai closed card untuk langsung menutup ronde.
- Mengganti bonus closed card menjadi penalti flip bagi pemain yang kartu buangannya dijadikan target meld bukti.
- Menampilkan kartu penalti flip pada meja dan rincian pengurangannya pada skor akhir.

## 1.1.9 - 2026-06-01

Emoji suit dan meld joker panjang Rummy.

- Mengganti seluruh label kartu publik Rummy menjadi simbol suit ringkas seperti `6 ♦️`.
- Mengizinkan meld bukti buangan berisi lebih dari 3 kartu selama tetap valid.
- Memastikan run seperti `4-5-Joker-7-8` diterima.

## 1.1.8 - 2026-06-01

Koreksi meld bukti ambil tiga buangan Rummy.

- Mengubah meld bukti saat mengambil 3 kartu buangan menjadi tepat 3 kartu bersama minimal 2 kartu tangan sebelumnya.
- Membebaskan dua kartu di atas target untuk disimpan atau dibuang kembali.

## 1.1.7 - 2026-06-01

Publikasi changelog berurutan.

- Mendeteksi versi changelog yang terlewati pada histori channel.
- Mengirim seluruh changelog publik yang belum diposting secara berurutan.
- Menyelaraskan versi aplikasi dengan changelog terbaru.

## 1.1.6 - 2026-06-01

Detail skor dan log suit Rummy.

- Menampilkan rincian meld terbuka, meld tangan, deadwood, bonus closed card, subtotal, dan multiplier Go Rummy pada hasil akhir ronde.
- Meringkas kartu pada log aktivitas dengan simbol suit, misalnya `8 ♥️`.

## 1.1.5 - 2026-06-01

Koreksi meld bukti ambil dua buangan Rummy.

- Mengubah meld bukti saat mengambil 2 kartu buangan menjadi tepat 3 kartu bersama minimal 2 kartu tangan sebelumnya.
- Membebaskan kartu teratas yang ikut terambil untuk disimpan atau dibuang kembali.
- Mempertahankan meld bukti tepat 4 kartu saat mengambil 3 kartu buangan.

## 1.1.4 - 2026-06-01

Informasi pembuang kartu Rummy.

- Menampilkan pemain yang membuang setiap kartu pada panel 3 buangan teratas.
- Menampilkan pemain pembuang kartu pada pilihan draw dari buangan.

## 1.1.3 - 2026-06-01

Penegasan meld bukti buangan Rummy.

- Mewajibkan meld bukti tepat 3 kartu saat mengambil 1 kartu buangan.
- Mewajibkan meld bukti tepat 4 kartu saat mengambil 2-3 kartu buangan.
- Menampilkan jumlah kartu meld bukti yang diwajibkan pada meja dan panel kartu pemain.

## 1.1.2 - 2026-06-01

Perbaikan alur giliran Rummy.

- Mengubah meld bukti setelah mengambil buangan menjadi pilihan manual pemain sambil tetap mewajibkan kartu target dipakai sebelum discard.
- Melanjutkan ronde setelah pemain menghabiskan tangan melalui meld atau discard biasa selama deck belum habis dan belum ada closed card.
- Melewati pemain yang sudah tidak memiliki kartu saat menentukan giliran berikutnya.

## 1.1.1 - 2026-06-01

Penyempurnaan rules Rummy.

- Membatasi pengambilan kartu buangan menjadi maksimal 3 kartu teratas.
- Mewajibkan kartu target dari buangan langsung menjadi meld bukti publik yang terkunci.
- Menampilkan 3 kartu buangan teratas dan meld terbuka kepada seluruh pemain.
- Menambahkan tombol **Turunkan Meld** dan **Gabungkan Meld** serta larangan membuang Ace sebelum pemain membuka minimal satu meld.
- Menambah joker Rummy menjadi 4 kartu: 2 joker merah dan 2 joker hitam tanpa mengubah deck standar.
- Menambahkan rule Go Rummy yang menggandakan seluruh poin ronde.

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
