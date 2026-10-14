import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base, Thread, Chapter, UserBookmark, GlobalSetting
from services.ai.settings import resolve_active_model
from routers.threads import delete_chapter


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    t = Thread(id=1, original_title="Novel 1", title="Novel 1")
    session.add(t)

    ch1 = Chapter(id=101, thread_id=1, order=1, title_original="Ch 1", content_original="Text 1")
    ch2 = Chapter(id=102, thread_id=1, order=2, title_original="Ch 2", content_original="Text 2")
    ch3 = Chapter(id=103, thread_id=1, order=3, title_original="Ch 3", content_original="Text 3")
    session.add_all([ch1, ch2, ch3])

    bm = UserBookmark(id=1, thread_id=1, chapter_id=102, scroll_progress=45.0)
    session.add(bm)
    session.commit()

    yield session
    session.close()


def test_resolve_active_model_openrouter_guards_local_models():
    class DummySettings:
        llm_provider = "openrouter"
        openrouter_model = "deepseek/deepseek-chat"
        lm_model = "qwen2.5-7b-instruct"

    gs = DummySettings()
    # A local LM Studio model without author/model slash should be ignored
    assert resolve_active_model(gs, requested_model="qwen2.5-7b-instruct") == "deepseek/deepseek-chat"
    assert resolve_active_model(gs, requested_model="local-model") == "deepseek/deepseek-chat"
    # A genuine OpenRouter model with a slash should be accepted
    assert resolve_active_model(gs, requested_model="openai/gpt-4o") == "openai/gpt-4o"
    # When no model requested, use openrouter_model
    assert resolve_active_model(gs, requested_model=None) == "deepseek/deepseek-chat"


def test_delete_chapter_preserves_bookmark_to_nearest_chapter(test_db):
    # Currently bookmark is on chapter 102 (order 2)
    # Deleting chapter 102 should move the bookmark to chapter 101 (order 1)
    res = delete_chapter(thread_id=1, chapter_id=102, db=test_db)
    assert res["status"] == "deleted"

    bm = test_db.query(UserBookmark).filter_by(thread_id=1).first()
    assert bm is not None
    assert bm.chapter_id == 101
    assert bm.scroll_progress == 0.0

    # Chapter 103 (was order 3) should now be re-sequenced to order 2
    ch3 = test_db.query(Chapter).filter_by(id=103).first()
    assert ch3.order == 2

    # Thread chapters count should be 2
    thread = test_db.query(Thread).filter_by(id=1).first()
    assert len(thread.chapters) == 2
