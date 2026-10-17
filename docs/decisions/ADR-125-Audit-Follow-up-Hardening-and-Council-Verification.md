# ADR-125: Audit Follow-up Hardening & Council-Based Verification

## Status
Accepted (temuan audit pertama di commit `c670ccb`; council kedua beserta perbaikannya di commit yang menambahkan ADR ini, 2026-10-17)

## Date
2026-10-16 (diperbarui 2026-10-17)

## Context
Audit atas ADR-004–118 dan Issue #1–#24, dicocokkan dengan kode di `ccdb5c0`, menemukan:

1. **Kebocoran workspace di jalur scrape metadata**: `MetadataScraperEngine` dibuat sekali saat modul dimuat (`backend/routers/scrape.py`) dengan `NovalpieAdapter()` tanpa workspace, sehingga konfigurasi auth/konkurensi Novalpie diambil dari variabel global `ACTIVE_WORKSPACE`, bukan dari request (CLAUDE.md invariant #2).
2. **ErrorBoundary menghapus key yang salah**: tombol "Reset session" menghapus `readomni_app_session_v1`, padahal sejak ADR-118 key-nya `readomni_app_session_v1_<workspace>`.
3. **Test suite tidak portabel**: di Linux tanpa internet, baseline `468bfd9` menghasilkan 340 lulus / 36 gagal. Dengan `pytest-asyncio` terpasang tetap 13 gagal (12 butuh DNS sungguhan, 1 tes path drive khusus Windows); dengan fixture DNS tetapi tanpa `pytest-asyncio`, 32 gagal.
4. **PIN Ghost Mode hanya penyamar UI**: workspace dipilih dari header `X-Workspace` atau cookie yang tidak ditandatangani, sementara backend berjalan di `0.0.0.0`. Pemilik proyek memutuskan **tidak** memperbaikinya dan hanya mendokumentasikannya.

---

## Decisions

### 1. Workspace eksplisit di scraper metadata
- `MetadataScraperEngine.scrape()` / `scrape_candidates()` menerima `workspace`. `_get_adapter()` membuat `NovalpieAdapter(workspace=ws)` per panggilan (dari `workspace` atau `get_db_workspace(db_session)`). Kedua route meneruskan `workspace=get_db_workspace(db)`.
- Engine tetap jatuh ke adapter bersama bila dipanggil tanpa `workspace` **dan** tanpa `db_session` (tidak ada konteks request).
- Tes: `backend/tests/test_services/test_scraper_engine_workspace.py`, termasuk tes level perilaku untuk route `/scrape_candidates`.

### 2. Reset session sesuai ADR-118
- `ErrorBoundary.tsx` menghapus `getWorkspaceStorageKey('readomni_app_session_v1')` dan key lama.

### 3. Test suite hermetik & portabel
- `pytest-asyncio>=0.23.0` ditambahkan ke `backend/requirements.txt` (disetujui pengguna).
- Fixture autouse di `backend/tests/conftest.py`:
  - `hermetic_dns`: hostname dipetakan ke IP publik tetap; IP literal dan `localhost` tetap memakai resolusi asli. Tes SSRF yang mem-patch `socket.getaddrinfo` sendiri tetap menang.
  - `no_external_network` (council kedua): `socket.connect`/`connect_ex` Python ke alamat IP non-loopback melempar error dan variabel proxy dibuang. Ini menutup httpx/asyncio/`http.client`, tetapi **bukan** penjaga mutlak: libcurl di dalam `curl_cffi`, browser Playwright, dan `connect` dengan hostname (bukan IP) tidak melewati penjaga ini. Tanpa ini, tes yang mock HTTP-nya meleset diam-diam keluar ke internet; council menemukan `test_thread_cache_images_workflow` mem-patch target yang salah (`services.image_cacher…` padahal router mengimpornya langsung) dan benar-benar menghubungi host luar. Patch target diperbaiki ke `routers.images.run_thread_image_caching_job` dan tes kini memastikan mock-nya dipanggil.
  - `isolated_adaptive_store` (council kedua): `AdaptiveDOM` menyimpan signature ke `backend/data/adaptive_selectors.json` yang dilacak git; dua file tes menulis ulang file itu setiap pytest dijalankan (perubahan seperti ini sempat ikut ter-commit). Fixture mengalihkannya ke file sementara per tes dan mengosongkan cache memori.
- Route `/images/{path}` menolak path berawalan huruf drive (`C:/…`) di semua OS (403); pertahanan utamanya tetap `Path.resolve()` + `is_relative_to()`.
- Hasil: **392/392** tes lulus di Linux tanpa internet.

### 4. PIN Ghost didokumentasikan sebagai batasan
- `docs/ghost-mode-security.md` + catatan di README (bagian Privacy): model ancaman, batasan terkait (PIN di `localStorage`, cookie 30 hari, file AdaptiveDOM bersama, cookie Novalpie global), dan arah perbaikan bila kelak diperlukan.

### 5. Verifikasi dengan council independen + judge
Untuk perubahan dengan risiko regresi lintas lapisan, verifikasi tidak hanya mengandalkan penulis kode:
1. **Council**: reviewer independen tanpa konteks percakapan, masing-masing dengan satu lensa.
2. **Bukti empiris**: setiap temuan diberi label REPRODUCED (skrip + output) atau STATIC-ONLY.
3. **Judge**: agent terpisah memverifikasi ulang setiap temuan langsung ke kode, menjalankan ulang repro untuk temuan High/Medium, lalu memutuskan FIX-NOW / DOCUMENT / DROP beserta perbaikan minimal.
4. Perbaikan dibuktikan dengan tes yang sebelumnya gagal (backend) atau cek E2E perilaku (frontend).

**Putaran pertama** (2026-10-16): 4 reviewer + 2 judge; menghasilkan perbaikan awal Pocket Offline Cache (ADR-124).

**Putaran kedua** (2026-10-17): 5 reviewer (correctness, security/tenancy, UX mobile-desktop, test skeptic, pemeriksa fakta ADR) + 1 judge, terhadap seluruh `git diff 468bfd9` dan draf dokumen. Putusan FIX-NOW yang dikerjakan:

| Grup | Temuan | Perbaikan |
| --- | --- | --- |
| G1 (High) | Cache offline bisa menulis lintas workspace saat tab lain berpindah (direproduksi dua arah) | Workspace dikunci per tab + reload lintas tab (ADR-124 §3) |
| G2 (High, HP) | Tombol "Aa" tak terjangkau dan BOTH/RE-TRANSLATE terpotong di 320–390 px | Toolbar reader dibuat muat |
| G3 (Medium) | Toast error palsu saat server lambat; salinan sessionStorage tertutup spinner; buka-dingin offline menampilkan tombol Translate mati; error HTTP menampilkan teks bab lain; tidak ada pemulihan | ADR-124 §4 |
| G4 (Medium) | Badge Offline palsu setelah pindah bab | `initialChapterId` lewat ref nilai mount |
| G5 (Medium) | Toast menutupi toolbar jempol dan tombol bottom sheet | Toast di atas saat membaca (offset 10.5rem, di bawah tiga baris kontrol) |
| G6 (Medium) | Overlay pengaturan: lebar penuh di desktop, tanpa Esc/klik luar, tanpa `role=dialog`, tombol ikon tanpa label, nilai ukuran font kontras ±1,2–1,65:1 | ADR-124 §6 |
| G7 (Medium) | "Clear Image Cache" terpotong di semua HP | Tombol berbagi baris dengan Refresh |
| G8 (Low) | Kontras teks destruktif, target sentuh 36 px, label simpan ambigu/meluap | ADR-124 §6 |
| G9 (Low) | Patch target tes salah; 3 mutan `track=0` lolos; istilah glosarium baru tetap terhapus sendiri lewat import/preset (ADR-122 mengklaim sudah beres); fallback kuota 50 vs 150 (ADR-123) | Tes + perbaikan backend (ADR-122, ADR-123) |
| G10 (docs) | 6 klaim salah dan sejumlah klaim berlebihan di ADR-119–125 dan dokumen terkait | Dokumen dikoreksi |

**Juri akhir** (independen, memeriksa seluruh perbaikan): semua grup terselesaikan, dengan tiga regresi kecil dari putaran ini yang lalu diperbaiki dan diverifikasi ulang dengan skrip juri:
- Toast pada offset 7rem menutupi baris kontrol ketiga (ternyata ada tiga baris, bukan dua).
- Label "BAB 30 / 30" meluber ke tombol bookmark di 320 px.
- Esc di textarea Style Guide menutup panel dan membuang teks yang belum disimpan.
Ditambah satu perbaikan kecil yang ia tandai "document": retry offline dibatasi satu yang sedang berjalan.

Selama verifikasi, dua kesalahan pada perbaikan putaran ini sendiri juga tertangkap oleh E2E dan diperbaiki:
- Ref `initialChapterId` yang ikut tersinkron ke prop membuat buka-dingin selalu jatuh ke daftar bab (diganti nilai saat mount; 12/12).
- Rekomendasi warna rose-700 untuk tema omni ternyata salah karena omni bertema gelap; kini rose-300 (7,14:1).
- Selain itu ditemukan tes yang menulis `adaptive_selectors.json` (lihat §3).

---

## Consequences

### Positive
- Invariant workspace CLAUDE.md terpenuhi di jalur scraper metadata dan di penyimpanan klien, termasuk dengan banyak tab.
- Test suite bisa dijalankan di mesin mana pun tanpa internet, menolak koneksi jaringan keluar dari klien HTTP Python dalam tes, dan tidak lagi mengotori file yang dilacak git.
- Proses council + judge + bukti empiris menangkap regresi UI dan bug logika yang lolos dari typecheck, lint, dan pytest, termasuk kesalahan pada perbaikan dan rekomendasi juri sendiri.

### Negative / Residual Risks
- "Zero bug" tidak dapat dibuktikan secara mutlak. Yang dapat dinyatakan: setelah dua putaran council + judge, semua temuan FIX-NOW sudah diperbaiki dan diverifikasi; sisanya tercatat sebagai risiko di ADR terkait.
- Verifikasi frontend dijalankan agent; skrip E2E-nya tidak ada di repo (repo belum punya runner E2E frontend).
- Ditemukan dan **didokumentasikan, belum diperbaiki** (di luar lingkup atau butuh keputusan/migrasi):
  - ~~SSRF lewat hop redirect di Tier 1b/Tier 3 (ADR-120)~~ dan ~~API key terkirim ke URL pilihan klien (ADR-122)~~: ditutup di ADR-126, bersama SSRF reflektif lama di adapter Novel Updates.
  - Kolom `auto_extracted` fantom (ADR-123).
  - Cookie Novalpie global dan file AdaptiveDOM yang dibagi kedua workspace (`docs/ghost-mode-security.md`, ADR-120).
  - Pemanggil non-stream kehilangan sinyal terpotong (ADR-121).
  - Celah kecil cache offline (ADR-124).
  - `mask_secret` menampilkan 4+4 karakter PIN panjang.
- `last_used_at` bercampur zona waktu: route lorebook memakai `datetime.now()` lokal (mengikuti kode lama), preset memakai `func.now()`, ContextEngine memakai UTC. Di UTC+7, istilah buatan manual/import terlihat ±7 jam "lebih baru" dalam urutan eviction.
- Berpindah workspace me-reload tab lain walau tab itu sedang punya isian belum disimpan atau stream terjemahan berjalan.
- Masalah tes yang sudah ada sebelumnya:
  - `test_graceful_cancellation` meninggalkan batch aktif sehingga `test_sequential_processing_transition` menggantung bila dijalankan sesudahnya. Urutan default lulus, dan tidak ada timeout per tes.
  - `TestClient(app)` menjalankan startup asli (`init_db`) terhadap `./app.db` di direktori kerja, jadi jalankan pytest dari root repo, bukan dari `backend/`.
- Utang aksesibilitas global yang belum disentuh:
  - Ring fokus `ring-ring/50` kurang dari 3:1 di tema white.
  - Tombol dialog konfirmasi 36 px, dan tombol konfirmasinya putih di atas red-500 (3,8:1).
  - Toggle HIDE di pengaturan reader 3,2:1.
