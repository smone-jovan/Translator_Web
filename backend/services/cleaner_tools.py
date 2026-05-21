import re
from dataclasses import dataclass, field

from database import Chapter, Thread
from services.hallucination_detector import HallucinationDetector


AD_LINE_PATTERNS = [
    r"discord",
    r"telegram",
    r"whatsapp",
    r"group chat",
    r"join\s+our\s+group",
    r"facebook\.com",
    r"instagram\.com",
    r"t\.me/",
    r"wa\.me/",
    r"discord\.gg",
    r"novelupdates",
    r"wattpad",
    r"webnovel",
    r"patreon",
    r"ko-?fi",
    r"buy me a coffee",
    r"scan the qr",
    r"备用网址",
    r"最新网址",
    r"本站",
    r"本章未完",
    r"收藏本站",
    r"广告",
    r"群号",
    r"qq群",
    r"加群",
    r"网址",
    r"www\.",
    r"https?://",
]

TOC_PATTERNS = [
    r"table of contents",
    r"contents",
    r"copyright",
    r"cover",
    r"title page",
    r"illustrations",
    r"目录",
    r"版权",
    r"封面",
    r"扉页",
]

CHAPTERISH_PATTERNS = [
    r"chapter\s+\d+",
    r"ch\.\s*\d+",
    r"bab\s+\d+",
    r"volume\s+\d+",
    r"vol\.\s*\d+",
    r"^\d+[.:：、\-\s]",
    r"第.{0,8}[章节话回卷]",
    r"序章",
    r"楔子",
    r"prologue",
    r"epilogue",
]


@dataclass
class CleanerSummary:
    chapters_scanned: int = 0
    chapters_deleted: int = 0
    chapters_updated: int = 0
    lines_removed: int = 0
    deleted_chapter_ids: list[int] = field(default_factory=list)


