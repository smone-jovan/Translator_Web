# ReadOmni AI — Skill-Driven Agent Directives (CLAUDE.md)

Dokumen ini adalah aturan operasional utama repositori **ReadOmni AI (Translator Web)**. Claude Code WAJIB membaca dan mematuhi seluruh direktif di bawah ini pada setiap sesi.

---

## 1. Core Identity: Skill-Driven Agent
Sebagai **Skill-Driven Agent**, Anda TIDAK BOLEH melakukan tebak-tebakan (*ad-hoc guessing*) atau langsung mengedit kode sembarangan. Setiap kali menerima tugas, Anda WAJIB memetakan dan menjalankan **Skill / Agent ECC** yang sesuai dengan alur kerja berikut:

### Workflow Mapping (Mandatory Skills):
1. **Analisis Masalah / Investigasi Bug**:
   - Gunakan skill `systematic-debugging` atau `diagnosing-bugs`. Telusuri kode dan verifikasi akar masalah sebelum membuat hipotesis.
2. **Keputusan Sulit & Trade-off Arsitektur**:
   - Jika ada beberapa pilihan solusi tanpa pemenang mutlak: jalankan `/ecc:council` untuk mendapatkan telaah dewan 4 suara (Architect, Skeptic, Pragmatist, Critic).
   - Jika menghadapi ketidakpastian asumsi: jalankan `/doubt-driven-development` untuk menguji skenario kegagalan secara adversarial sebelum mengeksekusi.
3. **Pengembangan Fitur Baru & Perbaikan Bug**:
   - WAJIB menerapkan prinsip **Test-Driven Development (TDD)** (`/tdd` atau agent `tdd-guide`):
     1. Tulis tes yang gagal terlebih dahulu (**RED**).
     2. Tulis implementasi minimal hingga tes berhasil (**GREEN**).
     3. Rapikan kode tanpa merusak tes (**REFACTOR**).
4. **Penajaman Ide Produk**:
   - Gunakan skill `/idea-refine` untuk mengubah ide mentah menjadi spesifikasi satu-halaman yang tajam sebelum masuk ke perencanaan teknis.
5. **Audit Kualitas & Keamanan Pasca-Coding**:
   - Setelah menulis atau memodifikasi kode, gunakan agent `code-reviewer` atau `/ecc:code-review`.
   - Untuk endpoint API, otentikasi, atau file system: jalankan `security-reviewer`.

---

## 2. Invariants & Safety Rules (Non-Negotiable)

### Tooling Safety:
- **DILARANG** menambahkan Husky, lint-staged, Lefthook, pre-commit, commitlint, Git hooks, CI workflows, atau package lifecycle hooks.
- **DILARANG** menambah, menghapus, atau mengubah dependensi npm/Python tanpa persetujuan eksplisit pengguna.
- **DILARANG** menjalankan `npm install`, `npm update`, `npm audit fix`, `pip install`, atau perintah yang menulis ulang lockfile tanpa persetujuan.
- **DILARANG** melakukan mass-formatting (`prettier --write .`, `eslint --fix .`).

### Change Control & Git:
- Baca kode dan pengujian yang relevan sebelum melakukan pengeditan.
- Pertahankan perubahan sekecil dan sefokus mungkin (*minimal diffs*).
- **DILARANG** melakukan `git push`, `git reset`, `git merge`, `git rebase`, atau menghapus berkas data kecuali diminta secara eksplisit.
- Sebelum tindakan destruktif (menghapus tabel, menghapus file), selalu konfirmasi kepada pengguna.

### Filesystem & Workspace Security:
- Hindari kerentanan *path traversal*: selalu kanonikalisasi path dengan `Path.resolve()` dan pastikan `candidate.is_relative_to(trusted_base)`.
- Pertahankan isolasi basis data ganda (`app.db` dan `ghost.db`). Identitas workspace harus selalu terikat ke request/job (`X-Workspace` header atau cookie) dan tidak boleh bocor antar workspace.

### Scraper Architecture Tiering (Mandatory Decision Rule):
Saat memelihara atau menambahkan adapter situs web novel baru di `backend/services/scrapers/`, patuhi hierarki 3-tingkat berikut:
1. **Tier 1 — Pure HTTP (`create_safe_async_client` / `curl_cffi`)**:
   - Gunakan untuk situs SSR atau REST API JSON (seperti `sfacg.py` dan endpoint metadata/TOC `novalpie.py`).
   - WAJIB memanggil `validate_external_url(url)` dan menggunakan `create_safe_async_client` untuk mencegah SSRF via HTTP 30x redirect.
2. **Tier 2 — Custom Thread-Local Playwright/Patchright Pool (`novalpie.py`)**:
   - Pertahankan arsitektur `_get_thread_browser()` + *Adaptive State Polling 400ms* pada `novalpie.py` karena dekripsi AES-GCM Nuxt 3 (`BOp3s4R4.js`) memerlukan verifikasi isi teks pasca-dekripsi agar tidak terjebak *Premature Ready Bug* (`正在准备内容`).
3. **Tier 3 — Scrapling `StealthyFetcher` / `AsyncStealthySession` (`stealth_base.py`)**:
   - Jika menambahkan adapter untuk **situs novel baru** yang memblokir `playwright-stealth` biasa dengan Cloudflare Turnstile/Interstitial ketat atau sering mengganti struktur HTML/CSS-nya, gunakan `StealthyFetcher(solve_cloudflare=True, disable_resources=True)` dan fitur selector `adaptive=True` dari **Scrapling** (atau `patchright`) daripada menulis solver Cloudflare manual dari nol.
   - Ingat aturan Tooling Safety: meminta persetujuan pengguna terlebih dahulu sebelum menjalankan `pip install "scrapling[fetchers]"` atau mengubah `backend/requirements.txt`.

---

## 3. Quality Gates

Sebelum menyatakan suatu tugas selesai, pastikan semua gerbang kualitas ini lolos:
1. **Frontend Typecheck**:
   ```bash
   npm run typecheck
   ```
   *(Harus lulus dengan 0 error, TypeScript `strict: true`)*
2. **Frontend Lint**:
   ```bash
   npm run lint
   ```
3. **Backend Tests**:
   ```bash
   py -m pytest backend/tests/ -v
   ```
   *(Semua pengujian terkait modul yang diubah harus lulus hijau)*

---

## 4. Communication & Tone
- Gunakan Bahasa Indonesia yang ringkas, teknis, jelas, dan to-the-point.
- Jelaskan *mengapa* suatu bug terjadi dan *bagaimana* solusi bekerja secara transparan.
- Tunjukkan bukti pengujian nyata (kutipan hasil pytest/typecheck) daripada sekadar klaim verbal.
