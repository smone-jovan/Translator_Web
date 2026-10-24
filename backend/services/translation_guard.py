"""
Recognise vision-model replies that are not translations: refusals, descriptions of the picture,
degenerate loops and empty output. Pure functions over text; applied to image replies only, because
a small multimodal model asked to "translate the text in the image" will often describe or refuse
an image that has no readable text.

The heuristics are deliberately conservative: a real translation wrongly rejected costs more than a
description let through. Every pattern list is a named constant so it can be tuned in one place.
"""
import re
from dataclasses import dataclass
from typing import List, Optional, Pattern

MAX_REFUSAL_CHARS = 400
MIN_DESCRIPTION_VOCABULARY = 3
LOOP_MIN_LINE_CHARS = 8
LOOP_MIN_LINE_REPEATS = 4
LOOP_MIN_LINES_FOR_VARIETY = 8
LOOP_MAX_UNIQUE_RATIO = 0.4
LOOP_CHUNK_CHARS = 40
LOOP_CHUNK_STEP = 20
LOOP_CHUNK_REPEATS = 4
LOOP_CHUNK_MIN_DISTINCT_CHARS = 8
LOOP_SCAN_CHARS = 6000

_FLAGS = re.IGNORECASE


def _compile(patterns: List[str]) -> List[Pattern[str]]:
    return [re.compile(p, _FLAGS) for p in patterns]


# Phrases an assistant uses to decline; deliberately specific so "I can't believe it!" stays a translation.
REFUSAL_PATTERNS = _compile(
    [
        r"explicit (adult )?(sexual )?content",
        r"\b(may|might) not be (appropriate|suitable)",
        r"feel free to ask",
        r"\bi (cannot|can't|can not|am unable to|won't) (provide|assist|help|generate|translate|create|fulfil)",
        r"if you'?re looking for (a )?(translation|different|non-explicit)",
        r"please provide the specific text",
        r"tidak (dapat|bisa) (membantu|menerjemahkan|memberikan|menghasilkan)",
        r"maaf,? (saya )?tidak (dapat|bisa)",
        r"无法(翻译|提供|协助|处理|帮助)",
        r"抱歉",
        r"申し訳",
        r"翻訳(する)?(こと)?(は|が)できません",
    ]
)

DESCRIPTION_OPENERS = _compile(
    [
        r"^\s*this (image|is an?|scene|illustration|picture|appears|depicts)\b",
        r"^\s*in this (scene|image|illustration)\b",
        r"^\s*the (image|scene|illustration) (shows|depicts|features)\b",
        r"^\s*gambar ini\b",
        r"^\s*ini adalah (sebuah )?(gambar|ilustrasi|adegan)\b",
    ]
)

DESCRIPTION_VOCABULARY = _compile(
    [
        r"\banime\b",
        r"\billustration\b",
        r"\bdepict",
        r"\bcharacter",
        r"\bpanel",
        r"\bstyle\b",
        r"\bmanga\b",
        r"\bscene\b",
        r"\bbackground\b",
        r"\bvisual novel\b",
        r"\bdoujinshi\b",
        r"\bilustrasi\b",
        r"\bkarakter\b",
        r"\blatar belakang\b",
        r"\badegan\b",
        r"\bmenampilkan\b",
    ]
)


REASON_MESSAGES = {
    "refusal": "Model menolak menerjemahkan gambar ini.",
    "description": "Model menjelaskan gambar, bukan menerjemahkan (mungkin tidak ada teks yang terbaca). Coba mode overlay.",
    "loop": "Model terjebak mengulang kalimat yang sama.",
    "empty": "Model tidak menghasilkan teks.",
}


class NonTranslationError(Exception):
    """The model answered, but not with a translation (see `reason`)."""

    def __init__(self, reason: str):
        self.reason = reason
        self.message = REASON_MESSAGES.get(reason, "Model tidak menghasilkan terjemahan.")
        super().__init__(self.message)


@dataclass(frozen=True)
class Verdict:
    kind: str  # ok | truncated | empty | refusal | description | loop
    ok: bool


_OK = Verdict("ok", True)
_TRUNCATED = Verdict("truncated", True)


def _normalised_lines(text: str) -> List[str]:
    lines = (re.sub(r"[\W_]+", " ", line.casefold()).strip() for line in text.splitlines())
    return [line for line in lines if line]


def _has_repeated_line(lines: List[str]) -> bool:
    counts: dict = {}
    for line in lines:
        if len(line) >= LOOP_MIN_LINE_CHARS:
            counts[line] = counts.get(line, 0) + 1
    return any(count >= LOOP_MIN_LINE_REPEATS for count in counts.values())


def _has_low_variety(lines: List[str]) -> bool:
    return len(lines) >= LOOP_MIN_LINES_FOR_VARIETY and len(set(lines)) / len(lines) < LOOP_MAX_UNIQUE_RATIO


def _has_repeated_chunk(text: str) -> bool:
    flat = " ".join(text[:LOOP_SCAN_CHARS].split())
    for start in range(0, max(0, len(flat) - LOOP_CHUNK_CHARS + 1), LOOP_CHUNK_STEP):
        chunk = flat[start : start + LOOP_CHUNK_CHARS]
        if len(set(chunk)) >= LOOP_CHUNK_MIN_DISTINCT_CHARS and flat.count(chunk) >= LOOP_CHUNK_REPEATS:
            return True
    return False


def is_loop(text: str) -> bool:
    lines = _normalised_lines(text)
    return _has_repeated_line(lines) or _has_low_variety(lines) or _has_repeated_chunk(text)


def _is_refusal(text: str) -> bool:
    return len(text) < MAX_REFUSAL_CHARS and any(p.search(text) for p in REFUSAL_PATTERNS)


def _is_description(text: str) -> bool:
    if not any(p.search(text) for p in DESCRIPTION_OPENERS):
        return False
    return sum(1 for p in DESCRIPTION_VOCABULARY if p.search(text)) >= MIN_DESCRIPTION_VOCABULARY


def classify_image_reply(text: Optional[str], finish_reason: Optional[str] = None) -> Verdict:
    stripped = (text or "").strip()
    if not stripped:
        return Verdict("empty", False)
    if _is_refusal(stripped):
        return Verdict("refusal", False)
    if is_loop(stripped):
        return Verdict("loop", False)
    if _is_description(stripped):
        return Verdict("description", False)
    return _TRUNCATED if finish_reason == "length" else _OK
