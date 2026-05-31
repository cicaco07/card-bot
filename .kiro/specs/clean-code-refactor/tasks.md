# Implementation Plan: Clean Code Refactor

## Overview

Rencana ini mengubah desain refactor menjadi langkah-langkah pengkodean inkremental yang aman. Strateginya **test-first**: seluruh jaring pengaman (characterization/golden test, command snapshot, smoke/contract test) dan property-based test ditulis lebih dulu terhadap `bot.py` yang BELUM dipecah untuk menetapkan baseline hijau (Req 2.6), lalu kode dipindah mengikuti **urutan migrasi 8 langkah** pada design. Setiap langkah migrasi diakhiri dengan menjalankan `pytest` dan harus tetap hijau sebelum lanjut (Req 9.1, 9.3), serta bot harus tetap dapat dijalankan.

Sumber kebenaran untuk setiap pemindahan simbol adalah **Peta Pemindahan Simbol (Sumber Kebenaran Refactor)** pada `design.md`. Setiap langkah ekstraksi WAJIB mengikuti peta tersebut serta mempertahankan seluruh kontrak impor, pesan kesalahan bahasa Indonesia, dan tanda tangan fungsi render persis seperti sebelum refactor.

Catatan penanda:
- Sub-task bertanda `*` bersifat opsional. Di sini sub-task `*` adalah property-based test (lapisan keyakinan terukur engine, Req 3) yang melengkapi jaring pengaman characterization.
- Characterization/golden/snapshot/smoke test TIDAK ditandai opsional karena merupakan prasyarat baseline hijau (Req 2.6) yang menjadi pondasi seluruh migrasi.
- Tugas "Jalankan pytest" pada akhir tiap langkah adalah tugas verifikasi inti (bukan opsional).

## Tasks

- [x] 1. Langkah 1 — Siapkan tooling pengujian dan kerangka test
  - Tambahkan `pytest` dan `hypothesis` ke `requirements.txt` sebagai dependensi pengembangan
  - Buat direktori `tests/` di root beserta `tests/__init__.py`, `tests/properties/__init__.py`, dan `tests/conftest.py`
  - Di `conftest.py` sediakan fixture seed bersama yang memanggil `random.seed(<seed tetap>)` sebelum aksi acak engine agar shuffle/deal reprodusibel
  - Pastikan `pytest` dapat dijalankan dari satu perintah di root
  - _Requirements: 2.1, 2.5_

- [x] 2. Langkah 1 — Tulis characterization/golden/snapshot test terhadap `bot.py` lama
  - [x] 2.1 Tulis characterization test alur inti Engine_UNO (`tests/test_uno_engine.py`)
    - Skenario ber-seed: start, play kartu (termasuk wild + pilih warna, skip, reverse, +2, +4), draw, pass, call UNO, challenge UNO
    - Rekam `PlayResult.public_messages` dan ringkasan `public_state()` sebagai golden
    - _Requirements: 2.2, 1.2_

  - [x] 2.2 Tulis characterization test alur inti Engine_Poker (`tests/test_poker_engine.py`)
    - Skenario ber-seed: start (penentuan first turn + pembuangan kartu 3), play tiap pola kombinasi, pass, auto-skip pair/triple, fase adu bomb, penentuan winner/loser
    - Sertakan scoring tournament: point first/second/middle/loser serta kasus bomb +40/-40
    - _Requirements: 2.3, 1.3_

  - [x] 2.3 Tulis golden string test Modul_Presentasi UNO & Poker (`tests/test_presentation.py`)
    - Minimal satu state lobby, satu state berjalan, dan satu state selesai untuk UNO dan Poker
    - Gunakan `user_id` tetap agar string yang memuat `mention(user_id)` deterministik
    - Sertakan golden untuk pesan kesalahan berbahasa Indonesia kunci (mis. guard sesi, `reply_error`)
    - _Requirements: 2.4, 1.4, 1.6_

  - [x] 2.4 Tulis snapshot test kontrak slash command via introspeksi `tree` (`tests/test_contracts.py`)
    - Rekam nama, deskripsi, dan parameter setiap command tanpa koneksi Discord
    - _Requirements: 1.1_

  - [x] 2.5 Tulis test parameter render gambar (`tests/test_render.py`)
    - Verifikasi `(BytesIO, filename)` menghasilkan gambar Pillow mode `"RGB"` dengan dimensi sesuai formula tata letak untuk UNO dan Poker
    - Pertahankan perbedaan parameter render yang memang berbeda (ukuran thumbnail, warna border) apa adanya
    - _Requirements: 1.5, 7.3_

  - [x] 2.6 Tulis smoke/contract test importability & kontrak paket (`tests/test_contracts.py`)
    - Impor `uno.*`, `poker.*` tanpa `ImportError`/`SyntaxError`
    - Verifikasi `from uno import Card, UnoGame, UnoGameError` dan `from poker import PokerCard, PokerGame, PokerGameError`
    - Verifikasi `inspect.signature` fungsi render publik tidak berubah
    - _Requirements: 6.1, 6.2, 6.3, 8.2, 9.2_

