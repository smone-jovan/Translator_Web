import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, Thread, Chapter, LorebookEntry, GlobalSetting, CharacterRelationship
from routers.lorebook import (
    list_lorebook,
    get_lorebook_stats,
    create_lorebook_entry,
    update_lorebook_entry,
    delete_lorebook_entry,
    toggle_lorebook_lock,
    toggle_lorebook_archive,
    bulk_lorebook_action,
    apply_preset as router_apply_preset,
    enforce_context_limit,
    LorebookCreate,
    LockToggle,
    ArchiveToggle,
    LorebookBulkRequest,
    PresetApplyRequest,
)
from routers.relationships import (
    get_relationships,
    create_relationship,
    update_relationship,
    delete_relationship,
    clear_thread_relationships,
    RelationshipCreate,
    RelationshipUpdate,
)
from routers.settings import (
    get_global_context,
    update_settings,
    GlobalSettingsUpdate,
)
from routers.threads import (
    get_thread,
    get_thread_context,
    save_thread_context,
    update_chapter_translation,
    reapply_glossary_chapter,
    reapply_glossary_thread,
    TranslationUpdate,
)
from services.genre_presets import list_presets, apply_preset


@pytest.fixture
def db_session(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    monkeypatch.setattr("routers.settings.load_secrets", lambda: {
        "openai_api_key": "",
        "gemini_api_key": "",
        "openrouter_api_key": "",
        "novalpie_cookie": "",
    })
    monkeypatch.setattr("routers.settings.save_secrets", lambda **kwargs: None)

    yield session
    session.close()


def test_bidirectional_enforce_context_limit_and_notes_preservation(db_session):
    gs = GlobalSetting(max_context_terms=2, target_language="Indonesian", translation_mode="quality")
    t = Thread(id=1, title="Test Cultivation", original_title="测试")
    db_session.add_all([gs, t])
    db_session.commit()

    e1 = create_lorebook_entry(1, LorebookCreate(original_term="林动", translated_term="Lin Dong", notes="Protagonis utama"), db=db_session)
    e2 = create_lorebook_entry(1, LorebookCreate(original_term="青檀", translated_term="Qingtan", notes="Adik perempuan Lin Dong"), db=db_session)
    db_e2 = db_session.get(LorebookEntry, e2.id)
    db_e2.usage_count = 10
    db_session.commit()

    e3 = create_lorebook_entry(1, LorebookCreate(original_term="小貂", translated_term="Xiao Diao", notes="Roh Marten Langit"), db=db_session)

    active = list_lorebook(1, include_archived=False, db=db_session)
    assert len(active) == 2

    all_entries = list_lorebook(1, include_archived=True, db=db_session)
    assert len(all_entries) == 3
    archived_e1 = next(x for x in all_entries if x.original_term == "林动")
    assert archived_e1.is_archived is True
    assert archived_e1.notes == "Protagonis utama"

    update_settings(GlobalSettingsUpdate(max_context_terms=5), db=db_session)

    active_after_expand = list_lorebook(1, include_archived=False, db=db_session)
    assert len(active_after_expand) == 3
    restored_e1 = next(x for x in active_after_expand if x.original_term == "林动")
    assert restored_e1.is_archived is False
    assert restored_e1.notes == "Protagonis utama"

    update_settings(GlobalSettingsUpdate(max_context_terms=2), db=db_session)
    assert len(list_lorebook(1, include_archived=False, db=db_session)) == 2

    delete_lorebook_entry(e3.id, db=db_session)
    active_after_delete = list_lorebook(1, include_archived=False, db=db_session)
    assert len(active_after_delete) == 2
    assert {x.original_term for x in active_after_delete} == {"林动", "青檀"}


def test_lorebook_stats_and_bulk_operations(db_session):
    gs = GlobalSetting(max_context_terms=50, target_language="Indonesian", translation_mode="fast")
    t = Thread(id=1, title="Bulk Novel", original_title="批量")
    db_session.add_all([gs, t])
    db_session.commit()

    bulk_lorebook_action(
        1,
        LorebookBulkRequest(
            action="import",
            entries=[
                LorebookCreate(original_term="萧炎", translated_term="Xiao Yan", gender="MALE", notes="MALE — Tokoh utama"),
                LorebookCreate(original_term="薰儿", translated_term="Xun'er", gender="FEMALE", notes="FEMALE — Tokoh wanita"),
            ],
        ),
        db=db_session,
    )
    garbage = LorebookEntry(thread_id=1, original_term="Final List", translated_term="12345", is_locked=False)
    db_session.add(garbage)
    db_session.commit()

    stats = get_lorebook_stats(1, db=db_session)
    assert stats["total_count"] == 3
    assert stats["male_count"] == 1
    assert stats["female_count"] == 1
    assert stats["translation_mode"] == "fast"
    assert stats["effective_prompt_limit"] == 10

    clean_res = bulk_lorebook_action(1, LorebookBulkRequest(action="clean_garbage"), db=db_session)
    assert clean_res["affected"] == 1
    assert get_lorebook_stats(1, db=db_session)["total_count"] == 2

    remaining = list_lorebook(1, include_archived=True, db=db_session)
    ids = [e.id for e in remaining]
    bulk_lorebook_action(1, LorebookBulkRequest(action="lock", entry_ids=[ids[0]]), db=db_session)
    assert db_session.get(LorebookEntry, ids[0]).is_locked is True

    toggle_lorebook_archive(ids[1], ArchiveToggle(is_archived=True), db=db_session)
    assert db_session.get(LorebookEntry, ids[1]).is_archived is True
    toggle_lorebook_archive(ids[1], ArchiveToggle(is_archived=False), db=db_session)
    assert db_session.get(LorebookEntry, ids[1]).is_archived is False


def test_bilingual_genre_presets_indonesian_and_english(db_session):
    t_en = Thread(id=1, title="English Cultivation")
    t_id = Thread(id=2, title="Indonesian Cultivation")
    gs = GlobalSetting(target_language="Indonesian", max_context_terms=150)
    db_session.add_all([t_en, t_id, gs])
    db_session.commit()

    res_en = apply_preset(db_session, 1, "xianxia")
    assert res_en["language"] == "English"
    jindan_en = db_session.query(LorebookEntry).filter_by(thread_id=1, original_term="金丹").first()
    assert jindan_en is not None
    assert "Core" in jindan_en.translated_term

    res_id = router_apply_preset(2, "xianxia", body=PresetApplyRequest(lock_entries=False), db=db_session)
    assert res_id["language"] == "Indonesian"
    jindan_id = db_session.query(LorebookEntry).filter_by(thread_id=2, original_term="金丹").first()
    shixiong_id = db_session.query(LorebookEntry).filter_by(thread_id=2, original_term="师兄").first()
    assert jindan_id is not None
    assert "Inti Emas" in jindan_id.translated_term
    assert jindan_id.is_locked is False
    assert shixiong_id.translated_term == "Kakak Senior"


def test_relationships_full_crud(db_session):
    t = Thread(id=1, title="Rel Novel")
    db_session.add(t)
    db_session.commit()

    r1 = create_relationship(
        1,
        RelationshipCreate(source_term="Xiao Yan", target_term="Yao Lao", relationship_type="Master-Disciple", notes="Guru cincin"),
        db=db_session,
    )
    assert r1.id is not None
    assert r1.relationship_type == "Master-Disciple"

    r1_dup = create_relationship(
        1,
        RelationshipCreate(source_term="xiao yan", target_term="yao lao", relationship_type="Guru & Murid", notes="Diperbarui"),
        db=db_session,
    )
    assert r1_dup.id == r1.id
    assert r1_dup.relationship_type == "Guru & Murid"

    r1_upd = update_relationship(
        r1.id,
        RelationshipUpdate(relationship_type="Mentor", notes="Sangat dekat"),
        db=db_session,
    )
    assert r1_upd.relationship_type == "Mentor"
    assert r1_upd.notes == "Sangat dekat"

    assert len(get_relationships(1, db=db_session)) == 1
    clear_res = clear_thread_relationships(1, db=db_session)
    assert clear_res["deleted_count"] == 1
    assert len(get_relationships(1, db=db_session)) == 0


def test_threads_style_guide_and_reapply_glossary_titles(db_session):
    gs = GlobalSetting(always_hide_thoughts=1, target_language="Indonesian")
    t = Thread(id=1, title="Novel Style", style_guide="Gunakan bahasa baku.", thread_context="Dunia kultivasi.")
    ch = Chapter(
        id=10,
        thread_id=1,
        order=0,
        title_original="第一章 青阳镇",
        title_translated="Bab 1: Kota Qingyang",
        content_original="青阳镇的林动。",
        content_translated="Di Kota Qingyang, Lin Dong berlatih.",
        translation_status="idle",
    )
    db_session.add_all([gs, t, ch])
    db_session.commit()

    detail = get_thread(1, db=db_session)
    assert detail.style_guide == "Gunakan bahasa baku."
    assert detail.thread_context == "Dunia kultivasi."

    create_lorebook_entry(
        1,
        LorebookCreate(original_term="林动", translated_term="Lin Dong Sang Pendekar", is_locked=True),
        db=db_session,
    )
    ch.title_translated = "Bab 1: Kemunculan Lin Dong"
    db_session.commit()

    sync_res = reapply_glossary_thread(1, db=db_session)
    assert sync_res["chapters_updated"] == 1
    db_session.refresh(ch)
    assert "Lin Dong Sang Pendekar" in ch.title_translated
    assert "Lin Dong Sang Pendekar" in ch.content_translated

    ch.translation_status = "idle"
    db_session.commit()
    update_chapter_translation(
        1,
        10,
        TranslationUpdate(translated_text="<think>Draft</think>\n\nLin Dong tersenyum di hadapan musuhnya."),
        db=db_session,
    )
    db_session.refresh(ch)
    assert ch.translation_status == "done"
    assert "<think>" not in ch.content_translated
    assert "Lin Dong Sang Pendekar" in ch.content_translated
