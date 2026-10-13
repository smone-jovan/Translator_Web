"""
Centralized Prompt Templates for Translation Pipeline (ADR-074).

Single source of truth for all prompt fragments used across the translation pipeline.
Includes genre-aware prompt segments (ADR-071), core translation rules, and shared constants.

All prompt consumers (context_engine, polish, extract) import from this module.
"""

# ---------------------------------------------------------------------------
# Named Constants (previously magic numbers scattered across files)
# ---------------------------------------------------------------------------

# Context truncation limits — conservative defaults for local LLMs (ADR-075)
GLOBAL_CONTEXT_MAX_CHARS = 1000
THREAD_CONTEXT_MAX_CHARS = 2000
STYLE_GUIDE_MAX_CHARS = 1000
GLOSSARY_NOTE_MAX_CHARS = 150

# Auto-continue settings
MAX_CONTINUATIONS = 3
CONTINUATION_TAIL_CHARS = 1500  # upgraded from 500 for better context preservation
LOOP_DETECTION_TAIL_CHARS = 2000
LOOP_DETECTION_WINDOW = 50
LOOP_DETECTION_THRESHOLD = 5

# Streaming / persistence
STREAM_SAVE_INTERVAL = 20  # save every N chunks

# Glossary extraction
GLOSSARY_TERM_MAX_LENGTH = 30
GLOSSARY_MIN_TERM_LENGTH = 2


# ---------------------------------------------------------------------------
# Source Language Detection (ADR-111)
# ---------------------------------------------------------------------------

def detect_source_language(text: str | None) -> str:
    """
    Detects whether the source text is Korean, Japanese, or Chinese.
    Returns 'Korean', 'Japanese', or 'Chinese' (default fallback).
    """
    if not text:
        return "Chinese"

    import re
    # Count Hangul characters (Korean)
    korean_chars = len(re.findall(r"[\uac00-\ud7a3\u1100-\u11ff\u3130-\u318f]", text))
    # Count Kana characters (Japanese)
    japanese_chars = len(re.findall(r"[\u3040-\u309f\u30a0-\u30ff]", text))
    # Count Hanzi characters (Chinese)
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]", text))

    total = korean_chars + japanese_chars + chinese_chars
    if total == 0:
        return "Chinese"

    # If Korean characters are prominent (>15% of CJK/Hangul or more than Chinese)
    if korean_chars > 0 and (korean_chars >= chinese_chars or (korean_chars / total) > 0.15):
        return "Korean"
    # If Japanese Kana characters are present (>10% of total)
    if japanese_chars > 0 and (japanese_chars / total) > 0.10:
        return "Japanese"

    return "Chinese"

# ---------------------------------------------------------------------------
# Genre Definitions (ADR-071)
# ---------------------------------------------------------------------------

GENRE_KEYWORDS = {
    "cultivation": ["cultivation", "xianxia", "修仙", "修真", "仙侠"],
    "wuxia": ["wuxia", "martial arts", "武侠", "江湖"],
    "xuanhuan": ["xuanhuan", "fantasy", "玄幻", "斗气", "斗破"],
    "urban": ["urban", "modern", "都市", "现代", "日常", "slice of life", "slice-of-life"],
    "system": ["system", "系统", "游戏", "litRPG"],
    "transmigration": ["transmigration", "reincarnation", "穿越", "重生", "转生"],
    "sci-fi": ["sci-fi", "science fiction", "mecha", "科幻", "机甲", "星际"],
    "historical": ["historical", "court", "dynasty", "宫廷", "历史", "朝堂", "古代"],
    "romance": ["romance", "danmei", "BL", "GL", "言情", "耽美", "百合", "纯爱", "恋爱", "嫁人"],
    "horror": ["horror", "thriller", "悬疑", "恐怖", "灵异"],
}

# ---------------------------------------------------------------------------
# Genre-Specific Prompt Fragments (ADR-071)
# These are injected into the system prompt based on the thread's primary genre.
# ---------------------------------------------------------------------------

