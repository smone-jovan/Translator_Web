# ADR-127: Residual Risk Register & Remediation Priorities

## Status
Accepted (2026-10-17). Register-nya hidup di `docs/residual-risks.md`; butir-butirnya masih terbuka.

## Date
2026-10-17

## Context
Audit dan dua putaran council (ADR-125, ADR-126) menutup temuan FIX-NOW, tetapi menyisakan 37 risiko yang sudah diketahui. Risiko itu tersebar di bagian "Negative / Residual Risks" delapan ADR (ADR-119–126) dan `docs/ghost-mode-security.md`. Masalahnya:

1. **Tidak ada satu tempat untuk melihat status.** Butir yang sudah ditutup (mis. SSRF redirect, kebocoran API key) hanya dicoret di ADR asalnya; butir yang masih terbuka harus dicari satu per satu.
2. **Tidak ada prioritas.** Utang aksesibilitas kecil dan API tanpa autentikasi tercatat dengan bobot yang sama.
3. **Akar yang sama tidak terlihat.** Enam butir keamanan (PIN Ghost, `openai_url`, URL LM Studio, cookie workspace, `mask_secret`, header `X-Workspace`) semuanya berakar pada API tanpa autentikasi, sehingga memperbaikinya satu per satu akan boros.

Pemilik proyek memutuskan untuk **mendokumentasikan dulu** sisa risiko ini sebelum mengerjakannya.

---

## Decisions

### 1. Satu register risiko sisa: `docs/residual-risks.md`
- Setiap butir punya ID tetap (`R-01`, `R-02`, …), dampak, prioritas, ADR asal, status, dan arah perbaikan.
- Dikelompokkan per area: keamanan & privasi, data & kebenaran fungsional, Pocket Offline Cache, UX/aksesibilitas/multi-tab, pengujian & tooling.
- ADR asal tetap menyimpan detail teknis dan tidak ditulis ulang; register menjadi sumber **status** dan **prioritas**.

### 2. Skala prioritas
- **P1**: dampak keamanan/privasi atau kehilangan data.
- **P2**: perilaku salah yang terlihat pengguna, atau utang yang membuat bug berikutnya mudah muncul.
- **P3**: kosmetik, kenyamanan, atau batasan yang disengaja.

Status hanya **Terbuka** atau **Diterima** (batasan yang disengaja). Butir yang ditutup dihapus dari register dan dicatat di ADR yang menutupnya.

### 3. Urutan pengerjaan
1. **R-01, autentikasi API + token workspace bertanda tangan**, sebagai satu perubahan berikutnya. Ini menutup atau mengecilkan R-02..R-06 sekaligus. Perubahan ini menyentuh God Node `GlobalSetting`/`SessionLocal` dan sebagian menggantikan ADR-083, jadi wajib ADR sendiri.
2. **R-12** (jejak domain `ghost` di `adaptive_selectors.json`), **R-07** (DNS rebinding di Tier 1a/1b), dan **R-36** (review ulang egress proxy oleh reviewer lain).
3. Butir P2 kebenaran data dan perilaku yang terlihat pengguna: R-13..R-16, R-20, R-21, R-28.
4. Butir P3 dikerjakan bila perubahan lain menyentuh area yang sama.

### 4. Aturan pemeliharaan
- ADR baru yang meninggalkan risiko sisa **wajib** menambahkannya ke register dengan ID baru (ID tidak pernah dipakai ulang).
- Menutup butir mensyaratkan tes yang sebelumnya gagal (atau cek E2E untuk UI) dan rujukan ke ADR/commit penutupnya. Coretan di ADR asal diperbarui dengan rujukan itu.
- Menurunkan prioritas atau mengubah status menjadi **Diterima** harus disertai alasan di kolom "Arah perbaikan".

---

## Consequences

### Positive
- Status semua risiko yang diketahui terlihat di satu halaman, dengan akar bersama yang jelas (R-01).
- Pekerjaan berikutnya punya urutan yang bisa dipertanggungjawabkan, bukan berdasarkan temuan terbaru.
- Klaim "zero bug" digantikan daftar yang jujur dan bisa diaudit.

### Negative
- Register bisa basi bila aturan pemeliharaan (§4) tidak diikuti; ADR asal dan register harus diperbarui bersamaan.
- Prioritas ditetapkan dari model ancaman saat ini (aplikasi pribadi di LAN rumah). Bila aplikasi dibuka ke jaringan yang tidak dipercaya, sebagian P2/P3 keamanan (R-03, R-07, R-10) perlu dinaikkan.
