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
- **LM Studio URL**: Default `http://localhost:1234` (atau IP laptop jika diakses dari HP).
- **Active Model**: Model yang dipilih di Laptop akan otomatis terpilih di HP.
- **Target Language**: Bahasa tujuan (Indonesian/English).

## 4. Troubleshooting
Jika HP tidak bisa konek:
1. Pastikan HP dan Laptop di WiFi yang sama.
2. Cek apakah Firewall Windows memblokir port 5173 (Vite) atau 8000 (FastAPI).
3. Pastikan backend berjalan dengan `--host 0.0.0.0`.
4. Cek `backend/main.py` apakah `allow_origins` sudah diset ke `["*"]`.