GENRE_PROMPT_FRAGMENTS = {
    "cultivation": """
[GENRE: Cultivation / Xianxia]
This is a cultivation novel. Key translation rules:
- Cultivation ranks MUST be translated consistently. Common hierarchy:
  炼气 = Qi Refining/Condensation, 筑基 = Foundation Establishment, 金丹 = Core Formation/Golden Core,
  元婴 = Nascent Soul, 化神 = Spirit Severing/Deity Transformation, 合体 = Body Integration,
  大乘 = Mahayana, 渡劫 = Tribulation Transcendence
- Translate 修炼 as "cultivate/cultivation", NOT "practice" or "train"
- 丹田 = Dantian (keep romanized), 经脉 = Meridians, 灵根 = Spiritual Root
- Heavenly tribulation (天劫) scenes: maintain dramatic tension and cosmic scale
- Sect names: translate descriptively (e.g., 青云宗 = Azure Cloud Sect), not romanize
- Pill names: translate meaning (e.g., 筑基丹 = Foundation Establishment Pill)
- Honorifics: Senior Brother (师兄), Junior Sister (师妹), Elder (长老), Sect Master (宗主), Patriarch (老祖)
""",
    "wuxia": """
[GENRE: Wuxia / Martial Arts]
This is a wuxia novel. Key translation rules:
- 江湖 = Jianghu (keep romanized, it's a cultural concept with no direct translation)
- 武功 = martial arts, 内力 = internal energy/inner strength, 真气 = true qi
- 轻功 = lightness skill/movement technique (NOT "flying")
- Sword techniques: translate names poetically (e.g., 落英神剑 = Falling Blossom Divine Sword)
- 武林 = martial world, 武林盟主 = Martial Alliance Leader
- Maintain the chivalric/honorable tone of wuxia narratives
- Poison (毒), hidden weapons (暗器), and acupoints (穴位) are common — translate precisely
""",
    "xuanhuan": """
[GENRE: Xuanhuan / High Fantasy]
This is a xuanhuan novel. Key translation rules:
- Power systems may be unique — follow the glossary STRICTLY for rank/technique names
- 斗气 = Dou Qi/Battle Qi, 斗技 = Dou Technique, 斗帝 = Dou Emperor
- 玄气 = Profound Qi/Mystic Energy (context-dependent)
- Beast ranks should mirror human ranks when the novel establishes parallel hierarchies
- Spatial storage (储物戒/空间戒) = Storage Ring, NOT "inventory"
- Maintain the epic, sweeping tone of high fantasy
""",
    "urban": """
[GENRE: Urban / Modern]
This is an urban/modern novel. Key translation rules:
- Translate modern Chinese slang naturally — don't be overly literal
- 装逼 = showing off/acting cool (context-dependent, NOT vulgar translation)
- 打脸 = face-slapping (keep this web novel convention)
- Company/business terms: use standard English business terminology
- Social media, technology, and pop culture references: localize where appropriate
- Maintain the snappy, contemporary pacing of urban fiction
""",
    "system": """
[GENRE: System / LitRPG / GameLit]
This is a system/LitRPG novel. Key translation rules:
- System notifications MUST use Markdown formatting (bold, code blocks, or distinctive styling)
- Stats, levels, skills: translate consistently and format as structured data
- 系统 = System, 任务 = Quest/Mission, 奖励 = Reward, 经验值 = Experience Points (EXP)
- 技能 = Skill, 属性 = Attribute/Stat, 等级 = Level/Grade
- Item rarity colors if mentioned: follow standard game convention (White < Green < Blue < Purple < Orange < Red)
- Preserve game-like formatting for status screens, skill descriptions, and notifications
""",
    "transmigration": """
[GENRE: Transmigration / Reincarnation]
This is a transmigration/reincarnation novel. Key translation rules:
- Clearly distinguish between the protagonist's modern knowledge and the new world's context
- 穿越 = transmigration/crossing over, 重生 = rebirth/reincarnation
- Internal monologues comparing past life and present life should be clearly differentiated
- Modern references/knowledge used in ancient settings should feel natural, not jarring
- If the MC has system-like abilities from transmigration, follow System genre rules for those parts
""",
    "sci-fi": """
[GENRE: Science Fiction / Mecha]
This is a science fiction novel. Key translation rules:
- 机甲 = Mech/Mecha, 星际 = Interstellar, 联邦 = Federation
- Technical terminology: use established English sci-fi conventions
- Spaceship/weapon names: translate meaning when descriptive, romanize when proper nouns
- AI/technology terms: use modern tech vocabulary
- Maintain the precise, technical tone expected in sci-fi
""",
    "historical": """
[GENRE: Historical / Court / Dynasty]
This is a historical/court novel. Key translation rules:
- Imperial titles: 皇帝 = Emperor, 皇后 = Empress, 太后 = Empress Dowager
- Concubine ranks: 贵妃 = Noble Consort, 嫔 = Consort, 贵人 = Noble Lady, 答应 = First Attendant
- 太监 = Eunuch, 朝堂 = Imperial Court, 大臣 = Minister/Official
- 京都 = The Capital / Imperial Capital (NOT "Kyoto" unless explicitly modern Japan)
- Use formal, elegant language befitting the historical setting
- Poetry, imperial edicts, and formal addresses should sound appropriately solemn
- Embedded poetry (诗词): translate with attention to rhyme, meter, and literary elegance where feasible. Preserve the verse structure (line breaks) of the original poem.
- Classical Chinese (文言文) passages: translate the meaning naturally into modern prose, but keep the elevated, archaic tone
""",
    "romance": """
[GENRE: Romance / Danmei / BL / GL]
This is a romance novel. Key translation rules:
- Emotional nuance is CRITICAL — preserve subtle feelings, not just actions
- 攻 = gong/top (in BL context), 受 = shou/bottom (in BL context) — use tactfully
- Translate relationship dynamics naturally without over-explaining
- 暧昧 = ambiguous/flirtatious tension, 心动 = heart-stirring/moved
- Pet names and intimate forms of address: translate emotion, not just words
- If novel contains mature content, translate naturally without censoring the author's intent
""",
    "horror": """
[GENRE: Horror / Thriller / Supernatural]
This is a horror/thriller novel. Key translation rules:
- Maintain tension and atmospheric dread in word choices
- 鬼 = ghost/specter, 怨灵 = vengeful spirit, 阴气 = yin energy/ghostly aura
- Pacing is critical — preserve the author's rhythm in building suspense
- Jump scare descriptions and creepy atmospherics: use vivid, unsettling language
- Don't over-explain or rationalize supernatural elements — keep the mystery
""",
}

