# Stealth Dual-Space Mode

## Problem Statement
Bagaimana kita bisa menciptakan ruang *database* kedua yang tersembunyi secara sempurna di dalam aplikasi (seperti kepribadian ganda) agar pengguna bisa menerjemahkan dan memamerkan novel kepada teman tanpa membocorkan perpustakaan novel utamanya yang memiliki genre sensitif/pribadi?

## Recommended Direction
**The "Global Workspace Switcher" (Mode Kepribadian Ganda).**
Alih-alih memfilter data (yang berisiko bocor), aplikasi akan memiliki tombol "Ganti Otak" rahasia. Saat Anda menahan tombol Profil selama 10 detik lalu memasukkan PIN (03697), *frontend* akan mengirimkan perintah global ke *backend* untuk menutup koneksi ke `app.db` dan membuka koneksi ke `ghost.db`. 
Untuk menyiasati masalah API Key (karena syaratnya API key tidak boleh terpisah), *backend* akan diinstruksikan untuk selalu melakukan *fallback* (mengambil salinan) tabel `Settings` dari `app.db` ke `ghost.db` saat terjadi perpindahan. Saat pindah ke *Ghost Space*, seluruh tugas latar belakang (seperti *batch translation*) dari *Main Space* akan **dihentikan paksa (killed)** agar tidak ada notifikasi hantu yang tiba-tiba muncul.

## Key Assumptions to Validate
- [ ] *Database Hot-Swapping:* FastAPI dan SQLAlchemy mampu melakukan perpindahan koneksi file SQLite secara dinamis saat aplikasi sedang menyala tanpa perlu *restart server*.
- [ ] *State Reset:* Mematikan paksa *Background Translator* saat berganti mode tidak akan merusak status terjemahan bab yang sedang berjalan (harus dipastikan aman).

## MVP Scope (Yang Akan Dikerjakan)
- Menambahkan logika *Long-Press* (10 detik) pada ikon/tombol *Profile* di *Sidebar*.
- Menambahkan modal *Pin Input* yang hanya terbuka setelah *long-press*.
- Membuat *endpoint* API rahasia `/api/system/switch_workspace` di *backend*.
- Membuat sistem *Hot-Swap* koneksi SQLite dari `app.db` ke `ghost.db`.
- Logika sinkronisasi otomatis satu arah untuk tabel `Settings` (membawa API Key dari Utama ke Ghost).
- Pembersihan memori (*clear state, cancel batch queue*) setiap kali ganti ruang.

## Not Doing (Yang TIDAK Akan Dikerjakan & Alasannya)
- **Multi-user UI login screen** — *Alasan:* Membuat aplikasi terlihat seperti layanan web biasa dan memancing teman Anda bertanya *"Loh, kamu punya akun lain ya?"*. Aplikasi harus terlihat seperti *single-user* bodoh.
- **Auto-Destruction / Timeout** — *Alasan:* Anda sudah memastikan pergantian mode dilakukan secara manual *sebelum* presentasi. Membuatnya kembali terkunci otomatis berisiko mengganggu Anda saat sedang membaca santai.
- **Enkripsi File Database** — *Alasan:* Teman Anda hanya melihat layar (UI), bukan membuka *folder* proyek di laptop Anda. Enkripsi SQLite hanya membuat aplikasi melambat tanpa manfaat keamanan yang relevan di skenario ini.
