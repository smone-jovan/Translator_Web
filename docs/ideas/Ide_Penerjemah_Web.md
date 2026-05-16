# Ide Aplikasi Penerjemah Web & EPUB (Self-Hosted)

## Problem Statement
Butuh platform web self-hosted ramah seluler. Ekstrak web (scraping) & urai EPUB otomatis. Terjemah pakai LM Studio lokal. Simpan konteks/glosarium agar terjemahan konsisten. Tampilan UI/UX mirip ReadOmni.

## Fitur Inti
1.  **Ekstraksi Web (Scraping):** Input URL -> Ambil teks bersih -> Kirim ke LM Studio.
2.  **Manajemen EPUB:** Upload EPUB -> Pisah per bab otomatis.
3.  **Memori Konteks (Lorebook):** Simpan istilah/nama. Sisipkan ke prompt AI otomatis (contoh: "Terjemahkan X jadi Y").
4.  **UI/UX:** Sidebar menu (Translate, Context, Library). Kaca-kaca/Glassmorphism. Responsif HP.

## Stack Teknologi (Rekomendasi)
*   **Backend:** Python (FastAPI). Integrasi LLM lokal gampang.
*   **Frontend:** Next.js / Vue + TailwindCSS.
*   **Scraping Tools:**
    *   `Crawl4AI` (Python) -> Ubah web jadi Markdown bersih untuk AI.
    *   `Playwright` -> Jika web sumber berat JS.
*   **EPUB Parser:** `EbookLib` (Python) atau `epub-parser` (Node.js).
*   **Database:** SQLite / PostgreSQL (Simpan histori bab, glosarium).

## Variasi Ide
*   **Sistem RAG:** AI ingat plot 5 bab terakhir.
*   **Antrean Latar Belakang (Background Queue):** Paste 100 link -> scrape & terjemah semalaman -> jadi EPUB rapi.

## Status
Menunggu feedback user tentang sumber web spesifik & arsitektur server (Lokal vs Jaringan).