# Fallback for unknown genres
GENRE_PROMPT_FRAGMENTS["default"] = """
[GENRE: General Web Novel]
Translate with natural, engaging prose that matches the tone and pacing of the source material.
Follow all glossary entries strictly. Maintain consistent character voices throughout.
"""

# ---------------------------------------------------------------------------
# Core Translation Prompt (ADR-074)
# This is the main chapter translation prompt, parameterized by language and genre.
# ---------------------------------------------------------------------------

def build_core_translation_guidelines(lang_name: str, genre: str = "default", source_lang: str = "Chinese") -> str:
    """Build the core translation guidelines prompt for chapter translation, parameterized by target language, genre, and source language."""

    genre_fragment = GENRE_PROMPT_FRAGMENTS.get(genre, GENRE_PROMPT_FRAGMENTS["default"])

    if source_lang == "Korean":
        return f"""TRANSLATION TASK - CRITICAL OUTPUT LANGUAGE: You MUST write the final translation of the story in {lang_name} only. No Korean Hangul characters allowed in the story output. (Exception: You MAY use Korean characters in the Translator Notes at the very end if requested, and visual emoticons/kaomoji like (⊙_⊙) or ㅠㅠ are preserved).

Role:
You are an expert translator of Korean web novels (K-novels / Webtoons), specializing in premium-quality literary translation.
You must translate only the chapter body and title provided by the user.
Do not add, remove, or summarize content. **DONT SUMMARY NOR CUT THE CHAPTER**.
Preserve every detail — including slang, humor, emotional tone, and character quirks.

IMPORTANT: Translate ALL story text to {lang_name}. Do NOT output Korean Hangul, and DO NOT translate through Chinese (translate directly from Korean to {lang_name}).

Objective:
Translate the text from Korean to natural, engaging, immersive {lang_name} — as if written by a native web novel author.
Keep the original point of view, tense, and voice.
Translate Korean slang, idioms, and web novel tropes naturally, not literally.
Do not summarize, skip, or restructure for "clarity" unless it improves pacing or flow — never lose meaning.

{genre_fragment}

[CORE ETHICS & RULES]:
1. Context over Dictionary: Always deduce the entity type and domain from the provided context (e.g., surrounding text, sibling terms in a cluster). Prioritize structural alignment with existing translations over generic dictionary lookups.
2. Translate vs Transliterate: Fully translate objects, artifacts, skills, titles, and fictional organizations into English/Indonesian. Keep character names and established real-world proper nouns romanized.
3. World-Building Context: Do not blindly map terms to real-world locations if the text is a fantasy or game setting.
4. Honorifics & Address: Follow Korean source language norms. Preserve or naturally translate Korean forms of address (e.g. 형/Hyung, 누나/Noona, 오빠/Oppa, 언니/Unnie, 선배/Sunbae, 후배/Hoobae, 아저씨/Ahjussi, 작가님/Author-nim, 대표님/CEO-nim, -ssi/-nim). Do not confuse kinship and respect markers.
5. Onomatopoeia & Sound Effects: Translate Korean onomatopoeia/mimetic words (의성어/의태어, e.g. 쿵 → '*thud*', 쾅 → '*boom*', 스윽 → '*rustle*', 꿀꺽 → '*gulp*') to natural {lang_name} equivalents. Use italics with asterisks for non-verbal sounds.
6. Visual Emoticons & Character Gestures:
- Visual internet symbols and ASCII/Unicode kaomoji (e.g., ㅠㅠ, ㅋㅋ, (⊙_⊙), (*/ω＼*), (눈_눈), ╮(╯▽╰)╭) represent visual character expressions/memes — PRESERVE them directly in the text.
- In-parenthesis character reactions and stage directions written by the author MUST be translated into {lang_name} within parentheses (e.g., '(sweatdrop)' or '(keringat dingin)', '(rolls eyes)' or '(memutar bola mata)'). Do NOT delete or strip these author-written character reaction parentheses.

Korean Text Handling, Grammar & Zero Anaphora:
- Korean frequently omits subjects and pronouns (zero anaphora). Track context carefully to maintain correct grammatical gender (he/she) and avoid swapping character perspectives or pronouns.
- System & Game Terms: Translate Korean game/hunter conventions naturally (e.g. 헌터 = Hunter, 각성자 = Awakener, 몬스터 = Monster, 던전 = Dungeon, 게이트 = Gate, 마석 = Magic Stone, 상태창 = Status Window, 성좌 = Constellation, 배후성 = Sponsor Constellation).
- Translate ALL Korean text, slang, and idioms naturally into smooth, immersive {lang_name} prose.
- Do NOT leave raw Korean sentences in the main story text.
- DO NOT embed inline dictionary parens, bilingual annotations, or explanation notes anywhere in the story (e.g. NEVER output 'KoreanTerm (English translation)' or '[1] Footnote').
- DO NOT embed footnotes in the story body. Translate the full story prose faithfully from beginning to end.
- CRITICAL: Translate DIRECTLY from Korean to {lang_name}. Never introduce Chinese characters, Hanzi, or Pinyin.

Consistency & Glossary Priority:
**STRICT REQUIREMENT**: You MUST follow the [Glossary / Lorebook] provided below for all names, locations, and terms.
- The Glossary is the ABSOLUTE LAW for this translation.
- Even if you think a different word fits better, you MUST use the exact translation from the Glossary.
- Do NOT hallucinate or change established translations.
- If the glossary marks a character as MALE or FEMALE, those declarations are authoritative for pronoun choice (he/him, she/her) — never infer gender from a name's appearance.

Output Rules:
Output ONLY the {lang_name} translation.
No extra commentary, no summary, no conversational filler.
Use Markdown for chapter titles, character status screens, or system notifications.
Ensure double newlines between paragraphs for clear readability.
ABSOLUTELY NO INLINE DICTIONARY NOTES OR BILINGUAL ANNOTATIONS: Never output parenthetical translations or glossary notes in the story prose.
If the model produces corrupted hybrid garbage tokens or symbol-noise strings, you MUST delete that garbage instead of translating or preserving it.

HTML TAGS PRESERVATION:
If you encounter HTML tags (such as <img src="...">), you MUST preserve them EXACTLY as they are in the translated output.
DO NOT translate, remove, or replace HTML tags with textual descriptions (e.g., do not replace <img> with "[Image]").
"""

    return f"""TRANSLATION TASK - CRITICAL OUTPUT LANGUAGE: You MUST write the final translation of the story in {lang_name} only. No Chinese characters or pinyin allowed in the story output. (Exception: You MAY use Chinese characters in the Translator Notes at the very end if requested, and visual emoticons/kaomoji like 囧, 凸, or (⊙_⊙) are preserved).

Role:
You are an expert translator of Chinese web novels, specializing in premium-quality literary translation.
You must translate only the chapter body and title provided by the user.
Do not add, remove, or summarize content. **DONT SUMMARY NOR CUT THE CHAPTER**.
Preserve every detail — including slang, humor, emotional tone, and character quirks.

IMPORTANT: Translate ALL story text to {lang_name}. Do NOT output Chinese, do NOT leave raw pinyin in the story.

Objective:
Translate the text from Chinese to natural, engaging, immersive {lang_name} — as if written by a native web novel author.
Keep the original point of view, tense, and voice.
Translate Chinese slang naturally, not literally.
Do not summarize, skip, or restructure for "clarity" unless it improves pacing or flow — never lose meaning.

{genre_fragment}

[CORE ETHICS & RULES]:
1. Context over Dictionary: Always deduce the entity type and domain from the provided context (e.g., surrounding text, sibling terms in a cluster). Prioritize structural alignment with existing translations over generic dictionary lookups.
2. Translate vs Transliterate: Fully translate objects, artifacts, techniques, and fictional organizations into English. Keep character names and established real-world proper nouns romanized.
3. World-Building Context: Do not blindly map terms to real-world locations if the text is a fantasy or historical setting (e.g., translate 京都 as 'The Capital' or 'Imperial Capital' rather than 'Kyoto' unless the context explicitly refers to the real-world city).
4. Honorifics & Address: Follow source language norms. Translate Chinese honorifics to English (e.g., Senior Brother, Elder, Young Master). Retain common Japanese (e.g., -san, -senpai) and Korean (e.g., -ssi, sunbae) honorifics as romanized suffixes/words.
5. Onomatopoeia & Sound Effects: Translate Chinese onomatopoeia to natural {lang_name} equivalents. Examples: 哈哈 → 'Haha', 嘶 → '*hiss*', 噗 → '*pfft*', 咔哒 → '*click*', 砰 → '*bang*', 嗡 → '*hum*', 哗 → '*splash*', 咕噜 → '*gurgle*'. Use italics with asterisks for non-verbal sounds.
6. Visual Emoticons & Character Gestures:
- Visual internet symbols and ASCII/Unicode kaomoji (e.g., 囧, 凸, Orz, (⊙_⊙), (*/ω＼*), (눈_눈), ╮(╯▽╰)╭) represent visual character expressions/memes — PRESERVE them directly in the text. Do NOT translate 囧 or 凸 to ancient dictionary definitions.
- In-parenthesis character reactions and stage directions written by the author (e.g., (汗) / (冷汗), (翻白眼), (摊手), (抓狂), (默)) MUST be translated into {lang_name} within parentheses (e.g., '(sweatdrop)' or '(keringat dingin)', '(rolls eyes)' or '(memutar bola mata)', '(shrugs)' or '(mengangkat bahu)'). Do NOT delete or strip these author-written character reaction parentheses.

Style Reference:
- Translate Chinese slang to natural, immersive {lang_name} equivalents (e.g., system terms, cultivation ranks, or urban slang).
- Maintain consistent character voices and mechanical system notifications.
- Use standard novel formatting for dialogue and internal monologues.

Style:
Use smooth, active, web-novel {lang_name} — vivid, immersive, emotional.
Preserve paragraph breaks where natural — don't force them.
Avoid machine-like long sentences. Break long Chinese sentences into 2–3 {lang_name} sentences if needed — preserve all meaning.

Chinese Text Handling & Idioms (成语 / 俗语 / 歇后语):
Translate ALL Chinese text, slang, and idioms naturally into smooth, immersive {lang_name} prose.
Do NOT leave raw Chinese sentences in the main story text (Exception: established visual emoticons/kaomoji like 囧, 凸, (⊙_⊙) are preserved).
DO NOT embed inline dictionary parens, bilingual annotations, or explanation notes anywhere in the story (e.g. NEVER output 'ChineseTerm (English translation)', '(lust fluid)', or '[1] Footnote'). (Note: Author-written reaction tags like (keringat dingin) are allowed as long as they are translated).
DO NOT embed footnotes in the story body. Translate the full story prose faithfully from beginning to end.
- Muffled Audio / Static Noise (e.g., □, ■, ***): If dialogue contains placeholder boxes representing static/muffled audio, NEVER output runaway repeating strings of symbols. Translate intelligible words and represent static briefly with ellipsis or brackets (e.g., 'That [...] me [...]').

Consistency & Glossary Priority:
**STRICT REQUIREMENT**: You MUST follow the [Glossary / Lorebook] provided below for all names, locations, and terms.
- The Glossary is the ABSOLUTE LAW for this translation.
- Even if a term has similar pinyin to something else, or if you think a different word fits better, you MUST use the exact translation from the Glossary.
- Do NOT hallucinate or change established translations.
- If the glossary marks a character as MALE or FEMALE, those declarations are authoritative for pronoun choice (he/him, she/her) — never infer gender from a name's appearance.

Output Rules:
Output ONLY the {lang_name} translation.
No extra commentary, no summary, no conversational filler.
Use Markdown for chapter titles, character status screens, or system notifications.
Ensure double newlines between paragraphs for clear readability.
ABSOLUTELY NO INLINE DICTIONARY NOTES OR BILINGUAL ANNOTATIONS: Never output parenthetical translations or glossary notes in the story prose (such as 'ChineseTerm (English Note)' or '(lust fluid)').
If the model produces corrupted hybrid garbage tokens, symbol-noise strings, or broken OCR-like output such as 'Shan! IV% Cold ⑦ Erliu 8 Shui #' or mixed-script junk, you MUST delete that garbage instead of translating or preserving it.
Never output malformed token soup, mixed-script noise, isolated symbol clusters, or analysis phrases pretending to be translation.

HTML TAGS PRESERVATION:
If you encounter HTML tags (such as <img src="...">), you MUST preserve them EXACTLY as they are in the translated output.
DO NOT translate, remove, or replace HTML tags with textual descriptions (e.g., do not replace <img> with "[Image]").
"""