- [x] 3. Langkah 1 — Tulis property-based test untuk 7 properti kebenaran (terhadap `bot.py` lama)
  - Semua property test memakai Hypothesis dengan minimum 100 contoh (`@settings(max_examples=100)` atau lebih) dan diberi komentar tag format `# Feature: clean-code-refactor, Property {n}: {property_text}`
  - [x]* 3.1 Tulis property test konservasi total kartu UNO (`tests/properties/test_uno_conservation.py`)
    - **Property 1: Konservasi total kartu UNO**
    - Jalankan rangkaian aksi UNO legal acak; pastikan total kartu (tangan + deck + discard) selalu konstan = 108, termasuk skenario reshuffle deck
    - Tag: `# Feature: clean-code-refactor, Property 1: ...`, min 100 contoh
    - **Validates: Requirements 3.1**

  - [x]* 3.2 Tulis property test rentang indeks giliran UNO (`tests/properties/test_uno_turn_index.py`)
    - **Property 2: Indeks giliran UNO selalu dalam rentang valid**
    - Setelah perpindahan giliran acak, pastikan `0 <= turn_index < len(players)`
    - Tag: `# Feature: clean-code-refactor, Property 2: ...`, min 100 contoh
    - **Validates: Requirements 3.4**

  - [x]* 3.3 Tulis property test anti-simetri perbandingan kombinasi Poker (`tests/properties/test_poker_compare.py`)
    - **Property 3: Anti-simetri perbandingan kombinasi Poker**
    - Untuk pasangan kombinasi valid berpola sama: `sign(compare(a,b)) == -sign(compare(b,a))` dan `compare(a,a) == 0`
    - Tag: `# Feature: clean-code-refactor, Property 3: ...`, min 100 contoh
    - **Validates: Requirements 3.2**

  - [x]* 3.4 Tulis property test order-independence evaluasi kombinasi (`tests/properties/test_poker_eval_order.py`)
    - **Property 4: Evaluasi kombinasi tidak bergantung urutan kartu masukan**
    - Permutasi urutan kartu menghasilkan `kind`, `pattern`, dan `rank_key` identik
    - Tag: `# Feature: clean-code-refactor, Property 4: ...`, min 100 contoh
    - **Validates: Requirements 3.3**

  - [x]* 3.5 Tulis property test himpunan kartu tak valid memunculkan error (`tests/properties/test_poker_invalid.py`)
    - **Property 5: Himpunan kartu tak valid memunculkan error**
    - Untuk himpunan kartu (tanpa rank "3") yang tidak membentuk kombinasi valid, `evaluate_combination` memunculkan `PokerGameError`
    - Tag: `# Feature: clean-code-refactor, Property 5: ...`, min 100 contoh
    - **Validates: Requirements 3.5**

  - [x]* 3.6 Tulis property test kartu rank "3" memunculkan error (`tests/properties/test_poker_rank_three.py`)
    - **Property 6: Kartu rank "3" pada evaluasi memunculkan error**
    - Untuk himpunan yang memuat minimal satu kartu rank "3", `evaluate_combination` memunculkan `PokerGameError`
    - Tag: `# Feature: clean-code-refactor, Property 6: ...`, min 100 contoh
    - **Validates: Requirements 3.6**

  - [x]* 3.7 Tulis property test konsistensi parameter render gambar (`tests/properties/test_render_layout.py`)
    - **Property 7: Parameter render gambar konsisten dengan formula tata letak**
    - Untuk himpunan kartu valid (UNO & Poker) dan halaman valid, render mengembalikan gambar Pillow mode `"RGB"` dengan kolom = `min(5, jumlah_kartu_tampil)` dan dimensi sesuai formula, tanpa galat
    - Tag: `# Feature: clean-code-refactor, Property 7: ...`, min 100 contoh
    - **Validates: Requirements 1.5, 7.3**

- [x] 4. Checkpoint Langkah 1 — Tetapkan baseline hijau
  - Jalankan `pytest` terhadap kode SEBELUM refactor; seluruh characterization/golden/snapshot/smoke test harus lulus
  - Pastikan semua tests pass, tanyakan ke user jika ada pertanyaan
  - _Requirements: 2.6_

