# ADR-124: Pocket Offline Cache — Mobile Reading Without a Reachable Server

## Status
Accepted (fitur di commit `c670ccb`; perbaikan dari dua putaran council + judge ada di commit yang menambahkan ADR ini, 2026-10-17)

## Date
2026-10-16

## Context
`docs/ideas/mobile-offline-reader.md` (fase 2) meminta agar pembaca di HP tetap bisa membaca bab saat laptop/server tidak terjangkau: laptop tidur, keluar dari Wi-Fi rumah, atau backend mati. Fase 1 dokumen itu baru **sebagian** terwujud: ergonomi sentuh dan toolbar jempol sudah ada (ADR-096), tetapi swipe horizontal antar bab belum diimplementasikan.

Batasan yang mengikat desain:

1. **Tanpa HTTPS di LAN**: aplikasi diakses lewat `http://<IP-LAN>`. Service Worker dan `navigator.storage` hanya tersedia di *secure context*, sehingga PWA offline penuh tidak bisa dipakai tanpa sertifikat di setiap HP.
2. **Tanpa dependensi baru** (CLAUDE.md): pustaka seperti `idb` tidak boleh ditambahkan tanpa persetujuan.
3. **Isolasi workspace** (CLAUDE.md invariant #3): data `main` dan `ghost` tidak boleh bercampur di penyimpanan klien.
4. **`GET /api/threads/{t}/chapters/{c}` tidak read-only**: endpoint ini memindahkan `UserBookmark` (posisi baca) dan, bila prefetch aktif, mengantrekan terjemahan latar. Mengunduh 50 bab lewat endpoint ini akan melompatkan posisi baca dan bisa memakan kuota LLM.

---

## Decisions

### 1. Penyimpanan: IndexedDB mentah, satu database per workspace (`src/lib/offlineStorage.ts`)
- Nama DB: `getWorkspaceStorageKey("readomni_offline_v1")`, yaitu `readomni_offline_v1_main` / `readomni_offline_v1_ghost`.
- Store `chapters` (key `${threadId}_${chapterId}`, index `threadId`) dan `threads` (snapshot daftar bab agar daftar isi tetap tampil saat offline).
- Hanya bab dengan `has_translation` yang dipilih (`selectChaptersToCache`). Respons tanpa terjemahan yang bisa dipakai (kosong atau `processing`) tidak disimpan dan tidak boleh menimpa salinan yang bagus.
- `navigator.storage.persist()` diminta bila tersedia (hanya di HTTPS/localhost). Simpan massal berhenti saat `QuotaExceededError`.

### 2. Unduhan tanpa efek samping: `?track=0` (`backend/routers/threads.py`)
- `get_chapter(..., track: bool = True)`. Dengan `track=0`, bookmark tidak dipindah atau dibuat, `scroll_progress` hanya dilaporkan untuk bab yang memang di-bookmark, dan tidak ada prefetch/terjemahan yang diantrekan. Scraping on-demand untuk bab tanpa teks asli tetap berjalan (docstring); cache offline tidak memicunya karena hanya mengambil bab terjemahan.
- Pemanasan bab N±1 di reader juga memakai `track=0`. Ini sekaligus memperbaiki bug lama: posisi baca di server bisa melompat ke bab tetangga.
- Tes: `backend/tests/test_routers/test_chapter_peek.py` (termasuk tiga tes yang membunuh mutan yang lolos dari tes awal).

### 3. Workspace dikunci per tab (`src/lib/api.ts`)
- `localStorage` dipakai bersama oleh semua tab. Versi awal membaca workspace aktif ulang pada setiap panggilan, sehingga saat tab lain berpindah workspace, tab ini masih menampilkan data workspace lama sementara request dan tulisan IndexedDB-nya pindah ke workspace baru. Council mereproduksi teks bab ghost menimpa cache main (dan sebaliknya).
- Keputusan: `getActiveWorkspace()` mengembalikan workspace yang dibaca **sekali saat halaman dimuat** (`TAB_WORKSPACE`). Alur pindah workspace (Sidebar, Settings) menulis key lalu reload, jadi perilakunya tidak berubah.
- Listener `storage` (plus `pageshow` dan `visibilitychange` untuk tab HP yang dibekukan) me-reload tab lain saat `readomni_workspace` berubah, setelah `clearWorkspaceSessionCache()`.
- `cacheChaptersAhead()` memakai workspace tab tersebut secara eksplisit untuk header `X-Workspace` dan nama DB.

### 4. Kapan reader memakai salinan offline (`src/pages/ReaderPage.tsx`)
- **Gagal jaringan** (`fetch` melempar error) atau status proxy **502/503/504** (proxy Vite mengembalikan 502 saat backend mati) → pakai salinan offline. Error HTTP lain (404, 500) berasal dari backend yang hidup: reader menampilkan "Gagal memuat bab (HTTP n)" dan kembali ke bab yang masih tampil, sehingga teks bab lain tidak pernah muncul di bawah nomor bab yang salah.
- **Jaringan menggantung**: bila belum ada jawaban dalam 5 detik (`OFFLINE_FALLBACK_DELAY_MS`), salinan offline ditampilkan tanpa membatalkan request; jawaban server yang datang kemudian menggantikannya. Bila hanya ada salinan sessionStorage, salinan itu dimunculkan dari balik spinner. Bila tidak ada salinan sama sekali, muncul toast **informatif** (bukan error): "Server lambat — masih memuat bab…", atau "Bab ini belum disimpan…" khusus untuk novel yang memang memakai cache offline. Toast ini ditutup begitu request selesai.
- **Bab belum disimpan saat offline**: toast "Bab ini belum disimpan untuk dibaca offline" dan reader kembali ke bab sebelumnya; bila tidak ada (buka-dingin), reader menampilkan daftar bab, bukan layar "NO TRANSLATION YET" dengan tombol yang tidak berfungsi.
- **Pemulihan**: selama mode offline, event `online`, `focus`, dan `visibilitychange` memicu `fetchThread` ulang. Tanpa interval, dan paling banyak satu retry yang sedang berjalan (`offlineRetryInFlightRef`), karena `focus` dan `visibilitychange` muncul bersamaan setiap kali kembali ke tab.
- **Snapshot thread** hanya dipakai bila belum ada data thread live di layar, supaya polling yang sekadar lambat tidak mengubah reader menjadi "offline".
- `initialChapterId` dibaca lewat ref yang **hanya menyimpan nilai saat mount**. Sebelumnya prop ini (yang diisi App dari bab aktif) menjadi dependensi `fetchThread`, sehingga setiap pindah bab memuat ulang thread, me-reset penjaga data live, dan memunculkan badge Offline palsu. Menyinkronkan ref ke prop juga keliru: ReaderPage melaporkan `null` ke App sesaat setelah mount sehingga restorasi bab hilang. Dengan nilai saat mount, buka-dingin mendarat di bab yang diminta 12/12 kali (sebelumnya sekitar 10/12).
- Penjaga race: `activeRequestIdRef` untuk bab; `threadRequestIdRef`/`threadSuccessIdRef` untuk thread.
- Status: badge **Offline** di header (kontras ≥ 4,5:1 di semua tema; baris jumlah bab disembunyikan di layar < 360 px) dan toast satu kali saat masuk mode offline.

### 5. Kesegaran & ID yang dipakai ulang
- Saat online, salinan bab yang sudah tersimpan diperbarui (`refreshOfflineChapterIfCached`), begitu juga snapshot thread (`refreshOfflineThreadIfCached`).
- SQLite tidak memakai AUTOINCREMENT, sehingga ID novel bisa dipakai ulang setelah dihapus. Identitas novel dicek lewat `created_at` (tidak berubah saat rename, "Translate titles", atau scrape metadata): bila berbeda dari data live, cache novel itu dibuang. Judul sengaja tidak dipakai karena rename yang sah akan menghapus cache. Menghapus novel dari Library juga menghapus cache offline-nya di perangkat tersebut, hanya bila DELETE di server berhasil.

### 6. UI (`src/components/OfflineCachePanel.tsx`, pengaturan reader, Settings)
- **Pengaturan reader**: pilihan 10/20/50 bab (`aria-pressed`, tinggi 44 px di HP), tombol **Simpan N bab mulai Bab X** (menjadi **Perbarui … (sudah tersimpan)** bila semua target sudah ada; label bisa terbungkus; progres diumumkan via `aria-live`), dan **Hapus cache novel ini** (dengan konfirmasi).
- **Halaman Settings**: jumlah bab, novel, dan ukuran tersimpan, plus **Hapus Semua Cache Offline**.
- Teks tombol destruktif memakai `DESTRUCTIVE_TEXT` (`src/lib/utils.ts`): rose-700 di tema terang (sepia, white), rose-300 di omni (biru tua), rose-400 di tema hampir hitam. Rasio terukur 5,35–7,34:1.
- Overlay pengaturan reader: `role="dialog"`, fokus pindah ke panel saat dibuka, Esc menutup (kecuali dialog konfirmasi sedang terbuka), klik di luar menutup popover desktop, bottom sheet dibatasi `max-w-2xl` di layar lebar, `85dvh`, dan padding `safe-area-inset-bottom`.
- Toast saat membaca muncul di atas dengan offset 10.5rem, di bawah **tiga** baris kontrol (header halaman 4rem + navigasi reader 3.5rem + header panel terjemahan 2.5rem), sehingga tidak menutupi toolbar jempol bawah, tombol bottom sheet, maupun kontrol atas (terverifikasi 320–1920 px).
- Toolbar atas reader muat di 320 px: tombol "Daftar Isi" disembunyikan di bawah `sm` (label "BAB n / N" membuka drawer yang sama; bagian "/ N" disembunyikan di bawah 360 px agar tidak menabrak bintang bookmark), grup kiri boleh menyusut, tombol "Aa" ikon saja di HP. Tombol ikon diberi `aria-label`.
- Esc di dalam kolom isian (mis. textarea Style Guide) hanya keluar dari kolom tersebut; Esc kedua baru menutup panel, agar teks yang belum disimpan tidak hilang.

---

## Verification
- **Backend**: 392 tes pytest lulus tanpa jaringan.
- **Frontend**: `tsc -b --noEmit` dan `eslint .` bersih.
- **E2E Playwright** (dijalankan agent terhadap dev server; skripnya **tidak** ada di repo karena repo belum punya runner E2E frontend dan menambahkannya butuh persetujuan dependensi):
  - 8 cek perilaku offline: isolasi workspace, respons live yang telat menggantikan salinan offline, navigasi cepat saat menggantung, buka-dingin tanpa badai request, klasifikasi 5xx, pemulihan, `processing` tidak menimpa cache, server mati di tengah unduhan.
  - 7 cek per perbaikan: reload lintas tab tanpa kebocoran, pemulihan via `online`/`focus`, salinan sessionStorage saat menggantung, toast tidak menutupi kontrol (320 & 390 px), toolbar muat di 320/360/390 px, overlay desktop & keyboard, Settings di HP + kontras 6 tema.
  - Repro asli reviewer: tidak ada toast error palsu saat server lambat, tidak ada badge Offline palsu setelah pindah bab, error HTTP tetap di bab sebelumnya.

---

## Consequences

### Positive
- Bab yang sudah disimpan tetap terbaca saat server mati atau jaringan menggantung, tanpa layar error.
- Posisi baca dan kuota LLM tidak terganggu oleh unduhan massal.
- Isolasi main/ghost terjaga di penyimpanan HP, juga saat banyak tab terbuka.

### Negative / Residual Risks (diungkapkan secara sadar)
- **Tanpa Service Worker**: mode offline hanya bekerja selama tab aplikasi masih terbuka. Membuka aplikasi dari nol saat laptop mati tetap gagal, dan tab yang dibuang browser ikut kehilangan akses offline.
- **Penyimpanan tidak persisten di HTTP**: `persist()` tidak tersedia di origin non-HTTPS; browser (terutama Safari) bisa menghapus cache saat ruang menipis.
- **Gambar ilustrasi belum ikut disimpan**: bab bergambar menampilkan gambar rusak saat offline.
- **Salinan per bab tidak dicek identitasnya**: salinan offline bertahan setelah bab dihapus, terjemahannya dihapus, atau di-reset "Fix Truncated"; ID bab yang dipakai ulang dalam novel yang sama bisa menampilkan teks lama. Tidak ada pemeriksaan judul/urutan saat membaca dari cache.
- **Statistik di Settings** memakai `getAll()` sehingga semua isi bab dimuat hanya untuk menghitung ukuran; dengan ratusan bab di HP, membuka Settings bisa terasa berat. Cache juga tidak punya batas total.
- **Celah kecil lain**: `selectedChapterIdx` dari snapshot bisa bergeser bila daftar bab live berbeda; `refresh*IfCached` membaca lalu menulis di transaksi terpisah sehingga "Hapus cache" yang jatuh di antaranya bisa terbatalkan; status `busy` panel bersifat per instance, jadi membuka ulang overlay saat menyimpan bisa memulai unduhan kedua.
- **Effect bab bergantung pada `thread`**: setiap polling thread membatalkan dan mengirim ulang request bab yang lambat, sehingga fallback 5 detik bisa tertunda (pre-existing; berkurang setelah perbaikan `initialChapterId`).
- **Reload lintas tab**: berpindah workspace di satu tab me-reload tab lain; input yang belum disimpan di tab lain ikut hilang (konsisten dengan perilaku tab yang berpindah).
- Header (dan badge Offline-nya) hanya terlihat saat kontrol reader sedang ditampilkan; dalam mode baca imersif, indikator yang terlihat hanya toast satu kali.
- **Server yang lambat tetapi sehat** (> 5 detik) tetap memunculkan badge/toast Offline untuk bab yang tersimpan, sampai respons live menggantikannya. Ini konsekuensi sengaja dari fallback 5 detik.
- **Buka-dingin pada jaringan menggantung** butuh ±11 detik sebelum teks tersimpan tampil (timer thread 5 detik, lalu timer bab 5 detik). Perbaikan yang disarankan: langsung coba salinan bab begitu snapshot thread dipakai.
- Handler pemulihan layar (pre-existing) tetap memanggil `fetchThread` pada setiap `focus`/`visibilitychange` selama isi bab belum tampil, sehingga pada alamat LAN yang menggantung beberapa request tambahan bisa menumpuk saat pengguna bolak-balik tab.
- Buka-dingin offline pada bab yang tidak tersimpan dan tanpa bab sebelumnya membiarkan bab gagal itu tetap terpilih di sesi; pembukaan offline berikutnya mencobanya lagi dan memunculkan toast yang sama.
- Fokus tidak kembali ke tombol gear setelah overlay pengaturan ditutup.