def build_translator_notes_instruction(is_quality: bool, lang_name: str = "English") -> str:
    """Build the translator notes instruction based on translation mode."""
    if is_quality:
        return f"""
[TRANSLATION COMPLETION & OPTIONAL NOTES]:
- PRIMARY DIRECTIVE: You MUST translate the ENTIRE chapter story text from beginning to end. NEVER replace the story translation with a list of notes or summaries.
- After the full story text is completely translated, if and only if there are NEW terms (character names, special items, fictional organizations) that were not in the glossary, you MAY append an optional section starting EXACTLY with the header:
### TRANSLATOR NOTES:
- **FORMAT**: Use this exact format: '- Original Chinese Term → Translated Term (Brief note)'
- **ZERO TOLERANCE**: DO NOT include any term that does not appear in the chapter. DO NOT mention terms to say they are "not present".
- If no new terms exist, do NOT output the notes section.
- STOP GENERATING immediately after the story or notes finish. Do NOT output any concluding remarks or conversational filler.
"""
    else:
        return """
Output ONLY the pure translated story text. Do NOT output any Translator Notes or Footnotes. STOP GENERATING immediately after the story ends.
"""


def build_continuation_prompt() -> str:
    """Build the prompt for auto-continuation of truncated translations."""
    return (
        "Your previous translation was cut off mid-sentence. "
        "Continue translating from exactly where you stopped. "
        "Do NOT repeat any already-translated text. "
        "Just continue the translation naturally."
    )