- [x] 5. Langkah 2 — Pecah leaf Engine Poker (`poker/game.py`)
  - [x] 5.1 Buat `poker/cards.py`
    - Pindahkan tipe `Suit`/`Rank`, konstanta (`SUITS`, `RANKS`, `PLAYABLE_RANKS`, `STRAIGHT_RANKS`, `RANK_VALUES`, `PLAYABLE_RANK_VALUES`, `STRAIGHT_RANK_VALUES`, `SUIT_VALUES`, `SUIT_LABELS`, `START_THREE_PRIORITY`, `RANK_LABELS`), kelas `PokerCard`, dan `PokerGameError` sesuai Peta Pemindahan Simbol
    - Tambahkan docstring tingkat modul
    - _Requirements: 5.1, 8.3_

  - [x] 5.2 Buat `poker/combinations.py`
    - Pindahkan `PokerCombination`, `evaluate_combination`, `compare_combinations`, serta helper privat `_straight_key`, `_cards_label`; impor dari `poker.cards`
    - Pertahankan seluruh pesan kesalahan identik
    - Tambahkan docstring tingkat modul
    - _Requirements: 5.2, 5.4, 8.3_

  - [x] 5.3 Rampingkan `poker/game.py` dan tambahkan re-export
    - Sisakan `PokerStatus`, `PokerPlayer`, `PokerActionResult`, `PokerGame`; impor dari `poker.cards` dan `poker.combinations`
    - Re-export seluruh simbol publik (termasuk `PokerCard`, `PokerGameError`, `evaluate_combination`, `compare_combinations`) agar `from poker.game import X` tetap valid
    - Pastikan `from poker.game import PokerCard` yang dipakai `poker/assets.py` tetap berfungsi
    - _Requirements: 5.3, 6.2, 6.4_

  - [x] 5.4 Jalankan pytest Langkah 2
    - Jalankan `pytest`; pastikan baseline tetap hijau setelah pemecahan engine Poker
    - _Requirements: 9.1, 9.3_

- [x] 6. Langkah 3 — Ekstrak lapisan domain dari `bot.py`
  - [x] 6.1 Buat `cardbot/__init__.py` dan `cardbot/constants.py`
    - Pindahkan `APP_VERSION`, `COLOR_CHOICES`, `POKER_MODE_CHOICES`, `POKER_TOURNAMENT_POINTS`
    - Tambahkan docstring tingkat modul
    - _Requirements: 4.5, 8.3_

  - [x] 6.2 Buat `cardbot/changelog.py`
    - Pindahkan `CHANGELOG_ENTRIES`, `semver_tuple`, `latest_changelog_entry`, `format_changelog_entry`, `format_public_changelog_entry`
    - _Requirements: 4.5, 8.3_

  - [x] 6.3 Buat `cardbot/text_utils.py`
    - Pindahkan `mention` dan `format_tournament_round_summary` (di leaf agar tak ada siklus `sessions ↔ presentation`)
    - _Requirements: 7.1, 8.3_

  - [x] 6.4 Buat `cardbot/state.py`
    - Pindahkan registry `sessions_by_channel`, `poker_sessions_by_channel`, `changelog_seen_versions_by_user`
    - Tambahkan accessor client privat `set_client(client)` / `get_client()`; rujuk tipe session hanya via `TYPE_CHECKING` (tanpa impor runtime)
    - _Requirements: 4.1, 8.3, 8.4_

  - [x] 6.5 Buat `cardbot/sessions.py`
    - Pindahkan `UnoSession`, `PokerSession`, `require_channel_id`, `get_session`, `get_poker_session`, `require_session_player`, `require_poker_player`, `finalize_poker_round_if_needed`
    - Pertahankan logika scoring tournament identik (first/second/middle/loser dan bomb +40/-40)
    - _Requirements: 4.1, 4.6, 8.1, 8.3_

  - [x] 6.6 Sambungkan kembali `bot.py` ke modul domain baru
    - Ganti definisi lama di `bot.py` dengan impor dari `cardbot.constants/changelog/text_utils/state/sessions` agar bot tetap berjalan
    - Hindari impor melingkar antar modul baru
    - _Requirements: 6.4, 8.2, 8.4_

  - [x] 6.7 Jalankan pytest Langkah 3
    - Jalankan `pytest`; pastikan tetap hijau setelah ekstraksi lapisan domain
    - _Requirements: 9.1, 9.3_

