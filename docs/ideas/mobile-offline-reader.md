# Idea: Mobile-First Reader & Pocket Offline Cache

## Problem Statement
Bagaimana kita membuat ReadOmni AI nyaman dibaca di layar HP (satu tangan) dan memungkinkan pembaca menyimpan bab ke memori HP agar tetap bisa dinikmati saat laptop mati atau di luar jangkauan Wi-Fi, tanpa terbentur restriksi HTTPS browser mobile?

---

## Executive Summary & Council Verdict
Berdasarkan telaah multi-perspektif (/ecc:council), pendekatan PWA tradisional (Service Worker, Web App Manifest, Screen WakeLock) terbentur **aturan keamanan browser (Secure Context)**: mobile Chrome dan iOS Safari secara mutlak memblokir Service Worker dan WakeLock pada koneksi HTTP LAN biasa (`http://192.168.x.x:5173`).

Oleh karena itu, arah pengembangan disesuaikan menjadi **"The Pragmatic Mobile Reader"**: fokus pada ergonomi sentuh murni (swipe, bottom thumb-bar, tema OLED) dan penyimpanan offline berbasis `IndexedDB` client-side yang tidak memerlukan sertifikat SSL khusus.

---

## Recommended Direction

### 1. Mobile Touch Ergonomics (Fase 1 - Prioritas Utama)
- **Horizontal Swipe Gestures:** Geser layar kiri/kanan untuk berpindah antar bab (menggunakan touch listener dengan threshold ambang batas agar tidak bertabrakan dengan vertical scroll).
- **Bottom Thumb Navigation Bar:** Tombol navigasi bab (Prev, Next, TOC, Tema, Settings) diposisikan di zona jangkauan jempol bawah (bukan di pojok atas layar).
- **Target Sentuh Ergonomis:** Semua tombol interaktif di HP memiliki hit-target minimal 44x44px.
- **Tema OLED True Black:** Palet warna hitam pekat (`#000000`) untuk menghemat konsumsi baterai pada layar AMOLED mobile saat membaca di ruangan gelap.

### 2. Pocket Offline Cache (Fase 2 - Penyimpanan Bab di HP)
- **One-Click Offline Cache:** Tombol *"Simpan Offline (20 Bab ke Depan)"* di antarmuka reader.
- **IndexedDB Storage:** Teks bab terjemahan dan gambar/ilustrasi di-cache langsung di penyimpanan browser HP menggunakan pustaka ringan (`idb`).
- **Offline Indicator:** Saat HP terputus dari Wi-Fi laptop, reader menampilkan badge *"Mode Offline"* dan membaca bab langsung dari IndexedDB tanpa menampilkan layar error `ERR_CONNECTION_REFUSED`.

---

## Key Assumptions & Validations
- [ ] **Touch Gesture Friction:** Swipe horizontal tidak boleh mengganggu kenyamanan pengguna saat memilih teks (*text selection*) atau men-scroll vertikal. *(Validasi: uji threshold `Math.abs(deltaX) > Math.abs(deltaY) * 2`)*.
- [ ] **Kapasitas Penyimpanan IndexedDB Mobile:** Memastikan browser mobile tidak membersihkan cache bab saat membuka tab lain. *(Teks 50 bab novel hanya ~1.5 MB, sangat aman di bawah batas kuota)*.
- [ ] **Perilaku Tanpa HTTPS:** Memastikan seluruh antarmuka IndexedDB dan touch gesture berfungsi 100% normal pada origin `http://<IP-LAN>:5173`.

---

## MVP Scope
1. **Touch Navigation:** Swipe kiri untuk bab berikutnya, swipe kanan untuk bab sebelumnya (dengan opsi toggle aktif/nonaktif di pengaturan reader).
2. **Bottom Floating Action Bar:** Toolbar ringkas di bawah reader mobile untuk pindah bab, buka daftar isi (TOC drawer), dan atur ukuran font.
3. **OLED Theme Preset:** Menambahkan opsi tema `OLED` ke dalam pilihan tema reader.
4. **Offline Chapter Store:** Service utilitas di frontend (`src/lib/offlineStorage.ts`) untuk menyimpan dan memanggil bab dari IndexedDB.

---

## Not Doing (and Why)
- **Service Worker PWA Offline Fallback:** Ditiadakan karena browser mobile menolak mendaftarkan Service Worker pada alamat IP HTTP non-localhost tanpa instalasi sertifikat SSL custom (mkcert) di setiap HP.
- **Bi-Directional Database Sync:** Ditiadakan. Sinkronisasi multi-master antara IndexedDB HP dan SQLite laptop rawan split-brain; HP murni berfungsi sebagai *consumer/viewer*, sedangkan SQLite laptop tetap menjadi *single source of truth*.
- **Screen WakeLock API:** Ditiadakan untuk saat ini karena membutuhkan Secure Context (HTTPS) dan otomatis dilepas oleh OS setiap kali tab berganti fokus.

---

## Open Questions
- Apakah drawer daftar isi (TOC) mobile sebaiknya muncul dari bawah (*bottom-sheet*) atau dari samping (*side-drawer*) untuk kenyamanan satu tangan?