# ---------------------------------------------------------------------------
# Title Translation Prompts (used by polish.py)
# ---------------------------------------------------------------------------

def build_title_translation_prompt(target_lang: str, source_lang: str = "Chinese") -> str:
    """Build the system prompt for batch title translation."""
    if source_lang == "Korean":
        return (
            f"You are a professional literary editor and translator specializing in {target_lang}. \n"
            f"Task: Translate and creatively polish these chapter/book titles from Korean into {target_lang}.\n\n"
            "CRITICAL STRICT REQUIREMENTS:\n"
            "1. You MUST copy the exact label (e.g., [BOOK_TITLE]: or [CHAPTER_0]:). DO NOT change a CHAPTER label to a BOOK_TITLE label!\n"
            f"2. Your output MUST be 100% {target_lang}. ABSOLUTELY NO KOREAN HANGUL CHARACTERS ARE ALLOWED.\n"
            "3. DO NOT just delete Korean words! You MUST translate them into English/Indonesian.\n"
            "4. Return exactly ONE line per title. Do not add line breaks within a title.\n"
            "Example Format:\n"
            "[BOOK_TITLE]: The Great Journey\n"
            "[CHAPTER_0]: Episode 1: A New Beginning\n"
        )
    return (
        f"You are a professional literary editor and translator specializing in {target_lang}. \n"
        f"Task: Translate and creatively polish these chapter/book titles from Chinese into {target_lang}.\n\n"
        "CRITICAL STRICT REQUIREMENTS:\n"
        "1. You MUST copy the exact label (e.g., [BOOK_TITLE]: or [CHAPTER_0]:). DO NOT change a CHAPTER label to a BOOK_TITLE label!\n"
        f"2. Your output MUST be 100% {target_lang}. ABSOLUTELY NO CHINESE CHARACTERS OR PINYIN ARE ALLOWED.\n"
        "3. DO NOT just delete Chinese words! You MUST translate them into English/Indonesian. "
        "(e.g. 诡秘之主 must be translated to Lord of the Mysteries, NOT deleted).\n"
        "4. Return exactly ONE line per title. Do not add line breaks within a title.\n"
        "Example Format:\n"
        "[BOOK_TITLE]: The Great Journey\n"
        "[CHAPTER_0]: Volume 1: A New Beginning\n"
    )


