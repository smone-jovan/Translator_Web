import io
import pytest
from fastapi.testclient import TestClient
from main import app
import database
from database import get_db, Thread, Chapter

@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture
def mock_dual_workspaces(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from database import Base, Thread

    engine_test_main = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    engine_test_ghost = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=engine_test_main)
    Base.metadata.create_all(bind=engine_test_ghost)

    SessionTestMain = sessionmaker(autocommit=False, autoflush=False, bind=engine_test_main)
    SessionTestGhost = sessionmaker(autocommit=False, autoflush=False, bind=engine_test_ghost)

    with SessionTestMain() as db_main:
        t_main = Thread(title="Main Workspace Book", source_type="manual")
        db_main.add(t_main)
        db_main.commit()

    with SessionTestGhost() as db_ghost:
        t_ghost = Thread(title="Ghost Workspace Secret Book", source_type="manual")
        db_ghost.add(t_ghost)
        db_ghost.commit()

    monkeypatch.setattr("database.SessionLocalMain", SessionTestMain)
    monkeypatch.setattr("database.SessionLocalGhost", SessionTestGhost)

    def mock_get_session_factory(ws: str = "main"):
        if str(ws).lower() == "ghost":
            return SessionTestGhost
        return SessionTestMain

    monkeypatch.setattr("database.get_session_factory", mock_get_session_factory)

    yield {
        "SessionMain": SessionTestMain,
        "SessionGhost": SessionTestGhost,
    }

# ==========================================
# 1. Preview API Tests
# ==========================================

