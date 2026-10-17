# ADR-119: Desktop Control Hub GUI & Zero-Console Launch

## Status
Accepted (diimplementasikan pada commit `2ed7989`, Issue #17; ADR ditulis retroaktif pada audit 2026-10-16)

## Date
2026-10-14

## Context
Aktivasi "sekali pencet" lewat `start_app.bat` / `launcher.py` masih berjalan di jendela Command Prompt:

1. **Jendela CMD menggantung** berisi log ANSI Uvicorn & Vite yang terus bergulir, sehingga aplikasi terasa seperti alat developer, bukan aplikasi desktop.
2. **Kontrol hanya lewat keyboard** (`[1]`–`[4]`, `[r]`, `[q]`) di terminal; tidak ada tombol klik, termasuk untuk menyalin URL Wi-Fi LAN yang dipakai di HP.
3. **Kedipan jendela CMD**: pemanggilan `subprocess` (`uvicorn`, `npm.cmd`, `netstat`, `taskkill`, `netsh`) tidak memakai `CREATE_NO_WINDOW`, sehingga jendela konsol sempat muncul saat aplikasi dijalankan tanpa konsol.

Mode CLI (`--cli`, `--no-browser`, `doctor`) dan tes `backend/tests/test_launcher.py` harus tetap berfungsi.

---

## Decisions

### 1. Zero-Console Launch
- `start_app.bat` tanpa argumen menjalankan `pythonw.exe launcher.py --gui --no-browser` (memprioritaskan `.venv\Scripts\pythonw.exe`) lalu langsung selesai, sehingga tidak ada jendela CMD tersisa.
- `hide_console_window()` (`launcher.py`) menyembunyikan konsol via Win32 `ShowWindow` bila `--gui` dijalankan dari `python.exe`.

### 2. Subprocess Tanpa Kedipan
- Helper `_win_creation_flags()` mengembalikan `subprocess.CREATE_NO_WINDOW` (`0x08000000`) di Windows dan `0` di OS lain; dipasang pada seluruh `subprocess.Popen` / `subprocess.run`.

### 3. Desktop Control Hub (`run_gui()`)
- Jendela `tkinter` (pustaka standar Python, **tanpa dependensi baru**) bertema gelap selaras UI web, dengan title bar gelap Windows 11 via `DwmSetWindowAttribute(hwnd, 20, …)`.
- Isi: kartu status real-time Backend `:8000` & Frontend `:5173`, kartu akses cepat (URL laptop & URL Wi-Fi LAN untuk HP + tombol salin), grid tombol aksi, serta laci **Live Logs** yang tersembunyi secara default.
- Log ditampilkan tanpa kode warna ANSI (`ANSI_ESCAPE_RE`) dari buffer terpisah `plain_log_buffer` (maks. 150 baris).

### 4. Kompatibilitas Mundur
- Argumen `--gui` dan `--cli` ditambahkan di `parse_args()`; seluruh fungsi CLI lama (`handle_key`, `log_buffer`, `get_service_status`, `run_doctor`, `--no-browser`) dipertahankan.
- Di Windows, GUI menjadi mode **default** walau tanpa `--gui` (`… or sys.platform == "win32"`); `--cli` dipakai untuk memaksa antarmuka terminal. Bila `tkinter` atau display tidak tersedia, launcher diam-diam jatuh ke mode CLI (`launcher.py`, `run_gui`).

---

## Consequences

### Positive
- Aplikasi tampil sebagai aplikasi desktop tanpa jendela terminal; URL untuk HP bisa disalin sekali klik.
- Tidak ada kedipan konsol dari subprocess di Windows.
- Nol dependensi baru (tkinter + ctypes bawaan).

### Negative / Trade-offs
- Fitur visual (title bar gelap, `CREATE_NO_WINDOW`, `pythonw.exe`) khusus Windows; OS lain memakai jalur CLI.
- Error saat startup tidak terlihat di konsol; pengguna perlu membuka laci Live Logs atau `launcher.log`.
