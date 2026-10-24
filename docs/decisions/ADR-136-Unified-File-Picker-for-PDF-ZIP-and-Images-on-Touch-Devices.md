# ADR-136: Pemilih Berkas Terpadu untuk PDF, ZIP, dan Gambar (Termasuk di HP)

## Status
Accepted (2026-10-24). Diverifikasi dengan typecheck, lint, dan simulasi di browser bawaan (tampilan layar sentuh); setelah pemilih terpadu pengguna berhasil mengunggah ZIP dari HP (keluhan berikutnya berkaitan dengan batas jumlah gambar), tetapi belum ada uji sistematis di beberapa perangkat dan browser. Frontend belum punya infrastruktur tes otomatis.

## Context
- Browser HP (Chrome Android, iOS) tidak punya pemilih folder: input `webkitdirectory` turun menjadi pemilih berkas biasa. Satu bab manga di HP karenanya dikirim sebagai ZIP (ADR-133) atau banyak gambar sekaligus.
- Chrome di Android mengabu-abukan berkas yang tidak cocok dengan atribut `accept` pemilihnya. Versi pertama input ZIP memakai `accept=".zip,application/zip,..."` dan ZIP tetap tidak bisa dipilih di HP pengguna; pemilih PDF di panel pertama (`accept="application/pdf"`) tentu mengabu-abukan ZIP.
- Pemilih tanpa filter ada di panel kedua ("Terjemahkan folder gambar"), di luar layar pertama HP (±820 px dari atas) dan sebagian tertutup menu bawah, sehingga pengguna hanya melihat pemilih PDF. Bukti: log server tidak mencatat satu pun unggahan gambar dari HP, kode yang disajikan server dev sudah terbaru, dan simulasi layar sentuh menunjukkan kedua panel dengan pemilih yang benar.

## Decision
- **Satu pintu masuk di atas** (`PdfTranslatePanel`): satu input `multiple` **tanpa `accept`**. Pilihan diarahkan berdasarkan nama atau MIME: semua PDF memulai alur PDF (PDF pertama); tidak ada PDF memanggil `onOtherFiles`, yang meneruskan berkas ZIP atau gambar ke panel folder gambar; campuran PDF dan berkas lain ditolak dengan pesan.
- **Penerusan lewat handle imperatif** (bukan efek, bukan event global): `ImageFolderTranslatePanel` mengekspos `ImageFolderPanelHandle.start(files)` lewat `ref` sebagai prop dan `useImperativeHandle` (React 19); `TranslatePage` menyambungkannya. Panel menggulir dirinya ke layar saat mulai supaya progres terlihat.
- **Panel folder gambar**: di desktop tetap ada pemilih folder (`webkitdirectory`), pemilih ZIP tanpa `accept`, dan pemilih gambar (PNG/JPEG/WebP). Di perangkat layar sentuh (`pointer: coarse`) hanya ada satu input `multiple` tanpa filter untuk ZIP atau banyak gambar. ZIP dikenali dari nama `.zip` atau tipe yang memuat "zip"; apa pun yang dipilih di pemilih ZIP dianggap arsip dan diperiksa server lewat magic bytes.
- Baris "Dipilih: …" menampilkan apa yang sampai ke aplikasi, sehingga kegagalan pemilih berkas HP bisa dibedakan dari kegagalan unggah.
- Tidak ada perubahan server dan tidak ada penyimpanan di `localStorage`.

## Alternatives
- **Filter `accept` yang lebih lengkap untuk ZIP**: dicoba pertama dan gagal di HP pengguna; daftar MIME ZIP berbeda antar aplikasi file manager.
- **Dua panel terpisah saja** (tanpa pintu masuk terpadu): panel kedua terlewat karena di luar layar pertama.
- **Panel folder gambar dipindah ke atas**: masih dua pintu masuk dan tetap membingungkan untuk PDF.
- **Unzip di klien**: butuh paket npm baru dan boros memori HP; ditolak (ADR-133).
- **`CustomEvent`/event global untuk meneruskan berkas**: kopling tersembunyi dan sulit dilacak; ref imperatif lebih eksplisit.

## Consequences / Residual
- Tanpa `accept`, pemilih menampilkan semua berkas, sehingga tipe yang tidak didukung bisa terpilih; server menolaknya dengan pesan yang jelas (mis. "File is not a ZIP archive").
- Pengarahan berdasarkan nama/MIME adalah heuristik; berkas PDF tanpa ekstensi dan tanpa MIME akan dianggap gambar/ZIP dan ditolak server.
- `PdfTranslatePanel` kini bergantung pada `TranslatePage` untuk meneruskan berkas lain; judul panelnya berubah menjadi "Terjemahkan PDF, ZIP, atau gambar".
- Pengecekan `pointer: coarse` dibaca sekali saat panel dibuat; perangkat hibrida (layar sentuh + mouse) memakai mode yang terdeteksi saat itu.

## Files
`src/components/PdfTranslatePanel.tsx`, `src/components/ImageFolderTranslatePanel.tsx`, `src/pages/TranslatePage.tsx`, `src/lib/pdfTranslate.ts` (`findZipFile`, `sortImageFiles`). Komit terkait: `fa0f7f5`, `0290dbe`, `8659054`, `5e91178`, `5e66517`.
