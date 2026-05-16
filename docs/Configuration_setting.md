# Configuration & Operations Guide

Panduan ini berisi instruksi cara menjalankan dan mengkonfigurasi **AI Translator Web** secara lokal menggunakan **LM Studio** sebagai engine terjemahan utama.

---

## 1. Menjalankan Backend (FastAPI)

Backend menangani scraping web, parsing EPUB, manajemen database, dan proxy streaming ke LM Studio.

1. Buka terminal baru dan masuk ke folder `backend`.
2. Aktifkan virtual environment (opsional tapi disarankan).
3. Install dependencies jika belum:
   ```bash
   pip install -r requirements.txt
   ```
4. Jalankan server menggunakan `uvicorn`:
   ```bash
   py -m uvicorn main:app --reload --port 8000
   ```
   *Atau jika menggunakan `python` biasa: `python -m uvicorn main:app --reload --port 8000`*

Backend akan berjalan di `http://localhost:8000`. Database `app.db` akan dibuat secara otomatis di dalam folder `backend/` pada startup pertama.

---

## 2. Menjalankan Frontend (React + Vite)

Frontend adalah antarmuka web (UI) untuk aplikasi ini.

1. Buka terminal baru dan masuk ke folder utama (root project).
2. Install dependencies node jika belum:
   ```bash
   npm install
   ```
3. Jalankan development server:
   ```bash
   npm run dev
   ```

Aplikasi web dapat diakses melalui browser di `http://localhost:5173`.

---

## 3. Konfigurasi LM Studio

Aplikasi ini sangat bergantung pada LM Studio untuk proses translasi berbasis AI lokal.

1. Download dan jalankan [LM Studio](https://lmstudio.ai).
2. Cari dan download model language yang cocok untuk terjemahan (Rekomendasi: `Qwen`, `Llama-3`, atau model `Gemma-2` berukuran 7B-14B parameter tergantung kapasitas RAM).
3. Buka tab **Local Server** (ikon panah dua arah di panel sebelah kiri).
4. Aktifkan server lokal dengan menekan tombol **Start Server**.
5. Pastikan:
   - Base URL berjalan di `http://localhost:1234/v1`
   - CORS diaktifkan (sudah default dari LM Studio).

---

## 4. Cara Penggunaan (Workflow)

Berikut adalah workflow ideal menggunakan aplikasi ini:

### A. Menggunakan Settings
Buka tab **Settings** di aplikasi web. 
- URL LM Studio harusnya sudah `http://localhost:1234/v1` secara default.
- Anda dapat melakukan klik "Test Connection" untuk memastikan LM Studio aktif.

### B. Membuat/Membuka Thread Baru
1. Masuk ke **Translate** tab.
2. Anda bisa menempelkan link novel web lalu klik **Extract**, ATAU
3. Upload file `.epub` dari lokal.
4. Teks akan diekstrak dan masuk ke panel kiri (Original). Jika ini EPUB, chapter 1 akan ditampilkan. Otomatis sebuah *Thread* (buku) baru akan dibuat di database.

### C. Menggunakan Lorebook (Glosarium)
Jika novel ini memiliki istilah spesifik (misal nama karakter, nama tempat, istilah kultivasi):
1. Buka tab **Context Library**.
2. Pilih thread (judul buku) yang baru saja anda tambahkan.
3. Klik **Add Term**, lalu masukkan istilah asli dan terjemahannya (Contoh: "仙侠" -> "Xianxia").
4. Sistem otomatis akan *"inject"* glossary ini sebagai system prompt ke LM Studio setiap kali anda melakukan translasi untuk buku tersebut!

### D. Proses Translasi
1. Kembali ke tab **Translate**.
2. Pastikan teks *Original* sudah terisi.
3. Klik **Translate**. 
4. Teks akan diterjemahkan secara *streaming* langsung dari LM Studio ke layar anda (layaknya ChatGPT).

---

## Troubleshooting

- **"⚠️ Streaming failed or endpoint unreachable."**
  - Pastikan Backend FastAPI menyala di port 8000.
  - Pastikan LM Studio Local Server menyala di port 1234.
- **Warna UI tidak sesuai dengan ReadOmni.**
  - Pastikan anda tidak menimpa file `src/index.css`. Desain tokens sudah dikunci di file tersebut.
- **Buku tidak ter-parsing.**
  - Fitur parser EPUB menangani format standar. Beberapa EPUB DRM mungkin gagal di-parse. Gunakan EPUB open (tanpa DRM).