- [x] 7. Langkah 4 — Ekstrak presentasi murni
  - [x] 7.1 Buat `cardbot/presentation/__init__.py` dan `cardbot/presentation/uno.py`
    - Pindahkan `lobby_text`, `public_state_text`, `finished_text`, `table_text`, `hand_text`, `rules_embed`, `table_visuals`, `hand_visuals`
    - Modul murni: hanya hasilkan `str`/`discord.Embed`/`list[discord.File]`, tanpa mengimpor `ui`
    - Tambahkan docstring tingkat modul
    - _Requirements: 4.2, 8.3, 8.4_

  - [x] 7.2 Buat `cardbot/presentation/poker.py`
    - Pindahkan `poker_lobby_text`, `poker_state_text`, `poker_finished_text`, `poker_table_text`, `poker_hand_text`, `poker_rules_embed`, `poker_table_visuals`, `poker_hand_visuals`, `tournament_scoreboard_text`
    - Modul murni, tanpa mengimpor `ui`
    - _Requirements: 4.2, 8.3, 8.4_

  - [x] 7.3 Sambungkan `bot.py` ke modul presentasi dan jalankan pytest Langkah 4
    - Perbarui impor presentasi di `bot.py`; jalankan `pytest` dan pastikan golden string tetap identik (hijau)
    - _Requirements: 6.4, 9.1, 9.3_

- [x] 8. Langkah 5 — Ekstrak Layanan Timer Poker
  - [x] 8.1 Buat `cardbot/timer.py` dengan dependency injection callback
    - Pindahkan `cancel_poker_turn_timer`, `schedule_poker_turn_timer`, `poker_turn_timer_worker`
    - `schedule_poker_turn_timer(session, on_timeout)` menerima coroutine callback; modul hanya bergantung pada `sessions` dan engine poker (tanpa impor `ui`/`presentation`)
    - Pertahankan logika debounce token (`turn_timer_token`) dan pembatalan task identik
    - Tambahkan docstring tingkat modul
    - _Requirements: 4.4, 8.3, 8.4_

  - [x] 8.2 Sambungkan `bot.py` ke `cardbot.timer` dan jalankan pytest Langkah 5
    - Suplai callback timeout dari `bot.py` sementara; jalankan `pytest` dan pastikan hijau
    - _Requirements: 6.4, 9.1, 9.3_

- [x] 9. Langkah 6 — Ekstrak lapisan UI
  - [x] 9.1 Buat `cardbot/ui/__init__.py` dan `cardbot/ui/common.py`
    - Pindahkan `reply_error` (pemilihan prefix "Remi Poker"/"UNO" sesuai tipe error) dengan logika percabangan identik
    - _Requirements: 4.3, 8.3_

  - [x] 9.2 Buat `cardbot/ui/uno.py`
    - Pindahkan factory `table_view`, siklus hidup pesan (`refresh_table_message`, `repost_table_message`, `delete_table_message`, `update_table_from_interaction`, `add_result_log`), serta seluruh View/Select UNO (`LobbyView`, `FinishedView`, `GameView`, `CardSelect`, `ChallengeTargetSelect`, `ChallengeUnoView`, `HandView`, `ColorPickView`)
    - Letakkan View + factory + siklus hidup pesan dalam satu modul untuk memutus siklus `ui ↔ messaging`; gunakan `state.get_client()` untuk mengirim/menghapus pesan
    - _Requirements: 4.3, 8.3, 8.4_

  - [x] 9.3 Buat `cardbot/ui/poker.py`
    - Pindahkan factory `poker_table_view`, siklus hidup pesan (`refresh_poker_table_message`, `repost_poker_table_message`, `delete_poker_table_message`, `update_poker_table_from_interaction`, `add_poker_result_log`), serta seluruh View/Select Poker (`PokerTimerSelect`, `PokerModeSelect`, `PokerTournamentRoundSelect`, `PokerLobbyView`, `PokerFinishedView`, `PokerTournamentRoundFinishedView`, `PokerGameView`, `PokerCardSelect`, `PokerHandView`)
    - Sediakan callback `_on_turn_timeout(session)` yang disuplai ke `timer.schedule_poker_turn_timer` (memutus siklus `timer ↔ messaging`)
    - _Requirements: 4.3, 4.4, 8.3, 8.4_

  - [x] 9.4 Sambungkan `bot.py` ke lapisan UI dan jalankan pytest Langkah 6
    - Perbarui impor UI di `bot.py`; jalankan `pytest` dan pastikan hijau
    - _Requirements: 6.4, 9.1, 9.3_

