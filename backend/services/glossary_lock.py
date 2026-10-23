import re
from typing import List, Set, Tuple, Any
from dataclasses import dataclass

try:
    import pypinyin
    from pypinyin import lazy_pinyin, Style
    HAS_PYPINYIN = True
except ImportError:
    HAS_PYPINYIN = False

CHINESE_CHAR_PATTERN = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")
EAST_ASIAN_CHAR_PATTERN = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff\uac00-\ud7a3\u1100-\u11ff\u3130-\u318f\u3040-\u309f\u30a0-\u30ff]")

# Stopword rentan yang sering bertabrakan dengan pinyin pendek (<= 3 huruf) atau pinyin 1 suku kata
COMMON_COLLISION_STOPWORDS = {
    # Indonesian
    "dan", "di", "ke", "ia", "si", "itu", "ini", "ada", "tak", "ya", "ha",
    "ah", "eh", "oh", "apa", "dia", "mau", "kan", "gua", "lu", "luo", "ba",
    "ma", "ta", "na", "ga", "dong", "sih", "yang", "uang", "tiang", "siang", "liar",
    # English
    "he", "an", "at", "in", "on", "to", "or", "no", "is", "it", "so", "by",
    "as", "if", "be", "we", "us", "am", "do", "go", "me", "my",
    "song", "fang", "long", "wang", "tang", "gang", "ring", "king", "wing", "hang", "bang"
}

PROTECTED_SPAN_RE = re.compile(
    r"(!\[[^\]]*\]\([^)]+\)|(?<!\!)\[[^\]]+\]\(https?://[^)]+\)|<[^>]+>|https?://[^\s)\"'>]+|❖(?:IMAGE|GAMBAR)_\d+❖)",
    re.IGNORECASE,
)

@dataclass
class GlossaryLockRule:
    pattern: re.Pattern
    replacement: str
    source_term: str
    is_case_sensitive: bool

    @property
    def length(self) -> int:
        return len(self.source_term)


_ALIAS_LINE_RE = re.compile(
    r"^(?P<head>[ \t]*(?:alias|aka|also known as|nama lain|variasi)[ \t]*:[ \t]*)(?P<body>[^\n\r]*)$",
    re.IGNORECASE | re.MULTILINE,
)


def append_replaced_alias(notes: str | None, old_term: str | None, new_term: str | None) -> str | None:
    """
    Catat terjemahan lama sebagai alias di catatan entri saat terjemahannya diubah, supaya
    'Sync to Chapters' ikut menulis ulang ejaan lama (termasuk koreksi huruf besar-kecil).
    """
    old = (old_term or "").strip()
    new = (new_term or "").strip()
    if not old or old == new or CHINESE_CHAR_PATTERN.search(old) or "," in old or "." in old:
        return notes

    notes = notes or ""
    match = _ALIAS_LINE_RE.search(notes)
    if match:
        existing = [a.strip() for a in match.group("body").split(",") if a.strip()]
        if old in existing:
            return notes
        merged = match.group("head") + ", ".join(existing + [old])
        return notes[:match.start()] + merged + notes[match.end():]

    return f"{notes}\nAlias: {old}" if notes else f"Alias: {old}"


def extract_pinyin_aliases(raw_term: str) -> List[str]:
    """
    Mengekstrak alias Pinyin dari sebuah istilah, termasuk penanganan pemisah slash (/),
    format gabung (Luoyi), dan format spasi kapital (Luo Yi).
    """
    if not raw_term:
        return []

    aliases: Set[str] = set()

    # Ekstrak tanda kurung terlebih dahulu sebelum split slash (e.g. 罗毅 (Luo Yi / Luoyi))
    for inside_paren in re.findall(r"\(([^)]+)\)", raw_term):
        for part in inside_paren.split("/"):
            clean_cand = part.strip(" \t\n\r*•-“”\"'")
            if clean_cand and not CHINESE_CHAR_PATTERN.search(clean_cand) and len(clean_cand) >= 2:
                aliases.add(clean_cand)

    clean_term_base = re.sub(r"\([^)]*\)", "", raw_term).strip()

    # Pisahkan jika ada subterm dengan slash (e.g. 夏茵 / 夏恩)
    subterms = [st.strip(" \t\n\r*•-“”\"'") for st in clean_term_base.split("/") if st.strip(" \t\n\r*•-“”\"'")]
    if not subterms and clean_term_base:
        subterms = [clean_term_base]

    for term in subterms:
        clean_term = term

        if not clean_term:
            continue

        # Jika mengandung Hanzi dan pypinyin tersedia
        if CHINESE_CHAR_PATTERN.search(clean_term) and HAS_PYPINYIN:
            try:
                pinyin_syllables = lazy_pinyin(clean_term, style=Style.NORMAL)
                if pinyin_syllables:
                    # Format spaced title: "Luo Yi"
                    spaced_title = " ".join(s.capitalize() for s in pinyin_syllables)
                    # Format combined title: "Luoyi"
                    combined_title = "".join(s.capitalize() for s in pinyin_syllables)
                    # Format lowercase: "luo yi"
                    spaced_lower = " ".join(pinyin_syllables)
                    combined_lower = "".join(pinyin_syllables)

                    aliases.add(spaced_title)
                    aliases.add(combined_title)
                    aliases.add(spaced_lower)
                    aliases.add(combined_lower)
            except Exception:
                pass
        else:
            # Istilah alfabetis biasa
            aliases.add(clean_term)

    return [a for a in aliases if a.strip()]


