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

def build_core_translation_guidelines(lang_name: str, genre: str = "default") -> str:
    """Build the core translation guidelines prompt for chapter translation."""

    genre_fragment = GENRE_PROMPT_FRAGMENTS.get(genre, GENRE_PROMPT_FRAGMENTS["default"])

    return f"""TRANSLATION TASK - CRITICAL OUTPUT LANGUAGE: You MUST write the final translation of the story in {lang_name} only. No Chinese characters or pinyin allowed in the story output. (Exception: You MAY use Chinese characters in the Translator Notes at the very end if requested).

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
Do NOT leave any Chinese characters or raw pinyin in the main story text.
DO NOT embed inline dictionary parens, bilingual annotations, or explanation notes anywhere in the story (e.g. NEVER output 'ChineseTerm (English translation)', '(lust fluid)', or '[1] Footnote').
DO NOT output any Footnotes or Translator Notes section. Output ONLY the pure translated story text.

Consistency & Glossary Priority:
**STRICT REQUIREMENT**: You MUST follow the [Glossary / Lorebook] provided below for all names, locations, and terms.
- The Glossary is the ABSOLUTE LAW for this translation.
- Even if a term has similar pinyin to something else, or if you think a different word fits better, you MUST use the exact translation from the Glossary.
- Do NOT hallucinate or change established translations.

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
**ZERO TOLERANCE**: DO NOT include any term in "Translator Notes" that does not appear in the current chapter text. DO NOT mention terms to say they are "not present". If it's not in the chapter, it MUST NOT be in the notes.
After the chapter, if needed, add a section starting EXACTLY with the phrase "### TRANSLATOR NOTES:" for NEW terms (names, items, etc.) FOUND IN THIS CHAPTER.
**FORMAT**: You MUST use this exact format: '- Original Chinese Term → Translated Term (Brief notes tentang istilah tersebut)'.
Do NOT include terms from the Style Reference examples unless they are in the chapter.
If no new terms, skip.
STOP GENERATING immediately after you finish the Translator Notes list. Do NOT output anything else.
"""
    else:
        return """
Do NOT output any Translator Notes. STOP GENERATING immediately after the story ends. Do NOT output anything else.
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

def build_title_translation_prompt(target_lang: str) -> str:
    """Build the system prompt for batch title translation."""
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
        f"You are a professional literary translator specializing in {target_lang}. "
        "Translate the following novel synopsis/description accurately and elegantly. "
        "Ensure the translation is natural and highly readable, retaining the original meaning and tone.\n\n"
        "CRITICAL INSTRUCTION: Output ONLY the direct translated synopsis text. "
        "Do NOT include any conversational text, options, translation notes, or greetings. "
        "Do NOT say 'Here are a few ways to translate this synopsis'. "
        "Just provide the single best translation."
    )


# ---------------------------------------------------------------------------
# Glossary Extraction Prompt (used by context_engine.py)
# ---------------------------------------------------------------------------

def build_glossary_extraction_prompt(target_lang: str) -> str:
    """Build the system prompt for dedicated glossary extraction pass."""
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
        "\nFormat your output EXACTLY starting with the header '### TRANSLATOR NOTES:', "
        "followed by a list like this:\n"
        "### TRANSLATOR NOTES:\n"
        f"- 原本术语 → Translated Term ({target_lang} context explicitly stating relationships/affiliations)\n"
        "\nExamples of GOOD entries:\n"
        "- 宁凡 → Ning Fan (Protagonist, a reincarnated cultivator who was formerly a mortal scholar)\n"
        "- 天云宗 → Heavenly Cloud Sect (Rival sect located in the Northern Region, enemies of the protagonist's faction)\n"
        "- 破天剑 → Heaven-Splitting Sword (Ancient artifact wielded by the sect master, capable of cutting through spatial barriers)\n"
        "\nExamples of BAD entries (DO NOT do this):\n"
        "- 宁凡 → Ning Fan (A character)  ← TOO VAGUE\n"
        "- 天云宗 → Heavenly Cloud Sect   ← MISSING CONTEXT PARENTHESES\n"
        "- 破天剑 → Heaven-Splitting Sword (An ancient artifact).  ← TRAILING PERIOD AFTER )\n"
        "\nIf no important terms, output: '### TRANSLATOR NOTES:\\nNo new terms found.'"
    )


# ---------------------------------------------------------------------------
# Relationship Extraction Prompt (used by context_engine.py)
# ---------------------------------------------------------------------------

def build_relationship_extraction_prompt(target_lang: str) -> str:
    """Build the system prompt for character relationship extraction."""
    return (
        "You are an expert literary analyst mapping out character relationships in a Chinese web novel.\n"
        "Task: Identify any interpersonal relationships, factions, or affiliations between characters mentioned in the text.\n"
        "Format your output STRICTLY as a JSON array of objects, with no markdown formatting or extra text.\n"
        f"CRITICAL: For 'source', 'target', 'type', and 'notes' fields, you MUST write ALL values in {target_lang}. "
        f"NEVER output Chinese characters in any field. The audience reads {target_lang} only.\n"
        'Example:\n[\\n  {"source": "Ning Fan", "target": "Old Demon", "type": "Master & Disciple", '
        '"notes": "Ning Fan learns cultivation from the old demon"}\\n]\n'
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