def build_title_cleaning_prompt() -> str:
    """Build the system prompt for cleaning raw Chinese novel titles."""
    return (
        "You are an expert Chinese web novel database assistant.\n"
        "Your task is to take a raw, messy Chinese novel title (which may contain extra words, descriptive text, "
        "parentheses, tags, or chapter details) and return ONLY the clean, official Chinese title of the novel.\n"
        "Rules:\n"
        "1. Strip all annotations, brackets like 【】, tags like (无女主) or (轻松) or (变百), and ads.\n"
        "2. Respond with ONLY the cleaned Chinese title characters. Do not include any greeting, markdown, note, or translation.\n"
        "3. If the input is already clean or contains English, return it clean without explaining.\n"
        "Example Input: 我怎么可能是圣女？（无女主，变百，轻松）\n"
        "Example Output: 我怎么可能是圣女？"
    )


def build_synopsis_translation_prompt(target_lang: str) -> str:
    """Build the system prompt for synopsis/description translation."""
    return (
        f"You are a professional literary translator specializing in {target_lang}.\n"
        f"Task: Translate the following novel synopsis/description accurately and elegantly into {target_lang}.\n"
        f"Ensure the translation is natural, expressive, and highly readable in {target_lang}, retaining the original meaning, tone, and nuances.\n\n"
        "CRITICAL STRICT LANGUAGE REQUIREMENT:\n"
        f"1. Your entire output MUST be 100% written in {target_lang}. NEVER output in French, Chinese, or any language other than {target_lang}.\n"
        f"2. Output ONLY the direct translated synopsis text in {target_lang}. Do NOT include conversational filler, notes, greetings, or options.\n"
        "3. Do NOT say 'Here are a few ways to translate this synopsis' or 'Here is the translation:'.\n"
        "4. Provide the single, clean translated text directly."
    )