def build_glossary_lock_rules(entries: List[Any]) -> List[GlossaryLockRule]:
    """
    Menyusun aturan regex penggantian istilah dari daftar entri Lorebook.
    Aturan diurutkan berdasarkan panjang karakter sumber secara descending untuk
    mencegah masalah substring (e.g. 'Luo Yi Chen' diganti sebelum 'Luo Yi').
    """
    raw_rules: List[GlossaryLockRule] = []

    for entry in entries:
        orig = getattr(entry, "original_term", "")
        trans = getattr(entry, "translated_term", "")
        if not orig or not trans:
            continue

        orig = orig.strip()
        trans = trans.strip()
        if not orig or not trans or orig == trans:
            continue

        # 1. Aturan untuk teks karakter asli (Hanzi / Hangul / Kana) dan variasi Pinyin suku kata fleksibel
        clean_orig_base = re.sub(r"\([^)]*\)", "", orig).strip()
        subterms = [st.strip(" \t\n\r*•-“”\"'") for st in clean_orig_base.split("/") if st.strip(" \t\n\r*•-“”\"'")]
        if not subterms and clean_orig_base:
            subterms = [clean_orig_base]
        for st in subterms:
            clean_st = st.strip()
            if clean_st and EAST_ASIAN_CHAR_PATTERN.search(clean_st):
                pattern = re.compile(re.escape(clean_st))
                raw_rules.append(GlossaryLockRule(
                    pattern=pattern,
                    replacement=trans,
                    source_term=clean_st,
                    is_case_sensitive=True
                ))

                # Syllable-flexible pattern untuk Pinyin Mandarin
                if CHINESE_CHAR_PATTERN.search(clean_st) and HAS_PYPINYIN:
                    try:
                        syllables = lazy_pinyin(clean_st, style=Style.NORMAL)
                        if len(syllables) >= 2:
                            escaped_s = [re.escape(s) for s in syllables]
                            # Cocokkan Lu Di Ya, Lu Diya, Ludiya, Lu-Diya, Ai'erte'er, dsb.
                            syll_regex = r"\s*['’\-]?\s*".join(escaped_s)
                            clitic_right_boundary = r"(?=(?:-?(?:nya|mu|ku))?\b)"
                            pat = re.compile(rf"\b{syll_regex}{clitic_right_boundary}", re.IGNORECASE)
                            raw_rules.append(GlossaryLockRule(
                                pattern=pat,
                                replacement=trans,
                                source_term=" ".join(s.capitalize() for s in syllables),
                                is_case_sensitive=False
                            ))
                        elif len(syllables) == 1:
                            syl = syllables[0]
                            # Semua pinyin 1 suku kata wajib case-sensitive untuk mencegah menimpa kata umum (e.g. song, long, fang)
                            pat = re.compile(rf"\b{re.escape(syl.capitalize())}\b")
                            is_cs = True
                            raw_rules.append(GlossaryLockRule(
                                pattern=pat,
                                replacement=trans,
                                source_term=syl.capitalize(),
                                is_case_sensitive=is_cs
                            ))
                    except Exception:
                        pass

        # 2. Aturan untuk alias Pinyin / Latin tambahan (dari term & catatan notes)
        aliases = set(extract_pinyin_aliases(orig))
        notes = getattr(entry, "notes", None)
        if notes:
            alias_match = re.search(r"(?:alias|aka|also known as|nama lain|alias names?|variasi)[:\s]+([^\n\r.]+)", notes, re.IGNORECASE)
            if alias_match:
                for candidate in alias_match.group(1).split(","):
                    clean_cand = candidate.strip(" \t\n\r*•-“”\"'/")
                    if clean_cand and len(clean_cand) >= 2 and not CHINESE_CHAR_PATTERN.search(clean_cand):
                        aliases.add(clean_cand)

        for alias in aliases:
            if not alias or alias == trans:
                continue

            alias_lower = alias.lower()
            is_multiword = (" " in alias) or (len(alias) >= 4 and any(c.isupper() for c in alias[1:]))

            # Clitic boundary untuk alias multi-kata atau alfabetis >= 4 karakter yang bukan stopword
            if (is_multiword or len(alias) >= 4) and alias_lower not in COMMON_COLLISION_STOPWORDS:
                clitic_boundary = r"(?=(?:-?(?:nya|mu|ku))?\b)"
            else:
                clitic_boundary = r"\b"

            # Guardrail kata pendek, pinyin 1 suku kata, & stopword (selalu case-sensitive)
            if not is_multiword or alias_lower in COMMON_COLLISION_STOPWORDS:
                escaped = re.escape(alias.capitalize())
                pattern = re.compile(rf"\b{escaped}{clitic_boundary}")
                is_case_sensitive = True
            else:
                parts = alias.split()
                if len(parts) > 1:
                    escaped_parts = [re.escape(p) for p in parts]
                    flexible_pattern = r"\s+".join(escaped_parts)
                    pattern = re.compile(rf"\b{flexible_pattern}{clitic_boundary}", re.IGNORECASE)
                else:
                    escaped = re.escape(alias)
                    pattern = re.compile(rf"\b{escaped}{clitic_boundary}", re.IGNORECASE)
                is_case_sensitive = False

            raw_rules.append(GlossaryLockRule(
                pattern=pattern,
                replacement=trans,
                source_term=alias,
                is_case_sensitive=is_case_sensitive
            ))

    # Urutkan berdasarkan panjang source_term (DESCENDING) agar frasa panjang diproses dulu
    raw_rules.sort(key=lambda r: r.length, reverse=True)

    # Dedup aturan dengan pattern yang identik
    unique_rules: List[GlossaryLockRule] = []
    seen_patterns: Set[str] = set()
    for rule in raw_rules:
        norm_pat = rule.pattern.pattern.lower() if (rule.pattern.flags & re.IGNORECASE) else rule.pattern.pattern
        pat_key = f"{norm_pat}_{rule.pattern.flags}_{rule.replacement}"
        if pat_key not in seen_patterns:
            seen_patterns.add(pat_key)
            unique_rules.append(rule)

    return unique_rules


