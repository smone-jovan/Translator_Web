# Fidelity Health Center & 1-Click Auto-Repair

## Problem Statement
Bagaimana cara mempermudah pembaca menemukan, memahami, dan memperbaiki bab-bab yang mengalami gangguan kualitas terjemahan (terpotong, dialog hilang, ringkasan abnormal) tanpa harus memeriksa dan mengulang terjemahan satu per satu secara manual?

## Recommended Direction
Membangun **Fidelity Health Center** yang terintegrasi di kontrol daftar bab (`ChapterListControls.tsx`), pembaca (`ChapterReader.tsx`), dan **Bulk Repair Action** di backend:

1. **Filter Cepat "⚠️ Issues"**: Menambahkan opsi filter ketiga pada tab bab (`Semua` | `Diterjemahkan` | `⚠️ Perlu Perhatian (N)`).
2. **1-Click Bulk Repair**: Tombol *"Perbaiki Semua Bab Bermasalah"* yang mengirim bab ber-warning ke antrean `background_translator` dengan prioritas tinggi dan instruksi prompt anti-summarization.
3. **Interactive Warning Drawer/Modal**: Mengklik badge warning di Reader atau Grid membuka popup ringkas yang menampilkan:
   - Ringkasan statistik (Paragraf asli vs terjemahan, baris dialog, status penutup kalimat).
   - Tombol instan *"Terjemahkan Ulang Bab Ini"* atau *"Abaikan Peringatan (Tandai Beres)"*.

## Key Assumptions to Validate
- [ ] Menerjemahkan ulang bab ber-warning berhasil membersihkan >85% issue fidelity tanpa intervensi manual.
- [ ] Pengguna lebih menyukai tombol "Perbaiki Sekaligus" daripada mengklik perbaiki satu per satu di setiap bab.
- [ ] Pacing throttler yang sudah ada di `background_translator.py` cukup aman menahan lonjakan re-translate massal pada free-tier API.

## MVP Scope
- **[Backend]** Endpoint `GET /api/threads/{id}/fidelity-issues` untuk mengambil daftar bab yang memiliki `fidelity_warning IS NOT NULL`.
- **[Backend]** Endpoint `POST /api/threads/{id}/retranslate-flagged` untuk mereset status dan menjadwalkan ulang penerjemahan bab bermasalah ke antrean `background_translator`.
- **[Backend]** Endpoint `POST /api/threads/{id}/chapters/{chapter_id}/dismiss-fidelity` untuk mengosongkan flag peringatan jika pengguna merasa hasil terjemahan sudah cukup bagus.
- **[Frontend]** Filter pill `⚠️ Perlu Perhatian` pada `ChapterListControls.tsx`.
- **[Frontend]** Tombol aksi massal *"Perbaiki Bab Bermasalah"* dengan dialog konfirmasi estimasi waktu.
- **[Frontend]** Quick-action di banner Reader: tombol *"Terjemahkan Ulang Sekarang"* & *"Tandai Selesai / Abaikan"*.

## Not Doing (and Why)
- **Side-by-Side Word/Sentence NLP Alignment** — Kompleksitas tinggi dan membebani komputasi lokal, sementara manfaat bagi pembaca kasual rendah.
- **Multi-Model Fallback Matrix** — Belum otomatis berganti model AI saat gagal untuk mencegah tagihan tak terduga pada akun pengguna.
- **Auto-Delete Corrupted Chapters** — Bab yang bermasalah tidak akan dihapus otomatis dari database; terjemahan yang ada tetap bisa dibaca sampai hasil terjemahan perbaikan selesai di-generate.

## Open Questions
- Apakah perlu opsi checklist untuk memilih hanya bab tertentu yang ingin diperbaiki, atau langsung perbaiki semua sekaligus?
- Apakah saat re-translate otomatis, kita ingin menaikkan parameter `max_tokens` (untuk mencegah pemotongan kalimat)?