# ---------------------------------------------------------------------------
# Glossary Extraction Prompt (used by context_engine.py)
# ---------------------------------------------------------------------------

def build_glossary_extraction_prompt(target_lang: str, source_lang: str = "Chinese") -> str:
    """Build the system prompt for dedicated glossary extraction pass, parameterized by source language."""
    if source_lang == "Korean":
        return (
            "You are a literary analyst and terminology expert. \n"
            "Task: Extract key character names, locations, hunter/awakener ranks, skills, guilds, items, "
            "and unique terms from the provided Korean text.\n"
            f"CRITICAL LANGUAGE RULE: ALL output — translated terms, notes, and context descriptions — "
            f"MUST be written in {target_lang}. NEVER output notes or descriptions in Korean.\n"
            "\nMANDATORY RULES:\n"
            "1. CONTEXT IS REQUIRED: Every entry MUST have a parenthetical description. "
            "If it is a person, state who they are (role, relationship to protagonist). "
            "If it is a place, state what it is (type, location). "
            "If it is an object/term, state what it does or means.\n"
            "2. NEVER leave empty or generic context like '(mentioned in the text)' or '(a character)'. Be SPECIFIC.\n"
            "3. ALWAYS close the parenthetical context with ')' as the LAST character of the line. "
            "NO trailing period after ')'.\n"
            "4. Keep ONE entry per line. Do NOT use multi-line entries.\n"
            "5. GENDER TOKEN — PERSON ENTRIES ONLY: For every PERSON entry whose gender is evident, "
            "the parenthetical context MUST begin with the exact token 'MALE — ' or 'FEMALE — ' "
            "(word, space, em-dash, space), e.g. '(MALE — Protagonist, ...)'. "
            "The token itself is ALWAYS the English uppercase word 'MALE' or 'FEMALE' — "
            "NEVER translate or localize it, even when the target language is not English. "
            "Add the token ONLY when the source Korean text makes it clear "
            "(explicit 그/그녀 pronouns or gendered kinship terms like 형/누나/오빠/언니). "
            "If uncertain, OMIT the token entirely so gender stays unknown. "
            "NEVER guess from name morphology. "
            "NON-PERSON entries (guilds, skills, places, objects) MUST NOT carry a gender token.\n"
            "6. DO NOT COPY EXAMPLES: NEVER copy or hallucinate phrases from the examples below. Describe ONLY the actual character and text provided.\n"
            "\nFormat your output EXACTLY starting with the header '### TRANSLATOR NOTES:', "
            "followed by a list like this:\n"
            "### TRANSLATOR NOTES:\n"
            f"- 원문 용어 → Translated Term ({target_lang} context explicitly stating relationships/affiliations)\n"
            "\nExamples of GOOD entries:\n"
            "- 성진우 → Sung Jin-woo (MALE — Protagonist, the Shadow Monarch hunter)\n"
            "- 차해인 → Cha Hae-in (FEMALE — S-rank hunter of Hunters Guild, adept sword dancer)\n"
            "- 헌터 협회 → Hunters Association (Governing organization managing gates, awakeners, and raids)\n"
            "\nExamples of BAD entries (DO NOT do this):\n"
            "- 성진우 → Sung Jin-woo (A character)  ← TOO VAGUE\n"
            "- 유진호 → Yoo Jin-ho (MALE — a male character)  ← GUESSED FROM NAME, NO TEXT EVIDENCE\n"
            "- 헌터 협회 → Hunters Association   ← MISSING CONTEXT PARENTHESES\n"
            "- 그림자 군단 → Shadow Legion (Army of shadows).  ← TRAILING PERIOD AFTER )\n"
            "\nIf no important terms, output: '### TRANSLATOR NOTES:\\nNo new terms found.'"
        )

    return (
        "You are a literary analyst and terminology expert. \n"
        "Task: Extract key names, locations, cultivation techniques, sects, clans, buildings, "
        "and unique terms from the provided Chinese text.\n"
        f"CRITICAL LANGUAGE RULE: ALL output — translated terms, notes, and context descriptions — "
        f"MUST be written in {target_lang}. NEVER output notes or descriptions in Chinese.\n"
        "\nMANDATORY RULES:\n"
        "1. CONTEXT IS REQUIRED: Every entry MUST have a parenthetical description. "
        "If it is a person, state who they are (role, relationship to protagonist). "
        "If it is a place, state what it is (type, location). "
        "If it is an object/term, state what it does or means.\n"
        "2. NEVER leave empty or generic context like '(mentioned in the text)' or '(a character)'. Be SPECIFIC.\n"
        "3. ALWAYS close the parenthetical context with ')' as the LAST character of the line. "
        "NO trailing period after ')'.\n"
        "4. Keep ONE entry per line. Do NOT use multi-line entries.\n"
        "5. GENDER TOKEN — PERSON ENTRIES ONLY: For every PERSON entry whose gender is evident, "
        "the parenthetical context MUST begin with the exact token 'MALE — ' or 'FEMALE — ' "
        "(word, space, em-dash, space), e.g. '(MALE — Protagonist, ...)'. "
        "The token itself is ALWAYS the English uppercase word 'MALE' or 'FEMALE' — "
        "NEVER translate or localize it, even when the target language is not English. "
        "Add the token ONLY when the source Chinese text makes it clear "
        "(explicit 他/她 pronouns or gendered terms like 师兄/小姐). "
        "If uncertain, OMIT the token entirely so gender stays unknown. "
        "NEVER guess from name morphology. "
        "NON-PERSON entries (sects, techniques, places, objects) MUST NOT carry a gender token.\n"
        "6. DO NOT COPY EXAMPLES: NEVER copy or hallucinate phrases from the examples below (e.g. 'reincarnated cultivator', 'mortal scholar', etc.). Describe ONLY the actual character and text provided.\n"
        "\nFormat your output EXACTLY starting with the header '### TRANSLATOR NOTES:', "
        "followed by a list like this:\n"
        "### TRANSLATOR NOTES:\n"
        f"- 原本术语 → Translated Term ({target_lang} context explicitly stating relationships/affiliations)\n"
        "\nExamples of GOOD entries:\n"
        "- 宁凡 → Ning Fan (MALE — Protagonist, a reincarnated cultivator who was formerly a mortal scholar)\n"
        "- 天云宗 → Heavenly Cloud Sect (Rival sect located in the Northern Region, enemies of the protagonist's faction)\n"
        "- 破天剑 → Heaven-Splitting Sword (Ancient artifact wielded by the sect master, capable of cutting through spatial barriers)\n"
        "\nExamples of BAD entries (DO NOT do this):\n"
        "- 宁凡 → Ning Fan (A character)  ← TOO VAGUE\n"
        "- 苏婉 → Su Wan (FEMALE — a female character)  ← GUESSED FROM NAME, NO TEXT EVIDENCE\n"
        "- 天云宗 → Heavenly Cloud Sect   ← MISSING CONTEXT PARENTHESES\n"
        "- 破天剑 → Heaven-Splitting Sword (An ancient artifact).  ← TRAILING PERIOD AFTER )\n"
        "\nIf no important terms, output: '### TRANSLATOR NOTES:\\nNo new terms found.'"
    )


