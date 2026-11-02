import pytest
from services.txt_importer import (
    decode_txt_bytes,
    parse_txt_to_drafts,
    count_words,
    TxtDecodeError,
    TxtInvalidContentError,
    ParsedDraft,
)

def test_decode_txt_bytes_utf8_bom():
    raw = "\ufeffHello UTF-8 BOM Novel".encode("utf-8")
    decoded = decode_txt_bytes(raw)
    assert decoded == "Hello UTF-8 BOM Novel"

def test_decode_txt_bytes_utf8_standard():
    raw = "Standard UTF-8 text with é accents and emojis 📖".encode("utf-8")
    assert decode_txt_bytes(raw) == "Standard UTF-8 text with é accents and emojis 📖"

def test_decode_txt_bytes_gb18030():
    text = "第一章 远方的故事"
    raw = text.encode("gb18030")
    assert decode_txt_bytes(raw) == text

def test_decode_txt_bytes_big5():
    text = "第一章 遠方的故事"
    raw = text.encode("big5")
    assert decode_txt_bytes(raw) == text

def test_decode_txt_bytes_shift_jis():
    text = "第1章 始まりの場所"
    raw = text.encode("shift_jis")
    assert decode_txt_bytes(raw) == text

def test_decode_txt_bytes_rejects_undecodable():
    # Sequence of invalid bytes that cannot be decoded as utf-8, gb18030, big5, or shift_jis
    # 0x80 alone is invalid in utf-8, and in gb18030/big5/shift_jis high bytes require valid trail bytes
    # A single byte 0xff or 0x80 repeated oddly:
    raw = b"\xff\xfe\xff\xfe\x00\x00\xff\x80\x81"
    # Wait, 0x00 is NUL, let's test undecodable without NUL:
    raw_no_nul = b"\x81\x01\x81\x02\xff\xff\x80"
    with pytest.raises(TxtDecodeError):
        decode_txt_bytes(raw_no_nul)

def test_decode_txt_bytes_rejects_nul():
    raw = b"Chapter 1\x00Corrupted text"
    with pytest.raises(TxtInvalidContentError, match="NUL"):
        decode_txt_bytes(raw)

def test_decode_txt_bytes_rejects_empty_or_whitespace():
    with pytest.raises(TxtInvalidContentError, match="empty|whitespace"):
        decode_txt_bytes(b"")
    with pytest.raises(TxtInvalidContentError, match="empty|whitespace"):
        decode_txt_bytes(b"   \r\n\t  \n  ")

def test_crlf_normalization():
    text = "Chapter 1\r\nLine 1\r\n\r\nLine 2\r\n"
    drafts = parse_txt_to_drafts(text)
    assert len(drafts) == 1
    assert drafts[0].title == "Chapter 1"
    assert "\r" not in drafts[0].body
    assert drafts[0].body == "Line 1\n\nLine 2"

def test_supported_heading_families():
    content = """Chapter 1: The Beginning
It was a dark and stormy night.

Ch. 2: The Return
He returned to the city.

Bab 3: Langkah Pertama
Langkah demi langkah dijalani.

Bab 4
Perjalanan berlanjut.

第5章 天地之间
万物复苏，春意盎然。

第6节 隐秘的线索
线索逐渐明朗。

第7回 决战时刻
英雄现身。

第8卷 终章序幕
故事走向高潮。
"""
    drafts = parse_txt_to_drafts(content)
    assert len(drafts) == 8
    assert drafts[0].title == "Chapter 1: The Beginning"
    assert drafts[1].title == "Ch. 2: The Return"
    assert drafts[2].title == "Bab 3: Langkah Pertama"
    assert drafts[3].title == "Bab 4"
    assert drafts[4].title == "第5章 天地之间"
    assert drafts[5].title == "第6节 隐秘的线索"
    assert drafts[6].title == "第7回 决战时刻"
    assert drafts[7].title == "第8卷 终章序幕"

def test_preface_preservation_as_prologue():
    content = """This is the preface text.
Before any chapter was written, there was an ancient world.

Chapter 1
Now the true journey begins.
"""
    drafts = parse_txt_to_drafts(content)
    assert len(drafts) == 2
    assert drafts[0].title == "Prologue"
    assert "This is the preface text." in drafts[0].body
    assert "ancient world" in drafts[0].body
    assert drafts[0].source_chapter_ordinal == 1
    assert drafts[1].title == "Chapter 1"
    assert drafts[1].body == "Now the true journey begins."
    assert drafts[1].source_chapter_ordinal == 2

