# Requirements Document

## Introduction

Fitur ini adalah refactor struktur file dan kode (clean code) untuk bot Discord permainan kartu yang berisi modul UNO dan Remi Poker. Tujuan utamanya adalah memperbaiki keterbacaan, kohesi, dan pemisahan tanggung jawab kode TANPA mengubah perilaku yang sudah ada (gameplay, command Discord, teks pesan, dan output gambar harus tetap identik).

Masalah clean code terbesar saat ini terkonsentrasi pada `bot.py` (sekitar 1804 baris) yang berperan sebagai "god module": mencampur konstanta aplikasi, dataclass session, registry session in-memory, fungsi formatter teks/embed untuk UNO dan Poker, helper siklus hidup pesan Discord, logika timer asyncio, banyak kelas Discord UI View/Select, setup client Discord, event handler, command handler slash, dan entry point. Selain itu `poker/game.py` (sekitar 714 baris) adalah engine murni yang masih sehat tetapi terlalu besar dan bisa dipecah menjadi file-file yang lebih kohesif. Modul engine `uno/game.py` relatif bersih.

Karena belum ada satu pun automated test di repositori, refactor yang menjamin perilaku tidak berubah sangat terbantu oleh jaring pengaman berupa characterization/regression test. Oleh karena itu requirements mencakup pembuatan test sebagai prasyarat dan pembuktian bahwa logika dipertahankan.

Refactor ini bersifat murni struktural: tidak ada penambahan fitur baru, tidak ada perubahan aturan permainan, dan tidak ada perubahan kontrak command/pesan yang terlihat pengguna.

## Glossary

- **Bot_Sistem**: Keseluruhan aplikasi bot Discord permainan kartu (kode di `bot.py` beserta paket `uno` dan `poker`).
- **Engine_UNO**: Modul logika permainan UNO murni yang independen dari Discord (saat ini `uno/game.py`, kelas `UnoGame`).
- **Engine_Poker**: Modul logika permainan Remi Poker murni yang independen dari Discord (saat ini `poker/game.py`, kelas `PokerGame`).
- **Modul_Presentasi**: Sekumpulan fungsi yang membentuk teks, embed, dan visual gambar untuk panel meja, lobby, dan tangan pemain (saat ini fungsi `*_text`, `*_visuals`, `*_embed`, `*_view` di `bot.py`).
- **Modul_Session**: Komponen yang menyimpan state per-channel dan logika non-engine terkait sesi (saat ini dataclass `UnoSession` dan `PokerSession` serta registry `sessions_by_channel`/`poker_sessions_by_channel`).
- **Modul_UI**: Sekumpulan kelas Discord `discord.ui.View` dan `discord.ui.Select` yang menangani interaksi tombol/dropdown (saat ini `LobbyView`, `GameView`, `PokerGameView`, `CardSelect`, dan lainnya di `bot.py`).
- **Modul_Command**: Handler slash command Discord (saat ini fungsi yang didekorasi `@tree.command` seperti `uno_start`, `poker-start`) dan event handler (`on_ready`) serta entry point `main()`.
- **Layanan_Timer**: Logika timer giliran berbasis asyncio untuk Poker (saat ini `schedule_poker_turn_timer`, `cancel_poker_turn_timer`, `poker_turn_timer_worker`).
- **Perilaku_Teramati**: Semua keluaran dan efek yang terlihat oleh pengguna atau klien Discord, mencakup: nama dan parameter slash command, isi teks pesan/embed, urutan dan isi pesan publik permainan, hasil aturan permainan, dan gambar kartu yang dirender.
- **Kontrak_Publik_Paket**: Simbol yang diekspor oleh `uno/__init__.py` dan `poker/__init__.py` beserta jalur impor yang dipakai modul lain.
- **Test_Karakterisasi**: Automated test yang merekam Perilaku_Teramati saat ini agar perubahan perilaku akibat refactor dapat terdeteksi.
- **Pengembang**: Orang yang memelihara dan mengembangkan Bot_Sistem.

## Requirements

### Requirement 1: Pemertahanan Perilaku Selama Refactor

**User Story:** Sebagai Pengembang, saya ingin refactor tidak mengubah perilaku apa pun yang terlihat, sehingga pengguna dan pemain tidak merasakan perbedaan setelah refactor.

#### Acceptance Criteria

1. THE Bot_Sistem SHALL mempertahankan nama, deskripsi, dan parameter setiap slash command yang ada sebelum refactor secara identik.
2. WHEN sebuah aksi permainan dijalankan dengan input yang sama, THE Engine_UNO SHALL menghasilkan state dan daftar pesan publik yang identik dengan perilaku sebelum refactor.
3. WHEN sebuah aksi permainan dijalankan dengan input yang sama, THE Engine_Poker SHALL menghasilkan state dan daftar pesan publik yang identik dengan perilaku sebelum refactor.
4. WHEN teks lobby, teks status, teks selesai, atau embed rules dibentuk untuk state yang sama, THE Modul_Presentasi SHALL menghasilkan string keluaran yang identik dengan perilaku sebelum refactor.
5. WHEN gambar kartu atau gambar tangan dirender untuk input yang sama, THE Modul_Presentasi SHALL menghasilkan gambar dengan parameter render yang identik (ukuran kanvas, tata letak, warna, dan teks) dengan perilaku sebelum refactor.
6. THE Bot_Sistem SHALL mempertahankan setiap pesan kesalahan berbahasa Indonesia yang ditampilkan kepada pengguna secara identik dengan perilaku sebelum refactor.

