import re
from dataclasses import dataclass


WORD_RE = re.compile(r"[A-Za-z0-9\u00C0-\u024F\u4E00-\u9FFF]+")
# Only truly suspicious characters — NOT #, %, $ (common in legitimate text)
SUSPICIOUS_CHAR_RE = re.compile(r"[①-⑳⑴-⑼⓪⒈-⒛@&]")
LATIN_RE = re.compile(r"[A-Za-z]")
CJK_RE = re.compile(r"[\u4E00-\u9FFF]")
PHRASE_LOOP_RE = re.compile(
    r"\b((?:[A-Za-z0-9À-ɏ']+\s+){1,9}[A-Za-z0-9À-ɏ']+)"
    r"(?:[\s,;—\-]+\1){3,}\b",
    re.IGNORECASE,
)


@dataclass
class RepetitionMatch:
    token: str
    count: int
    start_index: int
    end_index: int


class HallucinationDetector:
    @staticmethod
    def detect_repeated_words(text: str, threshold: int = 10) -> list[RepetitionMatch]:
        if not text:
            return []

        matches: list[RepetitionMatch] = []
        words = [(m.group(0), m.start(), m.end()) for m in WORD_RE.finditer(text)]
        if not words:
            return matches

        current_word = words[0][0].casefold()
        current_original = words[0][0]
        start_index = words[0][1]
        end_index = words[0][2]
        count = 1

        for word, word_start, word_end in words[1:]:
            normalized = word.casefold()
            if normalized == current_word:
                count += 1
                end_index = word_end
                continue

            if count >= threshold:
                matches.append(RepetitionMatch(current_original, count, start_index, end_index))

            current_word = normalized
            current_original = word
            start_index = word_start
            end_index = word_end
            count = 1

        if count >= threshold:
            matches.append(RepetitionMatch(current_original, count, start_index, end_index))

        return matches

    @staticmethod
    def detect_repeated_phrases(
        text: str,
        min_words: int = 2,
        max_words: int = 8,
        threshold: int = 4,
    ) -> list[RepetitionMatch]:
        """Detect consecutive multi-word N-gram phrase repetition loops."""
        if not text:
            return []

        matches: list[RepetitionMatch] = []
        pattern = re.compile(
            rf"\b((?:[A-Za-z0-9À-ɏ']+\s+){{{max(1, min_words - 1)},{max(1, max_words - 1)}}}[A-Za-z0-9À-ɏ']+)"
            rf"(?:[\s,;—\-]+\1){{{max(1, threshold - 1)},}}\b",
            re.IGNORECASE,
        )
        for m in pattern.finditer(text):
            phrase = m.group(1).strip()
            full_span = m.group(0)
            approx_count = max(threshold, len(re.findall(re.escape(phrase), full_span, flags=re.IGNORECASE)))
            matches.append(
                RepetitionMatch(
                    token=phrase,
                    count=approx_count,
                    start_index=m.start(),
                    end_index=m.end(),
                )
            )
        return matches

    @staticmethod
    def strip_word_soup_hallucinations(text: str) -> str:
        """
        Detect and strip associative dictionary dumps / word-soup hallucinations from translation output.
        (e.g., runaway LLM loops outputting endless space-separated vocabulary lists like
        'society civilization history era period age decade...' or 'unbone unmuscle untendon...').
        """
        if not text:
            return ""

        # Pattern for a block of space-separated words without sentence punctuation (20+ words in a row)
        word_stream_pattern = re.compile(
            r"(?:[A-Za-z0-9-]{2,}\s+){20,}[A-Za-z0-9-]{2,}",
            re.IGNORECASE
        )
        # Morphological prefix repetition pattern (e.g. 8+ 'un...' words in a row)
        un_pattern = re.compile(r"\b(un[a-z]{3,}\s+){8,}", re.IGNORECASE)

        cleaned_paras = []
        for para in re.split(r"\n\s*\n", text):
            para_strip = para.strip()
            if not para_strip:
                continue

            # Check if the paragraph contains a word-soup stream
            match = word_stream_pattern.search(para_strip)
            if match:
                start_idx = match.start()
                if start_idx < 60:
                    # Paragraph is overwhelmingly word soup -> discard
                    continue
                else:
                    # Word soup starts mid-paragraph -> truncate paragraph before the soup
                    valid_prefix = para_strip[:start_idx].strip()
                    if len(valid_prefix) > 20:
                        cleaned_paras.append(valid_prefix)
                    continue

            # Check morphological repetition pattern
            match_un = un_pattern.search(para_strip)
            if match_un:
                if match_un.start() < 60:
                    continue
                else:
                    valid_prefix = para_strip[:match_un.start()].strip()
                    if len(valid_prefix) > 20:
                        cleaned_paras.append(valid_prefix)
                    continue

            cleaned_paras.append(para_strip)

        result = "\n\n".join(cleaned_paras).strip()
        return result

    @staticmethod
    def strip_garbled_hallucination_lines(text: str) -> str:
        if not text:
            return ""

        cleaned_lines: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                cleaned_lines.append(line)
                continue

            # CONSERVATIVE: only strip lines that are CLEARLY garbage
            # Must be short, mostly symbols, and have no real words
            if len(stripped) > 80:
                cleaned_lines.append(line)
                continue

            # If line has any Latin or CJK words, it's probably legitimate
            has_real_words = bool(LATIN_RE.search(stripped)) or bool(CJK_RE.search(stripped))
            if has_real_words:
                cleaned_lines.append(line)
                continue

            tokens = stripped.split()
            suspicious_tokens = sum(1 for token in tokens if HallucinationDetector._is_suspicious_token(token))
            suspicious_ratio = suspicious_tokens / max(len(tokens), 1)
            # Require 5+ suspicious tokens AND 50%+ ratio (very conservative)
            if suspicious_tokens >= 5 and suspicious_ratio >= 0.50:
                continue

            cleaned_lines.append(line)

        cleaned = "\n".join(cleaned_lines)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    @staticmethod
    def strip_phrase_repetition_loops(text: str) -> str:
        """Collapse runaway multi-word phrase/clause repetition loops (4+ repeats of 2-10 words)."""
        if not text:
            return ""
        collapsed = text
        for _ in range(3):
            next_val = PHRASE_LOOP_RE.sub(r"\1", collapsed)
            if next_val == collapsed:
                break
            collapsed = next_val
        return collapsed

    @staticmethod
    def strip_repetitive_character_loops(text: str) -> str:
        """
        Collapse degenerate repetitive character runs (e.g. 50+ '□', '■', '•', or identical tokens)
        caused by model decoder loops / token degeneration.
        """
        if not text:
            return ""

        # 1. Collapse runaway placeholder symbols (e.g. 4+ '□', '■', '•', or Unicode square boxes) to max 3
        collapsed = re.sub(r"([□■•\ufffd\u25a0-\u25ff])\1{3,}", r"\1\1\1", text)

        # 2. Collapse extreme runs of any non-alphanumeric symbol (8+ identical chars) to max 3
        collapsed = re.sub(r"([^\s\w\u4e00-\u9fff])\1{7,}", r"\1\1\1", collapsed)

        # 3. Collapse runaway repetitive identical words (e.g. 8+ 'the the the ...')
        collapsed = re.sub(r"\b(\w+)(?:\s+\1){7,}\b", r"\1 \1 \1", collapsed, flags=re.IGNORECASE)

        collapsed = HallucinationDetector.strip_phrase_repetition_loops(collapsed)
        return collapsed


    @staticmethod
    def summarize_text_audit(text: str, threshold: int = 10) -> dict:
        word_matches = HallucinationDetector.detect_repeated_words(text, threshold=threshold)
        phrase_matches = HallucinationDetector.detect_repeated_phrases(text, threshold=4)
        matches = word_matches + phrase_matches
        return {
            "has_repetition": bool(matches),
            "repetition_matches": [
                {
                    "token": match.token,
                    "count": match.count,
                    "start_index": match.start_index,
                    "end_index": match.end_index,
                    "snippet": text[max(0, match.start_index - 40):min(len(text), match.end_index + 40)],
                }
                for match in matches
            ],
        }

    @staticmethod
    def _is_suspicious_token(token: str) -> bool:
        if not token:
            return False

        suspicious_chars = len(SUSPICIOUS_CHAR_RE.findall(token))
        if len(token) == 1:
            return suspicious_chars >= 1

        has_latin = bool(LATIN_RE.search(token))
        has_cjk = bool(CJK_RE.search(token))
        has_mixed_scripts = has_latin and has_cjk
        has_symbol_noise = suspicious_chars >= 1 and bool(re.search(r"[A-Za-z0-9\u4E00-\u9FFF]", token))
        has_dense_punct = len(re.findall(r"[^A-Za-z0-9\u00C0-\u024F\u4E00-\u9FFF]", token)) >= 1

        return has_mixed_scripts or (has_symbol_noise and has_dense_punct)