class CleanerTools:
    @staticmethod
    def clean_text_block(text: str | None) -> tuple[str, int]:
        if not text:
            return "", 0

        removed = 0
        cleaned_lines: list[str] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                cleaned_lines.append("")
                continue

            if CleanerTools._is_ad_or_web_noise(line):
                removed += 1
                continue

            cleaned_lines.append(raw_line)

        cleaned = "\n".join(cleaned_lines)
        cleaned = HallucinationDetector.strip_garbled_hallucination_lines(cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        return cleaned, removed

    @staticmethod
    def clean_title(title: str | None) -> str | None:
        if not title:
            return title

        cleaned, _ = CleanerTools.clean_text_block(title)
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" -_|:#\t\r\n")
        return cleaned or title.strip()

    @staticmethod
    def run_txt_cleaner(thread: Thread) -> CleanerSummary:
        summary = CleanerSummary()
        for chapter in thread.chapters:
            summary.chapters_scanned += 1
            changed = False

            original_title = chapter.title_original
            translated_title = chapter.title_translated
            original_body = chapter.content_original or ""
            translated_body = chapter.content_translated or ""

            cleaned_original_title = CleanerTools.clean_title(original_title)
            cleaned_translated_title = CleanerTools.clean_title(translated_title)
            cleaned_original_body, removed_original = CleanerTools.clean_text_block(original_body)
            cleaned_translated_body, removed_translated = CleanerTools.clean_text_block(translated_body)

            if cleaned_original_title != original_title:
                chapter.title_original = cleaned_original_title
                changed = True
            if cleaned_translated_title != translated_title:
                chapter.title_translated = cleaned_translated_title
                changed = True
            if cleaned_original_body != original_body:
                chapter.content_original = cleaned_original_body
                changed = True
            if cleaned_translated_body != translated_body:
                chapter.content_translated = cleaned_translated_body
                changed = True

            summary.lines_removed += removed_original + removed_translated
            if changed:
                summary.chapters_updated += 1

        return summary

    @staticmethod
    def run_epub_cleaner(thread: Thread) -> CleanerSummary:
        summary = CleanerSummary()
        kept_chapters: list[Chapter] = []
        chapters = sorted(thread.chapters, key=lambda item: item.order)

        for index, chapter in enumerate(chapters):
            summary.chapters_scanned += 1

            title = (chapter.title_original or "").strip()
            body = (chapter.content_original or "").strip()
            cleaned_title = CleanerTools.clean_title(title) or title
            cleaned_body, removed_lines = CleanerTools.clean_text_block(body)
            previous_chapter = kept_chapters[-1] if kept_chapters else None
            next_chapter = chapters[index + 1] if index + 1 < len(chapters) else None

            chapter.title_original = cleaned_title
            chapter.content_original = cleaned_body
            summary.lines_removed += removed_lines

            if CleanerTools._should_merge_into_previous(cleaned_title, cleaned_body, previous_chapter, next_chapter):
                if kept_chapters and cleaned_body:
                    previous = kept_chapters[-1]
                    previous_body = (previous.content_original or "").strip()
                    merged_body = CleanerTools._merge_chapter_bodies(previous_body, cleaned_body)
                    if merged_body != previous.content_original:
                        previous.content_original = merged_body
                        summary.chapters_updated += 1
                summary.chapters_deleted += 1
                summary.deleted_chapter_ids.append(chapter.id)
                continue

            kept_chapters.append(chapter)

        for new_order, chapter in enumerate(kept_chapters):
            if chapter.order != new_order:
                chapter.order = new_order
                summary.chapters_updated += 1

        return summary

    @staticmethod
    def _looks_like_false_epub_chapter(title: str, body: str) -> bool:
        title_lower = title.lower()
        body_len = len(body.strip())

        if any(re.search(pattern, title_lower) for pattern in TOC_PATTERNS) and body_len < 1200:
            return True

        if CleanerTools._looks_like_garbled_chapter_title(title):
            return True

        if CleanerTools._is_ad_or_web_noise(title) and body_len < 1500:
            return True

        if body_len < 80 and CleanerTools._is_ad_or_web_noise(body):
            return True

        if body_len < 50 and not CleanerTools._looks_like_real_chapter_title(title):
            return True

        return False

    @staticmethod
    def _should_merge_into_previous(
        title: str,
        body: str,
        previous_chapter: Chapter | None,
        next_chapter: Chapter | None
    ) -> bool:
        if CleanerTools._looks_like_false_epub_chapter(title, body):
            return True

        if not previous_chapter or not next_chapter:
            return False

        current_num = CleanerTools._extract_chapter_number(title)
        previous_num = CleanerTools._extract_chapter_number(previous_chapter.title_original or "")
        next_num = CleanerTools._extract_chapter_number(next_chapter.title_original or "")

        if current_num is None or previous_num is None or next_num is None:
            return False

        body_words = len((body or "").split())
        is_number_outlier = current_num not in {previous_num - 1, previous_num, previous_num + 1} and current_num not in {next_num - 1, next_num, next_num + 1}
        is_between_sequential_neighbors = next_num > previous_num and (next_num - previous_num) <= 3
        has_garbled_title = CleanerTools._looks_like_garbled_chapter_title(title)
        is_short_fragment = body_words <= 120

        return has_garbled_title and is_between_sequential_neighbors and (is_number_outlier or is_short_fragment)

    @staticmethod
    def _looks_like_real_chapter_title(title: str) -> bool:
        title_lower = title.lower()
        return any(re.search(pattern, title_lower) for pattern in CHAPTERISH_PATTERNS)

    @staticmethod
    def _looks_like_garbled_chapter_title(title: str) -> bool:
        if not title:
            return False

        stripped = title.strip()
        suspicious_chars = len(re.findall(r"[①-⑳⑴-⑼⓪⒈-⒛\[\]{}<>#%&_+=|\\/~@^*]", stripped))
        nonstandard_chars = len(re.findall(r"[^0-9A-Za-z\u4E00-\u9FFF\s:：\-_.(),，。!?！？]", stripped))
        latin_count = len(re.findall(r"[A-Za-z]", stripped))
        cjk_count = len(re.findall(r"[\u4E00-\u9FFF]", stripped))
        prefix_match = re.match(r"^(ch(?:apter)?\.?\s*\d+[:：\- ]+)", stripped, re.IGNORECASE)
        suffix = stripped[prefix_match.end():] if prefix_match else stripped
        suffix_len = max(len(suffix), 1)
        suspicious_ratio = (suspicious_chars + nonstandard_chars) / max(len(stripped), 1)

        if suspicious_ratio >= 0.12 and (suspicious_chars >= 2 or nonstandard_chars >= 4):
            return True

        if prefix_match and suffix_len <= 80 and (suspicious_chars >= 1 or nonstandard_chars >= 3) and latin_count >= 2 and cjk_count >= 2:
            return True

        return False

    @staticmethod
    def _merge_chapter_bodies(previous_body: str, next_body: str) -> str:
        previous_body = (previous_body or "").strip()
        next_body = (next_body or "").strip()
        if not previous_body:
            return next_body
        if not next_body:
            return previous_body
        if next_body in previous_body:
            return previous_body
        return f"{previous_body}\n\n{next_body}".strip()

    @staticmethod
    def _extract_chapter_number(title: str) -> int | None:
        if not title:
            return None

        simple_match = re.search(r"^\s*(\d+)[.:：、\-\s]", title)
        if simple_match:
            try:
                return int(simple_match.group(1))
            except ValueError:
                return None

        patterns = [
            r"ch(?:apter)?\.?\s*(\d+)",
            r"bab\s*(\d+)",
            r"第\s*(\d+)\s*[章节话回卷]",
            r"卷\s*([0-9]+)",
        ]
        lowered = title.lower()
        for pattern in patterns:
            match = re.search(pattern, lowered, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    return None
        return None

    @staticmethod
    def _is_ad_or_web_noise(text: str) -> bool:
        lowered = text.lower().strip()
        if not lowered:
            return False

        if any(re.search(pattern, lowered) for pattern in AD_LINE_PATTERNS):
            return True

        if len(re.findall(r"https?://|www\.|\.com|\.net|\.org|\.me|\.gg", lowered)) >= 1:
            return True

        return False