def test_no_heading_fallback_single_chapter():
    content = """A tale without chapters.
Just pure prose drifting through the pages.

Second paragraph of the tale.
"""
    drafts = parse_txt_to_drafts(content)
    assert len(drafts) == 1
    assert drafts[0].title == "Chapter 1"
    assert drafts[0].body == "A tale without chapters.\nJust pure prose drifting through the pages.\n\nSecond paragraph of the tale."
    assert drafts[0].source_chapter_ordinal == 1
    assert drafts[0].split_ordinal == 1
    assert drafts[0].split_total == 1

def test_false_looking_inline_text():
    content = """Chapter 1: A Real Chapter
Yesterday, he recalled that Chapter 12 was his lucky number.
Also, in Bab 3 there was a mention of something else.
Furthermore,第4章was mentioned in the conversation without being at the line boundary.
He continued reading peacefully.

Chapter 2: The Next Real Chapter
This is indeed the second chapter.
"""
    drafts = parse_txt_to_drafts(content)
    assert len(drafts) == 2
    assert drafts[0].title == "Chapter 1: A Real Chapter"
    assert "Chapter 12 was his lucky number" in drafts[0].body
    assert "Bab 3 there was a mention" in drafts[0].body
    assert "第4章was mentioned" in drafts[0].body
    assert drafts[1].title == "Chapter 2: The Next Real Chapter"
    assert drafts[1].body == "This is indeed the second chapter."

def test_no_lost_or_duplicated_body_text_and_split():
    # Create paragraphs totaling > 6000 words to force a split
    para1 = "Word " * 3500
    para2 = "Second " * 3500
    content = f"Chapter 1\n{para1.strip()}\n\n{para2.strip()}"
    drafts = parse_txt_to_drafts(content)
    
    assert len(drafts) == 2
    assert drafts[0].title == "Chapter 1 — Part 1/2"
    assert drafts[0].split_ordinal == 1
    assert drafts[0].split_total == 2
    assert drafts[0].source_chapter_ordinal == 1
    
    assert drafts[1].title == "Chapter 1 — Part 2/2"
    assert drafts[1].split_ordinal == 2
    assert drafts[1].split_total == 2
    assert drafts[1].source_chapter_ordinal == 1

    # Concatenating split bodies by '\n\n' preserves the source body perfectly
    reconstructed_body = "\n\n".join(d.body for d in drafts)
    expected_body = f"{para1.strip()}\n\n{para2.strip()}"
    assert reconstructed_body == expected_body
    
    # Heading line text is NOT duplicated in body
    assert "Chapter 1" not in drafts[0].body
    assert "Chapter 1" not in drafts[1].body

def test_unbreakable_oversized_paragraph():
    # A single paragraph with > 6000 words cannot be split without breaking the paragraph
    oversized_para = "SingleLongParagraph " * 7000
    content = f"Chapter 99: Epic\n{oversized_para.strip()}"
    drafts = parse_txt_to_drafts(content)

    assert len(drafts) == 1
    assert drafts[0].title == "Chapter 99: Epic"
    assert drafts[0].is_oversized is True
    assert drafts[0].word_count > 6000
    assert drafts[0].body == oversized_para.strip()

def test_cjk_fullwidth_and_webnovel_headings():
    content = """Ch 1 No Dot Heading
Body 1

第１章 全角数字章节
内容1

第１２話 日本語ウェブ小説話数
内容2

第一部 大陆风云
内容3
"""
    drafts = parse_txt_to_drafts(content)
    assert len(drafts) == 4
    assert drafts[0].title == "Ch 1 No Dot Heading"
    assert drafts[1].title == "第１章 全角数字章节"
    assert drafts[2].title == "第１２話 日本語ウェブ小説話数"
    assert drafts[3].title == "第一部 大陆风云"

def test_count_words_cjk_punctuation():
    # Chinese sentence with commas, quotes, and exclamation
    cjk_text = "“你好，世界！这是一段测试文本。”"
    # Chinese chars: 你好世界这是一段测试文本 (12 chars).
    # Isolated punctuation must not inflate word count
    count = count_words(cjk_text)
    assert count == 12

def test_roman_numerals_strict_uppercase_and_avoid_lowercase_words():
    # Strict uppercase Roman numerals match
    content = """Chapter IV: The Battle
The battle begins here.

Chapter did not go as planned.
It was a surprise to everyone.
"""
    drafts = parse_txt_to_drafts(content)
    assert len(drafts) == 1
    assert drafts[0].title == "Chapter IV: The Battle"
    assert "Chapter did not go as planned." in drafts[0].body