### Requirement 2: Jaring Pengaman Test Sebelum Refactor

**User Story:** Sebagai Pengembang, saya ingin ada automated test yang merekam perilaku saat ini sebelum kode dipindah, sehingga perubahan perilaku yang tidak disengaja dapat terdeteksi otomatis.

#### Acceptance Criteria

1. THE Bot_Sistem SHALL menyediakan kerangka kerja pengujian (test framework) yang dapat dijalankan dari satu perintah baris perintah.
2. THE Test_Karakterisasi SHALL mencakup alur permainan inti Engine_UNO meliputi memulai game, memainkan kartu, mengambil kartu, pass, call UNO, dan challenge UNO.
3. THE Test_Karakterisasi SHALL mencakup alur permainan inti Engine_Poker meliputi memulai game, memainkan kombinasi, pass, auto-skip, fase adu bomb, dan penentuan winner/loser.
4. THE Test_Karakterisasi SHALL mencakup keluaran Modul_Presentasi untuk minimal satu state lobby, satu state game berjalan, dan satu state selesai pada masing-masing UNO dan Poker.
5. WHERE sebuah fungsi mengandalkan keacakan, THE Test_Karakterisasi SHALL menetapkan seed acak yang tetap agar hasil dapat direproduksi.
6. WHEN suite Test_Karakterisasi dijalankan terhadap kode sebelum refactor, THE Bot_Sistem SHALL menyelesaikan seluruh test dengan status lulus.

### Requirement 3: Properti Round-Trip dan Determinisme Engine

**User Story:** Sebagai Pengembang, saya ingin properti kebenaran engine diuji secara menyeluruh, sehingga keyakinan bahwa logika permainan tetap utuh menjadi terukur.

#### Acceptance Criteria

1. WHEN sebuah deck dibangun lalu seluruh kartu dimainkan dan ditarik mengikuti aturan, THE Engine_UNO SHALL mempertahankan invarian bahwa jumlah total kartu di seluruh tangan, deck, dan discard pile tetap konstan.
2. WHEN dua kombinasi Poker dibandingkan, THE Engine_Poker SHALL menghasilkan urutan perbandingan yang konsisten (anti-simetris) untuk pasangan kombinasi mana pun yang valid.
3. FOR ALL himpunan kartu valid yang membentuk kombinasi yang sama, THE Engine_Poker SHALL mengevaluasi `kind` dan `pattern` kombinasi yang identik tanpa bergantung pada urutan masukan kartu.
4. WHEN giliran berpindah berulang kali pada Engine_UNO, THE Engine_UNO SHALL selalu menetapkan indeks giliran dalam rentang jumlah pemain yang valid.
5. IF himpunan kartu yang tidak membentuk kombinasi valid diberikan, THEN THE Engine_Poker SHALL memunculkan `PokerGameError`.
6. IF kartu dengan rank "3" diberikan ke evaluasi kombinasi, THEN THE Engine_Poker SHALL memunculkan `PokerGameError`.

### Requirement 4: Dekomposisi bot.py Menjadi Modul Kohesif

**User Story:** Sebagai Pengembang, saya ingin `bot.py` dipecah menjadi modul-modul dengan tanggung jawab tunggal, sehingga kode lebih mudah dibaca, ditelusuri, dan dipelihara.

#### Acceptance Criteria

1. THE Bot_Sistem SHALL memisahkan Modul_Session ke dalam modul tersendiri yang terpisah dari setup Discord client.
2. THE Bot_Sistem SHALL memisahkan Modul_Presentasi (fungsi pembentuk teks, embed, view selector, dan visual) ke dalam modul tersendiri terpisah dari Modul_Command.
3. THE Bot_Sistem SHALL memisahkan Modul_UI (kelas `discord.ui.View` dan `discord.ui.Select`) ke dalam modul tersendiri terpisah dari Modul_Command.
4. THE Bot_Sistem SHALL memisahkan Layanan_Timer Poker ke dalam modul tersendiri terpisah dari Modul_UI.
5. THE Bot_Sistem SHALL memisahkan konstanta aplikasi dan logika changelog ke dalam modul tersendiri terpisah dari logika permainan.
6. WHERE sebuah modul hasil pemisahan dibuat, THE Bot_Sistem SHALL menjaga setiap modul memuat hanya satu tanggung jawab utama yang kohesif.
7. THE Bot_Sistem SHALL mempertahankan satu entry point yang menjalankan bot dengan perilaku startup yang identik dengan `main()` sebelum refactor.

### Requirement 5: Pemecahan Engine Poker yang Besar

