"""
Prompt profile for the Index-Translate model family (Bilibili Index team).

These models are trained on two prompt shapes only: a one-line translation request and the
"instTrans" constrained format. A long free-form system prompt is outside that distribution and
small variants (2B) tend to echo it back, so for these models the whole request is a single user
message built from the official templates (github.com/bilibili/Index-Translate,
inference/llm/translate.py).
"""
import re
from typing import Dict, List, Sequence, Tuple

GlossaryPair = Tuple[str, str]

DEFAULT_GLOSSARY_LIMIT = 30
_MODEL_MARKER = "indextranslate"
_TARGET_NAMES = {"indonesian": "印尼语"}
_FALLBACK_TARGET_NAME = "英语"
_NOVEL_GENRE = "小说"
_PLAIN_SUFFIX = "直接输出翻译结果，不要进行任何解释。"
_CONSTRAINED_SUFFIX = "只输出译文，不要有任何额外说明。"


def is_index_translate_model(model: str | None) -> bool:
    """True for Index-Translate checkpoints/GGUF repos, however the separators are spelled."""
    if not model:
        return False
    return _MODEL_MARKER in re.sub(r"[\s_\-]", "", model.lower())


def _target_name(target_lang: str) -> str:
    return _TARGET_NAMES.get(target_lang.strip().lower(), _FALLBACK_TARGET_NAME)


def build_index_translate_prompt(
    text: str, target_lang: str, glossary: Sequence[GlossaryPair] = ()
) -> str:
    target = _target_name(target_lang)
    source = text.strip()
    if not glossary:
        return f"请将以下文本翻译为{target}，{_PLAIN_SUFFIX}\n\n{source}"

    terms = "、".join(f"{original}→{translated}" for original, translated in glossary)
    return (
        f"请将以下{_NOVEL_GENRE}翻译成{target}，并且严格遵循所有约束要求。\n\n"
        f"【源文】\n{source}\n\n"
        f"【约束要求】\n1. 【硬性要求】专名/术语对照: {terms}\n\n"
        f"{_CONSTRAINED_SUFFIX}"
    )


def build_index_translate_messages(
    text: str, target_lang: str, glossary: Sequence[GlossaryPair] = ()
) -> List[Dict[str, str]]:
    return [{"role": "user", "content": build_index_translate_prompt(text, target_lang, glossary)}]


def collect_glossary_pairs(
    db, thread_id: int | None, text: str, limit: int = DEFAULT_GLOSSARY_LIMIT
) -> List[GlossaryPair]:
    """Lorebook terms that actually occur in `text`, longest first. Small models only get relevant terms."""
    if not thread_id or not text:
        return []

    # Imported here: context_engine pulls in the AI package at import time.
    from sqlalchemy import select

    from database import LorebookEntry
    from services.context_engine import ContextEngine

    entries = db.execute(
        select(LorebookEntry).where(
            LorebookEntry.thread_id == thread_id, LorebookEntry.is_archived == False  # noqa: E712
        )
    ).scalars().all()

    matched = [
        entry
        for entry in entries
        if not ContextEngine.is_garbage_lorebook_entry(entry.original_term, entry.translated_term)
        and ContextEngine._term_matches_text(entry.original_term, text)
    ]
    matched.sort(key=lambda entry: (bool(entry.is_locked), len(entry.original_term)), reverse=True)
    return [(entry.original_term.strip(), entry.translated_term.strip()) for entry in matched[:limit]]
