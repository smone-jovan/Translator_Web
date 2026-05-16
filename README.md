# translator-web
> Baca novel web dan epub pakai AI lokal. Fokus ke privasi dan konsistensi istilah.

Aplikasi ini buat saya (dan mungkin kamu) yang suka baca novel terjemahan tapi mau kontrol penuh. Kita pakai **LM Studio** di laptop sendiri buat proses translasinya, jadi gak ada data yang bocor ke cloud.

---

## apa saja fiturnya?

### context engine yang gak asal-asalan
Beda sama translator biasa yang cuma lempar teks ke AI, sistem ini pakai cara yang lebih rapi:
- **Usage-based glossary**: Gak semua istilah dimasukkan ke prompt. Kita cuma ambil 50 istilah paling relevan yang muncul di bab tersebut biar AI gak bingung dan hemat token.
- **Aturan etika translasi**: Ada instruksi ketat buat jaga honorifik (kayak Senior Brother, -san, dsb) dan istilah dunia fantasi (biar Kyoto gak tiba-tiba jadi Ibu Kota kalau settingnya lagi di dunia lain).
- **Auto-save**: Kalau AI nemu istilah baru dan ngasih catatan di akhir bab, sistem bakal langsung simpan ke database.

### pengalaman baca yang "clean"
- **UI glassmorphism**: Tampilan transparan dan simpel. Enak dilihat lama-lama.
- **Flicker protection**: Gak ada layar putih kedip-kedip pas ganti bab.
- **Background processing**: AI bakal terus nerjemahin di belakang layar walaupun kamu tutup tab-nya.
- **Auto-prefetch**: Pas kamu lagi asik baca, bab selanjutnya sudah antre diterjemahin otomatis.

### ambil konten darimana saja
- **One-click scraper**: Paste link novelnya, nanti langsung jadi Markdown bersih tanpa iklan.
- **Epub support**: Upload file .epub, nanti sistem yang pecah jadi bab-bab di database.

---

## tech stack

Aplikasi ini pakai kombinasi teknologi yang saya rasa paling pas:

| bagian | teknologi |
|:---:|:---|
| **frontend** | React 19 + Vite |
| **styling** | TailwindCSS v4 |
| **backend** | Python 3.11 + FastAPI |
| **ai engine** | LM Studio (Local) |
| **database** | SQLite + SQLAlchemy |
| **parsing** | Crawl4AI + EbookLib |

---

## cara install

### persiapan
- Install **Node.js** v20 dan **Python** v3.11.
- Jalankan **[LM Studio](https://lmstudio.ai/)** (pastikan server lokalnya nyala di port 1234).

### 1. setup backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # atau venv\Scripts\activate di Windows
pip install -r requirements.txt
python main.py  # atau pakai uvicorn
```

### 2. setup frontend
```bash
npm install
npm run dev
```
Buka saja `http://localhost:5173`.

---

## dokumentasi lainnya

Kalau mau liat jeroannya:
- [Implementation plan](docs/implementation_plan.md): Rencana kerja dan fitur yang sudah ada.
- [Handoff guide](docs/Handoff.md): Status teknis buat yang mau ngulik kodenya.
- [Architectural decisions](docs/decisions/): Kenapa saya pakai cara ini, bukan cara itu.

---
*Dibuat biar baca novel jadi lebih enak.*
