# adr-012: manajemen glossary dan pipeline translasi yang kontekstual

## status
diterima

## konteks
Pas novelnya makin panjang, kualitas translasi AI mulai berantakan karena:
- Daftar istilah (glossary) makin numpuk, bikin token boros dan AI jadi bingung.
- AI sering pakai arti kamus umum padahal ini dunia novel fantasi (world-building hancur).
- Istilah baru yang dikasih AI di catatan sering kelupaan gak kesimpan ke database.
- Ada error "No running event loop" pas translasi jalan di background.

## keputusan
Kita bikin "Context Engine" khusus buat ngatur semua ini.

### detail teknis:
1. **optimasi glossary pakai ranking**:
   - Tiap istilah sekarang punya hitungan `usage_count` dan `last_used_at`.
   - Kita cuma ambil **50 istilah teratas** yang paling nyambung sama bab itu biar prompt-nya gak kepanjangan.
   - Ada sistem bersih-bersih otomatis: kalau satu judul novel punya lebih dari 100 istilah, kita hapus 20 yang paling jarang dipakai.
2. **suntik etika translasi**:
   - Kita paksa AI ikut 4 aturan wajib:
     - *Context over Dictionary*: Lihat konteks, jangan cuma liat kamus.
     - *Translate vs Transliterate*: Nama orang tetap, tapi jurus atau organisasi diterjemahin.
     - *World-Building*: Jangan tiba-tiba muncul nama lokasi dunia nyata (kayak Kyoto) kalau settingnya fantasi.
     - *Honorifics*: Jaga panggilan kayak "Kakak Senior" atau akhiran "-san".
3. **auto-save yang lebih fleksibel**:
   - Logika buat deteksi "Translator Notes" diperbaiki pakai regex yang lebih luwes biar gak gampang meleset.
4. **auto-migration database**:
   - Biar gak ribet tiap ada update, database sekarang otomatis nambahin kolom sendiri pas aplikasi dinyalain.

## konsekuensi
- **Hemat token**: Prompt jadi jauh lebih ringkas tapi tetap akurat.
- **Konsistensi terjaga**: AI sekarang lebih patuh sama istilah yang sudah kita tentukan.
- **Gak perlu maintenance manual**: Sistem sudah otomatis bersih-bersih istilah yang gak kepakai.
- **Lebih stabil**: Error event loop sudah hilang karena kita pindah ke `BackgroundTasks` bawaan FastAPI.
