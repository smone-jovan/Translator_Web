import asyncio
from unittest.mock import AsyncMock, patch
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from database import Base, Thread, Chapter, LorebookEntry, GlobalSetting, CharacterRelationship
from services.context_engine import ContextEngine
from services.ai.settings import resolve_active_base_url, resolve_active_model
from routers.lorebook import create_lorebook_entry, create_lorebook_entries_bulk, LorebookCreate, LorebookBulkCreate
from routers.context import extract_thread_context, ExtractRequest, _sample_chapter_text


def _make_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_auto_save_glossary_and_create_entry_do_not_self_evict_when_at_limit():
    """
    When a thread already has max_context_terms (e.g. 5) active entries with usage_count >= 2,
    adding a new term via auto_save_glossary or create_lorebook_entry must NOT immediately
    archive the newly added term or wipe the notes of evicted entries.
    """
    db = _make_memory_db()
    gs = GlobalSetting(max_context_terms=5)
    thread = Thread(id=1, title="Cultivation Novel", original_title="修仙小说")
    db.add_all([gs, thread])
    db.commit()

    for i in range(1, 6):
        db.add(
            LorebookEntry(
                thread_id=1,
                original_term=f"旧词{i}",
                translated_term=f"OldTerm{i}",
                notes=f"Important note for term {i}",
                usage_count=3 + i,
                is_locked=False,
                is_archived=False,
            )
        )
    db.commit()

    raw_output = (
        "Isi cerita bab 10.\n\n"
        "### TRANSLATOR NOTES:\n"
        "- 萧炎 (Xiao Yan) → Xiao Yan (MALE — Protagonist dari Klan Xiao)\n"
    )
    ContextEngine.auto_save_glossary(db, 1, raw_output)

    xiao_yan = db.execute(
        select(LorebookEntry).where(LorebookEntry.thread_id == 1, LorebookEntry.original_term == "萧炎")
    ).scalar_one_or_none()
    assert xiao_yan is not None
    assert xiao_yan.is_archived is False
    assert xiao_yan.usage_count >= 1
    assert xiao_yan.gender == "MALE"

    evicted = db.execute(
        select(LorebookEntry).where(LorebookEntry.thread_id == 1, LorebookEntry.original_term == "旧词1")
    ).scalar_one()
    assert evicted.is_archived is True
    assert evicted.notes == "Important note for term 1"

    restored = ContextEngine.reactivate_referenced_archived_terms(db, 1, "在这一章中，旧词1再次出现了。")
    assert restored == 1
    db.refresh(evicted)
    assert evicted.is_archived is False
    assert evicted.notes == "Important note for term 1"

    manual_entry = create_lorebook_entry(
        thread_id=1,
        body=LorebookCreate(original_term="魂殿", translated_term="Aula Jiwa", notes="Organisasi antagonis utama"),
        db=db,
    )
    assert manual_entry.is_archived is False
    assert manual_entry.notes == "Organisasi antagonis utama"
    db.close()


def test_auto_save_glossary_ignores_think_blocks_and_mid_story_words_and_validates_pinyin():
    db = _make_memory_db()
    db.add(Thread(id=1, title="Test"))
    db.commit()

    ai_text = (
        "<think>\n"
        "### TRANSLATOR NOTES:\n"
        "- 假词 → FakeThoughtTerm (Should never be saved because it is inside think block)\n"
        "</think>\n"
        "Dia membuka glossary kuno itu sambil membaca new terms dari kontrak serikat.\n"
        "Status: Aktif\n\n"
        "### TRANSLATOR NOTES:\n"
        "1. **성진우 (Sung Jin-woo)** → Sung Jin-woo (MALE — Protagonist, Hunter peringkat S)\n"
        "2) **헌터 협会** → Asosiasi Hunter (Organisasi resmi pengatur Gate)\n"
        "- Sung Jin-woo → Sung Jin-woo (MALE — Protagonist)\n"
        "- Status → Status (kondisi pemain)\n"
        "- Level → Level (tingkat kekuatan)\n"
    )
    ContextEngine.auto_save_glossary(db, 1, ai_text)

    entries = db.execute(select(LorebookEntry).where(LorebookEntry.thread_id == 1)).scalars().all()
    by_orig = {e.original_term: e for e in entries}

    assert "假词" not in by_orig
    assert "Status" not in by_orig
    assert "Level" not in by_orig
    assert "성진우" in by_orig
    assert by_orig["성진우"].translated_term == "Sung Jin-woo"
    assert by_orig["성진우"].gender == "MALE"
    assert "헌터 협会" in by_orig
    assert by_orig["헌터 협会"].gender is None
    assert "Sung Jin-woo" in by_orig
    db.close()


def test_strip_translator_notes_preserves_story_paragraphs_starting_with_notes_or_glossary():
    story = (
        "Paragraf pertama cerita.\n\n"
        "New terms of the treaty were discussed by the elders in the main hall.\n\n"
        "Notes left by the ancient emperor revealed the secret realm.\n\n"
        "Paragraf terakhir cerita yang sangat penting.\n\n"
        "### TRANSLATOR NOTES:\n"
        "- 秘境 → Alam Rahasia (Dimensi tersembunyi)"
    )
    cleaned = ContextEngine.strip_translator_notes(story)
    assert "New terms of the treaty were discussed" in cleaned
    assert "Notes left by the ancient emperor" in cleaned
    assert "Paragraf terakhir cerita yang sangat penting." in cleaned
    assert "Alam Rahasia" not in cleaned