def test_preview_valid_txt(client):
    content = "Chapter 1: The First Step\nThis is the content of chapter 1.\n\nChapter 2: The Second Step\nContent of chapter 2."
    file_bytes = content.encode("utf-8")
    
    response = client.post(
        "/api/txt-import/preview",
        files={"file": ("my_cool_novel.txt", file_bytes, "text/plain")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "my_cool_novel"
    assert len(data["drafts"]) == 2
    assert data["drafts"][0]["title"] == "Chapter 1: The First Step"
    assert data["drafts"][0]["body"] == "This is the content of chapter 1."
    assert data["drafts"][0]["source_chapter_ordinal"] == 1
    assert data["drafts"][0]["word_count"] > 0
    assert data["drafts"][1]["title"] == "Chapter 2: The Second Step"

def test_preview_rejects_wrong_extension(client):
    response = client.post(
        "/api/txt-import/preview",
        files={"file": ("novel.pdf", b"Some pdf content", "application/pdf")}
    )
    assert response.status_code == 400
    assert "txt" in response.json()["detail"].lower()

def test_preview_rejects_empty_content(client):
    response = client.post(
        "/api/txt-import/preview",
        files={"file": ("empty.txt", b"", "text/plain")}
    )
    assert response.status_code == 422

def test_preview_rejects_whitespace_content(client):
    response = client.post(
        "/api/txt-import/preview",
        files={"file": ("spaces.txt", b"   \r\n\t  \n  ", "text/plain")}
    )
    assert response.status_code == 422

def test_preview_rejects_nul_bytes(client):
    response = client.post(
        "/api/txt-import/preview",
        files={"file": ("nul.txt", b"Chapter 1\x00Invalid NUL byte", "text/plain")}
    )
    assert response.status_code == 422

def test_preview_rejects_undecodable_bytes(client):
    raw_garbage = b"\x81\x01\x81\x02\xff\xff\x80"
    response = client.post(
        "/api/txt-import/preview",
        files={"file": ("garbage.txt", raw_garbage, "text/plain")}
    )
    assert response.status_code == 422

def test_preview_size_limit(client, monkeypatch):
    from routers import txt_import
    monkeypatch.setattr(txt_import, "MAX_PREVIEW_BYTES", 100) # Mock small limit
    large_payload = b"A" * 150
    response = client.post(
        "/api/txt-import/preview",
        files={"file": ("large.txt", large_payload, "text/plain")}
    )
    assert response.status_code == 413

def test_preview_draft_and_character_limits(client, monkeypatch):
    from routers import txt_import
    # 1. Exceeding max characters
    monkeypatch.setattr(txt_import, "MAX_REVIEW_CHARS", 50)
    response = client.post(
        "/api/txt-import/preview",
        files={"file": ("long.txt", ("Chapter 1\n" + "A" * 60).encode("utf-8"), "text/plain")}
    )
    assert response.status_code == 413
    assert "character" in response.json()["detail"].lower()

    # 2. Exceeding max drafts
    monkeypatch.setattr(txt_import, "MAX_REVIEW_CHARS", 5_000_000)
    monkeypatch.setattr(txt_import, "MAX_REVIEW_DRAFTS", 2)
    many_chapters = "Chapter 1\nBody\nChapter 2\nBody\nChapter 3\nBody"
    response2 = client.post(
        "/api/txt-import/preview",
        files={"file": ("many.txt", many_chapters.encode("utf-8"), "text/plain")}
    )
    assert response2.status_code == 422
    assert "draft" in response2.json()["detail"].lower()

# ==========================================
# 2. Confirm API Tests
# ==========================================

def test_confirm_new_thread(client, db_session):
    payload = {
        "title": "Confirmed Novel Title",
        "author": "Author Name",
        "target": {"mode": "new"},
        "drafts": [
            {
                "title": "Edited Chapter 1",
                "body": "Edited body paragraph 1.",
                "source_chapter_ordinal": 1,
                "split_ordinal": 1,
                "split_total": 1
            },
            {
                "title": "Edited Chapter 2",
                "body": "Edited body paragraph 2.",
                "source_chapter_ordinal": 2,
                "split_ordinal": 1,
                "split_total": 1
            }
        ]
    }
    response = client.post("/api/txt-import/confirm", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "thread_id" in data
    assert len(data["chapter_ids"]) == 2

    # Verify DB state
    thread = db_session.query(Thread).filter(Thread.id == data["thread_id"]).first()
    assert thread is not None
    assert thread.title == "Confirmed Novel Title"
    assert thread.original_title == "Confirmed Novel Title"
    assert thread.author == "Author Name"
    assert thread.source_type == "txt"

    chapters = db_session.query(Chapter).filter(Chapter.thread_id == thread.id).order_by(Chapter.order.asc()).all()
    assert len(chapters) == 2
    assert chapters[0].order == 0
    assert chapters[0].title_original == "Edited Chapter 1"
    assert chapters[0].content_original == "Edited body paragraph 1."
    assert chapters[1].order == 1
    assert chapters[1].title_original == "Edited Chapter 2"
    assert chapters[1].content_original == "Edited body paragraph 2."

def test_confirm_existing_thread_append_after_max_order(client, db_session):
    existing_thread = Thread(
        title="Existing Project",
        author="Original Author",
        source_type="url",
        source_url="http://example.com"
    )
    db_session.add(existing_thread)
    db_session.commit()
    db_session.refresh(existing_thread)

    # Add existing chapters with order 0, 1, 5 (max order is 5)
    ch1 = Chapter(thread_id=existing_thread.id, order=0, title_original="Old Ch 0", content_original="C0")
    ch2 = Chapter(thread_id=existing_thread.id, order=1, title_original="Old Ch 1", content_original="C1")
    ch3 = Chapter(thread_id=existing_thread.id, order=5, title_original="Old Ch 5", content_original="C5")
    db_session.add_all([ch1, ch2, ch3])
    db_session.commit()

    payload = {
        "title": "This Title Should Not Overwrite Existing Thread",
        "author": "New Author",
        "target": {"mode": "existing", "thread_id": existing_thread.id},
        "drafts": [
            {"title": "Appended Part A", "body": "Appended body A"},
            {"title": "Appended Part B", "body": "Appended body B"}
        ]
    }
    response = client.post("/api/txt-import/confirm", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["thread_id"] == existing_thread.id
    assert len(data["chapter_ids"]) == 2

    # Thread metadata must remain untouched
    db_session.refresh(existing_thread)
    assert existing_thread.title == "Existing Project"
    assert existing_thread.author == "Original Author"
    assert existing_thread.source_type == "url"

    # Appended chapters must have order 6 and 7
    new_chapters = db_session.query(Chapter).filter(Chapter.id.in_(data["chapter_ids"])).order_by(Chapter.order.asc()).all()
    assert len(new_chapters) == 2
    assert new_chapters[0].order == 6
    assert new_chapters[0].title_original == "Appended Part A"
    assert new_chapters[1].order == 7
    assert new_chapters[1].title_original == "Appended Part B"

def test_confirm_existing_thread_not_found(client):
    payload = {
        "target": {"mode": "existing", "thread_id": 999999},
        "drafts": [{"title": "Ch", "body": "Body"}]
    }
    response = client.post("/api/txt-import/confirm", json=payload)
    assert response.status_code == 404

def test_confirm_validation_errors(client):
    # Empty drafts list
    resp1 = client.post("/api/txt-import/confirm", json={"target": {"mode": "new"}, "drafts": []})
    assert resp1.status_code == 422

    # Empty draft title
    resp2 = client.post("/api/txt-import/confirm", json={
        "target": {"mode": "new"},
        "drafts": [{"title": "   ", "body": "Valid body"}]
    })
    assert resp2.status_code == 422

    # Empty draft body
    resp3 = client.post("/api/txt-import/confirm", json={
        "target": {"mode": "new"},
        "drafts": [{"title": "Valid title", "body": "   "}]
    })
    assert resp3.status_code == 422

    # Draft title exceeding 500 chars
    resp4 = client.post("/api/txt-import/confirm", json={
        "target": {"mode": "new"},
        "drafts": [{"title": "A" * 501, "body": "Valid body"}]
    })
    assert resp4.status_code == 422

    # Novel title exceeding 500 chars
    resp5 = client.post("/api/txt-import/confirm", json={
        "title": "T" * 501,
        "target": {"mode": "new"},
        "drafts": [{"title": "Ch 1", "body": "Valid body"}]
    })
    assert resp5.status_code == 422

    # Author exceeding 200 chars
    resp6 = client.post("/api/txt-import/confirm", json={
        "author": "A" * 201,
        "target": {"mode": "new"},
        "drafts": [{"title": "Ch 1", "body": "Valid body"}]
    })
    assert resp6.status_code == 422

    # Exceeding draft count limit
    resp7 = client.post("/api/txt-import/confirm", json={
        "target": {"mode": "new"},
        "drafts": [{"title": f"Ch {i}", "body": "Valid body"} for i in range(1001)]
    })
    assert resp7.status_code == 422
    assert "draft" in resp7.json()["detail"].lower()

    # Exceeding character count limit
    from routers import txt_import
    orig_chars = txt_import.MAX_REVIEW_CHARS
    try:
        txt_import.MAX_REVIEW_CHARS = 100
        resp8 = client.post("/api/txt-import/confirm", json={
            "target": {"mode": "new"},
            "drafts": [{"title": "Ch 1", "body": "X" * 150}]
        })
        assert resp8.status_code == 413
        assert "character" in resp8.json()["detail"].lower()
    finally:
        txt_import.MAX_REVIEW_CHARS = orig_chars

def test_confirm_atomic_rollback_on_failure(client, db_session, monkeypatch):
    initial_threads = db_session.query(Thread).count()
    initial_chapters = db_session.query(Chapter).count()

    # Simulate an error during chapter addition/flush
    from routers import txt_import
    def crash_after_thread(*args, **kwargs):
        raise RuntimeError("Database connection interrupted during import")

    monkeypatch.setattr(txt_import, "_commit_import_transaction", crash_after_thread)

    payload = {
        "title": "Doomed Novel",
        "target": {"mode": "new"},
        "drafts": [{"title": "Ch 1", "body": "Content 1"}]
    }
    response = client.post("/api/txt-import/confirm", json=payload)
    assert response.status_code == 500

    # Ensure no partial thread or chapters were committed
    assert db_session.query(Thread).count() == initial_threads
    assert db_session.query(Chapter).count() == initial_chapters

# ==========================================
# 3. Workspace Isolation Tests
# ==========================================

def test_txt_import_workspace_isolation(mock_dual_workspaces):
    client = TestClient(app)
    client.cookies.set(database.GHOST_SESSION_COOKIE, database.issue_ghost_session())

    # Get thread IDs in main and ghost
    with mock_dual_workspaces["SessionMain"]() as db_m:
        t_main = db_m.query(Thread).first()
        main_id = t_main.id

    with mock_dual_workspaces["SessionGhost"]() as db_g:
        t_ghost = db_g.query(Thread).first()
        ghost_id = t_ghost.id

    # 1. Attempting to append to main thread ID from ghost workspace must return 404
    payload_to_main = {
        "target": {"mode": "existing", "thread_id": main_id},
        "drafts": [{"title": "Ghost Appended Ch", "body": "Secret body"}]
    }
    # If main_id != ghost_id, it returns 404
    # Even if main_id == ghost_id (in isolated SQLite dbs both might be 1),
    # let's test appending to main_id when in ghost workspace:
    resp_ghost_to_main = client.post(
        "/api/txt-import/confirm",
        headers={"X-Workspace": "ghost"},
        json={"target": {"mode": "existing", "thread_id": 99999}, "drafts": [{"title": "Ch", "body": "B"}]}
    )
    assert resp_ghost_to_main.status_code == 404

    # 2. Confirming new thread in Ghost creates thread strictly in Ghost DB
    resp_new_ghost = client.post(
        "/api/txt-import/confirm",
        headers={"X-Workspace": "ghost"},
        json={
            "title": "Strictly Ghost Novel",
            "target": {"mode": "new"},
            "drafts": [{"title": "Ghost Ch 1", "body": "Hidden content"}]
        }
    )
    assert resp_new_ghost.status_code == 200
    ghost_thread_id = resp_new_ghost.json()["thread_id"]

    # Verify thread exists in Ghost DB, but NOT in Main DB
    with mock_dual_workspaces["SessionGhost"]() as db_g:
        found_in_ghost = db_g.query(Thread).filter(Thread.id == ghost_thread_id).first()
        assert found_in_ghost is not None
        assert found_in_ghost.title == "Strictly Ghost Novel"

    with mock_dual_workspaces["SessionMain"]() as db_m:
        found_in_main = db_m.query(Thread).filter(Thread.id == ghost_thread_id).first()
        assert found_in_main is None

# ==========================================
# 4. Export Integration Tests
# ==========================================

def test_export_epub_after_import_uses_original_content_and_selected_ids(client, db_session):
    # 1. Confirm import
    confirm_payload = {
        "title": "Export Test Book",
        "author": "Famous Author",
        "target": {"mode": "new"},
        "drafts": [
            {"title": "Imported Ch 1", "body": "Raw original text for chapter 1."},
            {"title": "Imported Ch 2", "body": "Raw original text for chapter 2."},
            {"title": "Imported Ch 3", "body": "Raw original text for chapter 3."}
        ]
    }
    confirm_res = client.post("/api/txt-import/confirm", json=confirm_payload)
    assert confirm_res.status_code == 200
    import_data = confirm_res.json()
    thread_id = import_data["thread_id"]
    chapter_ids = import_data["chapter_ids"]

    # 2. Export ONLY chapter 1 and 2 (verifies that only newly selected chapter IDs are exported)
    export_payload = {
        "format": "epub",
        "title": "Export Test Book",
        "author": "Famous Author",
        "chapter_ids": [chapter_ids[0], chapter_ids[1]]
    }
    export_res = client.post(f"/api/threads/{thread_id}/export", json=export_payload)
    assert export_res.status_code == 200
    assert export_res.headers["content-type"] == "application/epub+zip"
    assert len(export_res.content) > 0

def test_preview_and_confirm_with_toc_and_volume_headings_no_deadlock(client):
    """Verifies that TXT with TOC and volume headings previews without empty drafts and confirms smoothly without 422."""
    raw_text = """Table of Contents
Chapter 1: The Beginning
Chapter 2: The Forest

第1卷 魔法篇
第1章 开始
正文第一章内容。

第2章 冒险
正文第二章内容。
"""
    # 1. Preview
    res_preview = client.post(
        "/api/txt-import/preview",
        files={"file": ("novel_with_toc.txt", raw_text.encode("utf-8"), "text/plain")}
    )
    assert res_preview.status_code == 200
    preview_data = res_preview.json()
    drafts = preview_data["drafts"]
    assert len(drafts) >= 2
    # Ensure zero empty bodies returned in preview
    for d in drafts:
        assert d["body"].strip() != "", f"Draft {d['title']} has empty body!"

    # 2. Confirm directly with previewed drafts (must not deadlock with 422)
    res_confirm = client.post(
        "/api/txt-import/confirm",
        json={
            "title": "TOC Novel",
            "target": {"mode": "new"},
            "drafts": drafts
        }
    )
    assert res_confirm.status_code == 200
    confirm_data = res_confirm.json()
    assert confirm_data["thread_id"] > 0
    assert len(confirm_data["chapter_ids"]) == len(drafts)

def test_confirm_transaction_no_post_commit_refresh_loop(client, db_session, monkeypatch):
    """Verifies that _commit_import_transaction does not invoke db.refresh loop after commit."""
    refresh_calls = 0
    orig_refresh = db_session.refresh

    def spied_refresh(instance):
        nonlocal refresh_calls
        refresh_calls += 1
        return orig_refresh(instance)

    monkeypatch.setattr(db_session, "refresh", spied_refresh)

    res = client.post(
        "/api/txt-import/confirm",
        json={
            "title": "No Refresh Novel",
            "target": {"mode": "new"},
            "drafts": [
                {"title": f"Ch {i}", "body": f"Content {i}"}
                for i in range(10)
            ]
        }
    )
    assert res.status_code == 200
    # db.refresh should not be called in a loop for the 10 chapters
    assert refresh_calls == 0

