# Configuration & Multi-Device Setup

## 1. Backend Setup (Host)
Agar aplikasi dapat diakses dari HP (iPhone/Android) di jaringan WiFi yang sama, jalankan backend dengan perintah:

```powershell
# Di folder backend
py -m uvicorn main:app --reload --port 8000 --host 0.0.0.0
```

## 2. Frontend Access
Akses aplikasi melalui browser di HP menggunakan IP lokal laptop Anda:
- Contoh: `http://192.168.31.95:5173`

## 3. Persistent Settings
Pengaturan berikut sekarang tersinkronisasi secara otomatis di seluruh perangkat:
- **Swappable AI Translation Model (ADR-029)**: Pilihan provider terjemahan yang dinamis:
  - **LM Studio (Local)**: Terjemahan offline gratis menggunakan model LLM lokal Anda di komputer (default).
  - **OpenAI (Cloud)**: Akses cloud berbayar ke OpenAI API (GPT-4o, GPT-4o-mini).
  - **Google Gemini**: Akses Gemini API gratis/premium dengan kecepatan sangat tinggi dan gratis tier personal melimpah dari Google AI Studio.
- **API Keys & Model custom**: API Key dan Model untuk OpenAI & Gemini tersimpan secara aman di database server dan disinkronkan ke seluruh klien.
- **Target Language**: Bahasa tujuan (Indonesian/English).
- **Advanced Prefetch**: 
  - **Toggle**: Mengaktifkan/menonaktifkan translasi otomatis bab selanjutnya.
  - **Range (1-5 Ch)**: Mengatur seberapa banyak bab yang akan diterjemahkan di latar belakang secara otomatis.

## 4. Troubleshooting
Jika HP tidak bisa konek:
1. Pastikan HP dan Laptop di WiFi yang sama.
2. Cek apakah Firewall Windows memblokir port 5173 (Vite) atau 8000 (FastAPI).
3. Pastikan backend berjalan dengan `--host 0.0.0.0`.
4. Cek `backend/main.py` apakah `allow_origins` sudah diset ke `["*"]`.