**User Story:** Sebagai Pengembang, saya ingin `poker/game.py` yang besar dipecah menjadi unit-unit kohesif, sehingga evaluasi kombinasi, definisi kartu, dan mesin permainan lebih mudah dipahami.

#### Acceptance Criteria

1. THE Engine_Poker SHALL memisahkan definisi kartu, rank, suit, dan konstanta terkait ke dalam unit tersendiri.
2. THE Engine_Poker SHALL memisahkan logika evaluasi dan perbandingan kombinasi (`evaluate_combination`, `compare_combinations`) ke dalam unit tersendiri terpisah dari kelas mesin permainan.
3. WHERE pemecahan dilakukan, THE Engine_Poker SHALL mempertahankan seluruh tanda tangan fungsi dan kelas publik yang dipakai modul lain.
4. THE Engine_Poker SHALL mempertahankan seluruh pesan kesalahan permainan secara identik dengan perilaku sebelum refactor.

### Requirement 6: Pemertahanan Kontrak Impor dan API Paket

**User Story:** Sebagai Pengembang, saya ingin jalur impor dan simbol publik paket tetap stabil, sehingga modul yang bergantung pada paket tidak rusak setelah refactor.

#### Acceptance Criteria

1. THE Kontrak_Publik_Paket SHALL mempertahankan simbol yang diekspor `uno/__init__.py` (`Card`, `UnoGame`, `UnoGameError`) tetap dapat diimpor dari paket `uno`.
2. THE Kontrak_Publik_Paket SHALL mempertahankan simbol yang diekspor `poker/__init__.py` (`PokerCard`, `PokerGame`, `PokerGameError`) tetap dapat diimpor dari paket `poker`.
3. WHEN sebuah fungsi render dipindah, THE Modul_Presentasi SHALL mempertahankan tanda tangan fungsi render publik (`render_card_image`, `render_hand_image`, `render_poker_hand_image`, `render_play_image`) tetap dapat dipanggil dengan argumen yang sama.
4. IF sebuah modul memindahkan simbol ke lokasi baru, THEN THE Bot_Sistem SHALL memperbarui seluruh pernyataan impor yang merujuk simbol tersebut agar impor tetap berhasil.

### Requirement 7: Pengurangan Duplikasi yang Aman

**User Story:** Sebagai Pengembang, saya ingin duplikasi kode antara jalur UNO dan Poker dikurangi jika aman, sehingga pemeliharaan lebih ringkas tanpa risiko mengubah perilaku.

#### Acceptance Criteria

1. WHERE terdapat helper yang identik secara fungsional di jalur UNO dan Poker (misalnya pembentukan teks vote, badge nomor, atau utilitas gambar), THE Bot_Sistem SHALL menyatukan helper tersebut ke satu lokasi bersama selama keluaran tetap identik.
2. IF penyatuan sebuah helper akan mengubah Perilaku_Teramati, THEN THE Bot_Sistem SHALL mempertahankan helper terpisah tanpa penyatuan.
3. THE Bot_Sistem SHALL mempertahankan perbedaan parameter render yang memang berbeda antara UNO dan Poker (misalnya ukuran thumbnail dan warna border) secara apa adanya.

### Requirement 8: Standar Kualitas Clean Code

**User Story:** Sebagai Pengembang, saya ingin kode hasil refactor mengikuti standar clean code yang konsisten, sehingga keterbacaan dan konsistensi gaya meningkat.

#### Acceptance Criteria

1. THE Bot_Sistem SHALL mempertahankan anotasi tipe pada tanda tangan fungsi dan kelas yang dipindah sekurang-kurangnya selengkap sebelum refactor.
2. THE Bot_Sistem SHALL mempertahankan setiap modul hasil refactor agar dapat diimpor tanpa galat sintaks maupun galat impor.
3. WHERE sebuah modul baru dibuat, THE Bot_Sistem SHALL menyertakan docstring tingkat modul yang menjelaskan tanggung jawab modul tersebut.
4. THE Bot_Sistem SHALL menghindari impor melingkar (circular import) antar modul hasil pemisahan.

### Requirement 9: Verifikasi Pasca-Refactor

**User Story:** Sebagai Pengembang, saya ingin bukti terukur bahwa refactor tidak mengubah perilaku, sehingga refactor dapat diterima dengan percaya diri.

#### Acceptance Criteria

1. WHEN suite Test_Karakterisasi dijalankan setelah refactor, THE Bot_Sistem SHALL menyelesaikan seluruh test dengan status lulus yang sama seperti sebelum refactor.
2. WHEN modul utama diimpor setelah refactor, THE Bot_Sistem SHALL berhasil memuat seluruh modul tanpa galat.
3. IF sebuah Test_Karakterisasi gagal setelah pemindahan kode, THEN THE Pengembang SHALL memulihkan perilaku agar test kembali lulus sebelum melanjutkan langkah refactor berikutnya.
4. THE Bot_Sistem SHALL mempertahankan kemampuan dijalankan melalui entry point yang sama tanpa perubahan instruksi menjalankan bagi pengguna.