- [x] 10. Langkah 7 — Ekstrak client/commands/app dan ubah `bot.py` menjadi shim
  - [x] 10.1 Buat `cardbot/client.py`
    - Pindahkan `intents`, `bot = discord.Client(...)`, `tree = app_commands.CommandTree(bot)`; tanpa dependensi paket internal
    - _Requirements: 4.7, 8.3_

  - [x] 10.2 Buat `cardbot/commands.py`
    - Pindahkan `on_ready`, flag `commands_synced`, dan seluruh `@tree.command` (`uno_start`, `changelog`, `publish_changelog`, `uno_hand`, `uno_status`, `uno_play`, `poker_start`, `poker_hand`, `poker_status`)
    - Pertahankan nama, deskripsi, dan parameter command identik
    - _Requirements: 4.7, 1.1, 8.3_

  - [x] 10.3 Buat `cardbot/app.py`
    - Pindahkan `main()`: muat env, `state.set_client(bot)`, impor `commands` (agar dekorator terdaftar), lalu `bot.run(token)` dengan perilaku startup identik
    - _Requirements: 4.7, 8.3_

  - [x] 10.4 Ubah `bot.py` root menjadi shim tipis
    - Ganti isi `bot.py` menjadi `from cardbot.app import main` + blok `if __name__ == "__main__": main()`
    - Perbarui seluruh pernyataan impor yang masih merujuk simbol lama
    - _Requirements: 4.7, 9.4, 6.4_

  - [x] 10.5 Jalankan pytest Langkah 7
    - Jalankan `pytest`; pastikan hijau setelah seluruh ekstraksi
    - _Requirements: 9.1, 9.3_

- [x] 11. Langkah 8 — Penyatuan duplikasi yang aman
  - [x] 11.1 Satukan helper identik antar jalur UNO & Poker yang aman
    - Satukan hanya helper yang keluarannya tetap identik (mis. teks vote, badge nomor, utilitas gambar) ke lokasi bersama
    - Pertahankan perbedaan parameter render yang memang berbeda (ukuran thumbnail, warna border) apa adanya
    - Batalkan penyatuan apa pun yang mengubah golden presentasi/render
    - _Requirements: 7.1, 7.2, 7.3_

  - [x] 11.2 Jalankan pytest Langkah 8
    - Jalankan `pytest`; golden presentasi/render harus tetap identik (hijau)
    - _Requirements: 9.1, 9.3_

- [x] 12. Checkpoint akhir — Verifikasi importability, entry point, dan full pytest
  - [x] 12.1 Verifikasi importability penuh seluruh modul
    - Impor setiap modul `cardbot.*`, `uno.*`, `poker.*` secara terisolasi tanpa `ImportError`/`SyntaxError`, buktikan tidak ada circular import
    - Verifikasi kontrak paket `from uno import ...`, `from poker import ...`, dan `from poker.game import ...` masih valid; signature render publik tidak berubah
    - _Requirements: 8.2, 8.4, 9.2, 6.1, 6.2, 6.3, 5.3_

  - [x] 12.2 Verifikasi entry point
    - Pastikan `cardbot.app.main` callable dan `bot.py` shim memanggilnya; perilaku menjalankan bot tidak berubah bagi pengguna
    - _Requirements: 4.7, 9.4_

  - [x] 12.3 Jalankan full pytest final
    - Jalankan seluruh suite `pytest` (characterization, golden, snapshot, smoke/contract, dan property test); seluruh test harus lulus sama seperti baseline
    - Pastikan semua tests pass, tanyakan ke user jika ada pertanyaan
    - _Requirements: 9.1_

## Notes

- Sub-task bertanda `*` (property-based test, Property 1–7) bersifat opsional dan dapat dilewati untuk MVP lebih cepat; karena memvalidasi Req 3, sangat disarankan tetap diimplementasikan sebagai lapisan keyakinan terukur engine.
- Tiap property test adalah sub-task tersendiri, ditulis dengan Hypothesis, minimum 100 contoh, dan diberi komentar tag `# Feature: clean-code-refactor, Property {n}: ...` yang merujuk properti pada `design.md`.
- Urutan tugas mengikuti urutan migrasi 8 langkah pada design; tiap langkah migrasi diakhiri dengan `pytest` hijau (Req 9.1, 9.3) dan menjaga bot tetap dapat dijalankan.
- Setiap langkah ekstraksi mengikuti Peta Pemindahan Simbol pada `design.md` sebagai sumber kebenaran dan mempertahankan kontrak impor, pesan kesalahan, serta tanda tangan render.
