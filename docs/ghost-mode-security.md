# Ghost Mode — Batasan Keamanan (Known Limitation)

Status: **diterima sebagai batasan yang disengaja** (2026-10-16). Tidak ada rencana perbaikan saat ini.

> Status dan prioritas batasan di halaman ini juga dilacak di `docs/residual-risks.md` (R-01, R-04..R-06, R-11, R-12, R-21; ADR-127).

## Ringkasan

PIN Ghost Mode adalah **penyamar tampilan (UI privacy)**, bukan kontrol akses. PIN mencegah orang yang meminjam perangkat Anda berpindah ke workspace `ghost` lewat antarmuka. PIN **tidak** melindungi isi `ghost.db` dari siapa pun yang bisa mengirim request HTTP langsung ke backend.

## Mengapa

- PIN hanya diperiksa di endpoint switch workspace (`POST /api/system/workspace` di `backend/routers/system.py`).
- Untuk semua request lain, `resolve_workspace()` (`backend/database.py`) memilih database dari header `X-Workspace` atau cookie `readomni_workspace`. Keduanya dikirim oleh klien dan tidak ditandatangani.
- Backend berjalan di `0.0.0.0` agar bisa diakses dari HP di jaringan lokal (`launcher.py`).

Akibatnya, perangkat lain di Wi-Fi yang sama bisa membaca data ghost tanpa PIN, misalnya:

```bash
curl -H "X-Workspace: ghost" http://<ip-komputer>:8000/api/threads
```

Batasan terkait:

- PIN bisa diganti lewat `POST /api/settings` tanpa memasukkan PIN lama.
- PIN default `03697` dipakai bila belum diubah.
- Tidak ada rate-limit untuk percobaan PIN.
- PIN disimpan sebagai teks biasa di SQLite (sudah dicatat di ADR-083).
- `GET /api/settings` menampilkan PIN dalam bentuk ter-mask (`mask_secret`); PIN yang lebih dari 8 karakter masih memperlihatkan 4 karakter pertama dan 4 terakhir.
- Cookie `readomni_workspace` di-set dengan `httponly=False` (sengaja, karena dibaca frontend), sehingga bisa dibaca atau diubah oleh skrip di halaman.
- Menghapus novel di server tidak menghapus salinan "Baca Offline" yang sudah tersimpan di HP lain.
- Cache "Baca Offline" di HP disimpan per workspace (`readomni_offline_v1_ghost`). Setelah kembali ke `main`, salinan ghost tetap ada di IndexedDB browser HP dan tidak terlihat dari panel workspace `main`; hapus dulu dari workspace `ghost` bila perlu.
- **PIN juga tersimpan polos di browser**: halaman Settings menyimpan PIN di `localStorage` (`ghost_pin`, `SettingsPage.tsx`) dan sesaat setelah diganti menampilkannya sebagai placeholder `Current PIN: …`. Orang yang meminjam perangkat dan membuka DevTools bisa membacanya.
- **Cookie workspace berumur 30 hari** (`max_age=2592000`): perangkat yang ditinggal dalam mode `ghost` akan langsung terbuka di `ghost` saat dibuka lagi dalam 30 hari.
- **Jejak domain ghost di file bersama**: `backend/data/adaptive_selectors.json` (AdaptiveDOM, ADR-120) satu file untuk kedua workspace dan dilacak git, sehingga domain yang di-scrape dari `ghost` ikut tercatat di sana.
- **Cookie Novalpie bersama**: cookie login Novalpie dibaca dari `backend/.env` global sebelum pengaturan per workspace (`novalpie.py`), sehingga scraping dari `ghost` memakai akun Novalpie yang sama dengan `main`.
- **Tab lain ikut berpindah** (sejak 2026-10-17, ADR-125): workspace setiap tab dikunci saat halaman dimuat, dan saat workspace diganti di satu tab, tab lain otomatis reload ke workspace baru. Tujuannya mencegah satu tab menampilkan data satu workspace sambil menulis ke workspace lain. Efek sampingnya: berpindah dari `ghost` ke `main` juga menutup tampilan ghost di tab lain.

## Model ancaman yang dicakup

| Skenario | Terlindungi? |
| --- | --- |
| Teman meminjam laptop/HP dan membuka aplikasi lewat browser | Ya |
| Orang lain di Wi-Fi yang sama mengirim request langsung ke port 8000 | Tidak |
| Seseorang membuka file `ghost.db` di disk | Tidak |

## Saran penggunaan

- Jalankan aplikasi hanya di jaringan yang Anda percaya (rumah), bukan Wi-Fi publik/kantor.
- Ganti PIN default di **Settings → Privacy & Security**.
- Bila perlu akses dari HP di jaringan yang tidak dipercaya, matikan akses LAN dan gunakan aplikasi hanya dari komputer sendiri.

## Jika suatu saat ingin diperketat

Arah perbaikan yang sudah dianalisis (belum dikerjakan):

1. Endpoint switch menerbitkan token HMAC `httponly`; `resolve_workspace()` hanya memakai `ghost` bila token valid.
2. Rate-limit percobaan PIN.
3. Penggantian PIN wajib menyertakan PIN lama.

Perubahan ini menyentuh God Node `GlobalSetting` dan `SessionLocal`, sehingga perlu ADR baru yang menggantikan sebagian ADR-083.