def apply_glossary_lock(text: str, rules: List[GlossaryLockRule]) -> str:
    """
    Menjalankan substitusi regex secara deterministik dan non-overlapping pada teks hasil terjemahan.
    Mencegah cascading replacement (efek domino berulang) dan menjaga idempotensi jika istilah
    sudah berada dalam bentuk terjemahan target.
    """
    if not text or not rules:
        return text

    occupied_spans: List[Tuple[int, int]] = []

    # 0. Lindungi span gambar Markdown, link Markdown, tag HTML, dan URL
    for m in PROTECTED_SPAN_RE.finditer(text):
        occupied_spans.append(m.span())

    # 1. Lindungi kemunculan istilah target yang sudah ada di teks (idempotensi mutlak)
    unique_replacements = {r.replacement for r in rules if r.replacement}
    for repl in unique_replacements:
        pattern_str = re.escape(repl)
        if repl[0].isalnum():
            pattern_str = r"\b" + pattern_str
        if repl[-1].isalnum():
            pattern_str = pattern_str + r"(?=(?:-?(?:nya|mu|ku))?\b)"

        # Case-sensitive: varian huruf besar-kecil lain dari target boleh ditulis ulang oleh aturan alias
        flags = 0

        try:
            for m in re.finditer(pattern_str, text, flags=flags):
                occupied_spans.append(m.span())
        except Exception:
            pass

    # 2. Ambil kecocokan non-overlapping berdasarkan prioritas urutan rules
    accepted_replacements: List[Tuple[int, int, str]] = []

    for rule in rules:
        for m in rule.pattern.finditer(text):
            start, end = m.span()
            overlap = False
            for o_start, o_end in occupied_spans:
                if not (end <= o_start or start >= o_end):
                    overlap = True
                    break
            if not overlap:
                occupied_spans.append((start, end))
                accepted_replacements.append((start, end, rule.replacement))

    if not accepted_replacements:
        return text

    # 3. Urutkan penggantian berdasarkan posisi awal karakter
    accepted_replacements.sort(key=lambda x: x[0])

    # 4. Bangun teks baru secara single-pass (literal string insertion, bebas cascading)
    pieces: List[str] = []
    last_idx = 0
    for start, end, repl in accepted_replacements:
        pieces.append(text[last_idx:start])
        pieces.append(repl)
        last_idx = end
    pieces.append(text[last_idx:])

    return "".join(pieces)