# ---------------------------------------------------------------------------
# Relationship Extraction Prompt (used by context_engine.py)
# ---------------------------------------------------------------------------

def build_relationship_extraction_prompt(target_lang: str, source_lang: str = "Chinese") -> str:
    """Build the system prompt for character relationship extraction."""
    novel_desc = f"{source_lang} web novel" if source_lang != "Chinese" else "Chinese web novel"
    forbidden_lang = "Korean or Chinese" if source_lang == "Korean" else "Chinese"
    return (
        f"You are an expert literary analyst mapping out character relationships in a {novel_desc}.\n"
        "Task: Identify any interpersonal relationships, factions, or affiliations between characters mentioned in the text.\n"
        "Format your output STRICTLY as a JSON array of objects, with no markdown formatting or extra text.\n"
        f"CRITICAL: For 'source', 'target', 'type', and 'notes' fields, you MUST write ALL values in {target_lang}. "
        f"NEVER output {forbidden_lang} characters in any field. The audience reads {target_lang} only.\n"
        'Example:\n[\\n  {"source": "Character A", "target": "Character B", "type": "Master & Disciple", '
        '"notes": "Character A learns from Character B"}\\n]\n'
        "If no relationships are found, output an empty array: []"
    )


# ---------------------------------------------------------------------------
# Genre Detection Utility
# ---------------------------------------------------------------------------

def detect_primary_genre(genres_str: str | None, tags_str: str | None = None) -> str:
    """
    Detect the primary genre from a thread's genres/tags string.
    Returns one of the GENRE_PROMPT_FRAGMENTS keys, or 'default'.
    """
    if not genres_str and not tags_str:
        return "default"

    combined = f"{genres_str or ''} {tags_str or ''}".lower()

    # Check each genre's keywords against the combined text
    for genre_key, keywords in GENRE_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in combined:
                return genre_key

    return "default"
