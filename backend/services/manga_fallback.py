"""
Optional second (vision) model for text boxes the primary Index-Translate model could not translate
(looping, describing the picture, empty). The reply goes through the same guard as the primary one, so a
comment or a description never reaches the page. ADR-137 measured it on a handful of failed boxes only.
"""
from typing import Dict, List

from services.translation_guard import NonTranslationError, classify_image_reply, unwrap_labeled_quote

NO_TEXT_MARKER = "NOTEXT"
FALLBACK_MAX_TOKENS = 300
_QUOTES = "\"'“”‘’「」『』"

_PROMPT = (
    "This is a crop of one text bubble from a manga page. Translate the text inside it into {lang}. "
    "Output ONLY the translation: no explanation, no quotation marks, no description of the picture. "
    "If there is no readable text, output the single word " + NO_TEXT_MARKER + "."
)


def build_fallback_messages(image_data_url: str, target_lang: str) -> List[Dict[str, object]]:
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": _PROMPT.format(lang=target_lang)},
                {"type": "image_url", "image_url": {"url": image_data_url}},
            ],
        }
    ]


async def translate_crop_fallback(provider, image_data_url: str, target_lang: str) -> str:
    """Translation of one crop, or "" when the model says there is no text. Raises NonTranslationError for
    replies that are not translations."""
    raw = await provider.chat_completion(
        messages=build_fallback_messages(image_data_url, target_lang),
        temperature=0.0,
        max_tokens=FALLBACK_MAX_TOKENS,
    )
    text = unwrap_labeled_quote((raw or "").strip()).strip().strip(_QUOTES).strip()
    if not text or text.upper().rstrip(".!") == NO_TEXT_MARKER:
        return ""
    verdict = classify_image_reply(text)
    if not verdict.ok:
        raise NonTranslationError(verdict.kind)
    return text