def test_roman_numerals_avoid_civil_mix_ill():
    content = """Chapter 1
Some normal chapter.

Chapter civil disputes were common.
Chapter mix of elements happened.
Chapter ill tidings spread.
"""
    drafts = parse_txt_to_drafts(content)
    assert len(drafts) == 1
    assert drafts[0].title == "Chapter 1"
    assert "Chapter civil disputes" in drafts[0].body
    assert "Chapter mix of elements" in drafts[0].body
    assert "Chapter ill tidings" in drafts[0].body

def test_cjk_japanese_volume_kanji_and_traditional_numerals():
    content = """第1巻 始まりの場所
第1話 旅立ち
ここは日本風のウェブ小説の世界。

第萬章 萬古神帝
万代不灭。

第兩章 兩世為人
重活一世。
"""
    drafts = parse_txt_to_drafts(content)
    assert len(drafts) == 3
    # Japanese volume kanji 巻 merged into following chapter with body
    assert drafts[0].title == "第1巻 始まりの場所 — 第1話 旅立ち"
    assert drafts[0].body == "ここは日本風のウェブ小説の世界。"
    # Traditional numerals 萬 and 兩
    assert drafts[1].title == "第萬章 萬古神帝"
    assert drafts[2].title == "第兩章 兩世為人"

def test_empty_drafts_toc_list_filtering():
    content = """Table of Contents
Chapter 1: The Beginning
Chapter 2: The Forest
Chapter 3: The City

Chapter 1: The Beginning
The hero leaves the village on a bright morning.

Chapter 2: The Forest
The woods were dark, damp, and perilous.
"""
    drafts = parse_txt_to_drafts(content)
    # TOC items (Chapter 1, 2, 3 with empty bodies) must be filtered out so no empty drafts exist
    assert all(d.body.strip() != "" for d in drafts)
    titles = [d.title for d in drafts]
    assert "Prologue" in titles
    assert "Chapter 1: The Beginning" in titles
    assert "Chapter 2: The Forest" in titles
    assert len([t for t in titles if "Chapter 1: The Beginning" in t]) == 1

def test_consecutive_volume_and_chapter_heading_merging():
    content = """第1卷 魔法学院篇
第1章 新生入学
今天早晨天气晴朗，学院钟声响起。

第二部 诸神黄昏
第一卷 序章
第一章 觉醒
远古的神祇悄然复苏。
"""
    drafts = parse_txt_to_drafts(content)
    assert len(drafts) == 2
    assert drafts[0].title == "第1卷 魔法学院篇 — 第1章 新生入学"
    assert drafts[0].body == "今天早晨天气晴朗，学院钟声响起。"
    assert drafts[1].title == "第二部 诸神黄昏 — 第一卷 序章 — 第一章 觉醒"
    assert drafts[1].body == "远古的神祇悄然复苏。"

def test_all_empty_headings_raises_invalid_content_error():
    content = """Chapter 1

Chapter 2

Chapter 3
"""
    with pytest.raises(TxtInvalidContentError, match="no readable chapter content"):
        parse_txt_to_drafts(content)

def test_nested_volume_hierarchy_book_volume_part_chapter():
    content = """Book 1
Volume 1
Part 1
Chapter 1
This is the story of the ancient world.
"""
    drafts = parse_txt_to_drafts(content)
    assert len(drafts) == 1
    assert drafts[0].title == "Book 1 — Volume 1 — Part 1 — Chapter 1"
    assert drafts[0].body == "This is the story of the ancient world."

def test_toc_sibling_volumes_do_not_accumulate():
    content = """Volume 1: The Forest
Volume 2: The Sea

Volume 1: The Forest
Chapter 1
Body of chapter 1.
"""
    drafts = parse_txt_to_drafts(content)
    assert len(drafts) == 1
    assert drafts[0].title == "Volume 1: The Forest — Chapter 1"
    assert drafts[0].body == "Body of chapter 1."

def test_cjk_ideographic_zero_heading_and_volume():
    # Chapter with ideographic zero 〇 (\u3007), e.g. 第一〇章 (Chapter 10)
    content = """第一〇巻 终局篇
第一〇章 命运之轮
万物运转不息。
"""
    drafts = parse_txt_to_drafts(content)
    assert len(drafts) == 1
    assert drafts[0].title == "第一〇巻 终局篇 — 第一〇章 命运之轮"
    assert drafts[0].body == "万物运转不息。"

def test_indonesian_buku_bagian_jilid_headings():
    content = """Buku 1: Dunia Baru
Bagian 1: Awal Mula
Bab 1
Ini adalah kisah petualangan di tanah harapan.
"""
    drafts = parse_txt_to_drafts(content)
    assert len(drafts) == 1
    assert drafts[0].title == "Buku 1: Dunia Baru — Bagian 1: Awal Mula — Bab 1"
    assert drafts[0].body == "Ini adalah kisah petualangan di tanah harapan."


