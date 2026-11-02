"""
Optional second (vision) model for text boxes the primary Index-Translate model could not translate
(looping, describing the picture, empty). The reply goes through the same guard as the primary one, so a
comment or a description never reaches the page. ADR-137 measured it on a handful of failed boxes only.
"""
import re
from typing import Dict, List

from services.translation_guard import NonTranslationError, classify_image_reply, unwrap_labeled_quote

NO_TEXT_MARKER = "NOTEXT"
FALLBACK_MAX_TOKENS = 300
# A reasoning model (Qwen3.x) would otherwise spend the token budget thinking; models without the switch ignore it.
NO_THINKING_PAYLOAD = {"chat_template_kwargs": {"enable_thinking": False}}
_QUOTES = "\"'“”‘’「」『』"
_THINK_BLOCK = re.compile(r"<think\b[^>]*>.*?</think>", re.DOTALL | re.IGNORECASE)
_THINK_OPEN = re.compile(r"<think\b", re.IGNORECASE)

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
    messages = build_fallback_messages(image_data_url, target_lang)
    if hasattr(provider, "chat_completion_detailed"):
        raw = (
            await provider.chat_completion_detailed(
                messages, temperature=0.0, max_tokens=FALLBACK_MAX_TOKENS, extra=NO_THINKING_PAYLOAD
            )
        ).text
    else:
        raw = await provider.chat_completion(messages=messages, temperature=0.0, max_tokens=FALLBACK_MAX_TOKENS)
    raw = _THINK_BLOCK.sub("", raw or "")
    if _THINK_OPEN.search(raw):
        # Cut off mid-thought: there is no answer yet, which is not the same as "no text in the bubble".
        raise NonTranslationError("empty")
    text = unwrap_labeled_quote(raw.strip()).strip().strip(_QUOTES).strip()
    if not text or text.upper().rstrip(".!") == NO_TEXT_MARKER:
        return ""
    verdict = classify_image_reply(text)
    if not verdict.ok:
        raise NonTranslationError(verdict.kind)
    return text