def test_build_translation_prompt_prioritizes_compound_terms_and_injects_relationships_and_indo_gender():
    db = _make_memory_db()
    db.add(GlobalSetting(max_context_terms=50, target_language="Indonesian"))
    db.add(Thread(id=1, title="Test", genres="Xianxia"))
    db.add_all([
        LorebookEntry(
            thread_id=1,
            original_term="天云",
            translated_term="Tianyun",
            usage_count=20,
            is_locked=False,
            is_archived=False,
        ),
        LorebookEntry(
            thread_id=1,
            original_term="天云宗大长老",
            translated_term="Tetua Agung Sekte Awan Langit",
            usage_count=1,
            is_locked=False,
            is_archived=False,
        ),
        LorebookEntry(
            thread_id=1,
            original_term="罗毅 (Luo Yi / Luoyi)",
            translated_term="Luo Yi",
            gender="MALE",
            notes="Protagonis utama",
            usage_count=2,
            is_locked=False,
            is_archived=False,
        ),
        CharacterRelationship(
            thread_id=1,
            source_term="Luo Yi",
            target_term="Tetua Agung Sekte Awan Langit",
            relationship_type="Murid & Guru",
            notes="Luo Yi menghormati Tetua Agung sebagai guru kultivasinya",
        ),
    ])
    db.commit()

    prompt = ContextEngine.build_translation_prompt(
        db=db,
        thread_id=1,
        target_lang="Indonesian",
        original_text="罗毅拜见了天云宗大长老。",
        translation_mode="quality",
    )

    assert "Tetua Agung Sekte Awan Langit" in prompt
    assert "Luo Yi" in prompt
    assert "[CHARACTER RELATIONSHIPS & HIERARCHY]:" in prompt
    assert "Luo Yi → Tetua Agung Sekte Awan Langit: Murid & Guru" in prompt
    assert "Tuan Muda, Putra" in prompt
    assert "NEVER leak English pronouns (he/she/him/her)" in prompt
    db.close()


def test_extract_context_router_object_scoped_fallback_and_existing_filtering():
    db = _make_memory_db()
    db.add(GlobalSetting(llm_provider="gemini", gemini_model="gemini-2.5-flash", target_language="Indonesian"))
    db.add(Thread(id=1, title="Test Novel"))
    db.add(
        Chapter(
            id=1,
            thread_id=1,
            order=0,
            title_original="第1章",
            content_original=("Awal bab tentang 萧炎. " * 40) + ("Tengah bab tentang 云韵. " * 40) + ("Akhir bab tentang 魂殿. " * 40),
        )
    )
    db.add(LorebookEntry(thread_id=1, original_term="萧炎", translated_term="Xiao Yan", usage_count=5))
    db.commit()

    sampled = _sample_chapter_text(db.get(Chapter, 1).content_original, 600)
    assert "Awal bab" in sampled and "Tengah bab" in sampled and "Akhir bab" in sampled

    mock_llm_output = (
        "Berikut hasil ekstraksi [Bab 1]:\n"
        '[\n'
        '  {"original_term": "萧炎", "translated_term": "Xiao Yan", "notes": "Tokoh utama", "gender": "MALE"},\n'
        '  {"original_term": "魂殿", "translated_term": "Aula Jiwa", "notes": "Organisasi jahat", "gender": null},\n'
        '  {"original_term": "云韵 (Yun Yun)", "translated_term": "Yun Yun", "notes": "Ketua Sekte Yunlan", "gender": "FEMALE"}\n'
        ']'
    )

    mock_provider = AsyncMock()
    mock_provider.chat_completion = AsyncMock(return_value=mock_llm_output)

    with patch("routers.context.AIProviderFactory.get_provider", return_value=mock_provider):
        res = asyncio.run(extract_thread_context(1, ExtractRequest(lm_url="http://localhost:1234"), db=db))

    terms = res["terms"]
    by_orig = {t["original_term"]: t for t in terms}

    assert "萧炎" not in by_orig
    assert "魂殿" in by_orig
    assert by_orig["魂殿"]["gender"] is None
    assert "云韵" in by_orig
    assert by_orig["云韵"]["gender"] == "FEMALE"
    db.close()


def test_resolve_active_base_url_guards_cloud_providers_against_localhost():
    gs = GlobalSetting(
        llm_provider="gemini",
        lm_url="http://localhost:1234",
    )
    assert resolve_active_base_url(gs, "http://localhost:1234") == "https://generativelanguage.googleapis.com/v1beta/openai"

    gs.llm_provider = "openrouter"
    assert resolve_active_base_url(gs, "http://127.0.0.1:1234") == "https://openrouter.ai/api/v1"

    gs.llm_provider = "openai"
    assert resolve_active_base_url(gs, "http://localhost:1234") == "https://api.openai.com/v1"

    gs.llm_provider = "lm_studio"
    assert resolve_active_base_url(gs, "http://192.168.1.10:1234") == "http://192.168.1.10:1234"


def test_bulk_lorebook_endpoint_saves_and_protects_all_entries():
    db = _make_memory_db()
    db.add(GlobalSetting(max_context_terms=3))
    db.add(Thread(id=1, title="Test"))
    db.commit()

    bulk_res = create_lorebook_entries_bulk(
        thread_id=1,
        body=LorebookBulkCreate(
            entries=[
                LorebookCreate(original_term="林动", translated_term="Lin Dong", notes="Protagonis", gender="MALE"),
                LorebookCreate(original_term="绫清竹", translated_term="Ling Qingzhu", notes="Heroine", gender="FEMALE"),
            ],
            is_locked=True,
        ),
        db=db,
    )
    assert len(bulk_res) == 2
    assert all(e.is_locked is True and e.is_archived is False for e in bulk_res)
    db.close()
