# Ghost Mode — Batasan Keamanan (Known Limitation)

Status: **diterima sebagai batasan yang disengaja** (2026-10-16). Tidak ada rencana perbaikan saat ini.

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
- Cache "Baca Offline" di HP disimpan per workspace (`readomni_offline_v1_ghost`). Setelah kembali ke `main`, salinan ghost tetap ada di IndexedDB browser HP dan tidak terlihat dari panel workspace `main`; hapus dulu dari workspace `ghost` bila perlu.

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
