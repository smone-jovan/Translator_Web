import re
from dataclasses import dataclass


WORD_RE = re.compile(r"[A-Za-z0-9\u00C0-\u024F\u4E00-\u9FFF]+")
SUSPICIOUS_CHAR_RE = re.compile(r"[①-⑳⑴-⑼⓪⒈-⒛#%$@&]")
LATIN_RE = re.compile(r"[A-Za-z]")
CJK_RE = re.compile(r"[\u4E00-\u9FFF]")


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
    def strip_garbled_hallucination_lines(text: str) -> str:
        if not text:
            return ""

        cleaned_lines: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                cleaned_lines.append(line)
                continue

            tokens = stripped.split()
            suspicious_tokens = sum(1 for token in tokens if HallucinationDetector._is_suspicious_token(token))
            suspicious_ratio = suspicious_tokens / max(len(tokens), 1)
            if suspicious_tokens >= 3 and suspicious_ratio >= 0.35 and len(stripped) <= 160:
                continue

            cleaned_lines.append(line)

        cleaned = "\n".join(cleaned_lines)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    @staticmethod
    def summarize_text_audit(text: str, threshold: int = 10) -> dict:
        matches = HallucinationDetector.detect_repeated_words(text, threshold=threshold)
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
