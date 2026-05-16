# ADR-004: Robust Local AI Connectivity Logic

## Status
Accepted

## Date
2026-05-16

## Context
Aplikasi ini berkomunikasi dengan LM Studio yang berjalan secara lokal di mesin user. Pada sistem operasi Windows, `localhost` sering kali beresolusi ke alamat IPv6 (`::1`), sedangkan banyak layanan lokal (seperti LM Studio) hanya mendengarkan pada alamat IPv4 (`127.0.0.1`). 

Hal ini menyebabkan kegagalan koneksi inter-proses (Backend Python ke LM Studio) meskipun browser (Frontend) tetap bisa terhubung secara normal karena browser memiliki mekanisme fallback otomatis.

## Decision
Mengimplementasikan dua lapis pertahanan untuk stabilitas AI:

1. **Dual-Stack Fallback (Connectivity)**: 
   - Backend akan secara otomatis mencoba `localhost` dan `127.0.0.1` secara bergantian jika salah satu gagal. 
   - Berlaku untuk layanan **Translation** dan **Context Extraction**.

2. **Plain-Text Fallback (Parsing)**:
   - Jika AI gagal memberikan JSON yang valid (sering terjadi pada model lokal kecil), sistem akan melakukan *manual parsing* terhadap teks biasa.
   - Sistem akan mencari pola seperti `Istilah: Penjelasan` atau list baris per baris untuk tetap mendapatkan data glossary meskipun format JSON rusak.

## Alternatives Considered

### Mewajibkan User menggunakan 127.0.0.1
- **Pros**: Sederhana secara kode.
- **Cons**: Mengurangi kenyamanan user karena harus mengubah setting manual. User awam lebih terbiasa dengan istilah `localhost`.

### Menggunakan library `dnspython` untuk resolusi DNS manual
- **Pros**: Sangat teknis dan akurat.
- **Cons**: Menambah dependensi eksternal dan overhead kompleksitas kode yang tidak sebanding untuk kasus penggunaan lokal sederhana.

## Consequences
- **Reliability**: Aplikasi menjadi jauh lebih stabil di berbagai konfigurasi jaringan Windows.
- **Performance**: Ada sedikit overhead (timeout) jika alamat pertama gagal, namun ini hanya terjadi sekali di awal percobaan yang gagal.
- **Maintainability**: Kode menjadi sedikit lebih panjang di bagian konektivitas, namun memberikan pesan error yang jauh lebih deskriptif (mencatat semua alamat yang dicoba).
