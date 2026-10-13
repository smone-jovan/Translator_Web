import pytest
from fastapi.testclient import TestClient
from main import app
from database import get_db, Thread, Chapter, count_images_in_text


@pytest.fixture
def client(db_session, default_global_settings):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_count_images_in_text():
    # 1. Empty / None
    assert count_images_in_text(None) == 0
    assert count_images_in_text("") == 0
    assert count_images_in_text("Just plain text with no illustrations.") == 0

    # 2. Markdown images
    md_text = "Paragraph 1\n\n![Cover Art](https://example.com/cover.jpg)\n\nParagraph 2\n![Scene 1](images/scene1.png)"
    assert count_images_in_text(md_text) == 2

    # 3. HTML img tags
    html_text = '<p>Start</p><img src="https://example.com/art.jpg" alt="Art" /><p>End</p>'
    assert count_images_in_text(html_text) == 1

    # 4. Escaped HTML img tags
    escaped_text = "Before &lt;img src=\"test.png\" /&gt; after"
    assert count_images_in_text(escaped_text) == 1

    # 5. Mixed formats
    mixed = "![One](1.png) text <img src=\"2.png\"> text ![Three](3.png)"
    assert count_images_in_text(mixed) == 3


def test_chapter_image_count_orm_listeners(db_session):
    thread = Thread(title="Image Test Novel", source_type="epub")
    db_session.add(thread)
    db_session.commit()
    db_session.refresh(thread)

    # Insert chapter with 2 images
    ch1 = Chapter(
        thread_id=thread.id,
        order=0,
        title_original="Chapter 1",
        content_original="Hello world\n\n![Illo 1](1.jpg)\n\n![Illo 2](2.jpg)"
    )
    db_session.add(ch1)
    db_session.commit()
    db_session.refresh(ch1)

    assert ch1.image_count == 2

    # Update chapter with translation having 3 images
    ch1.content_translated = "Halo dunia\n\n![Illo 1](1.jpg)\n\n![Illo 2](2.jpg)\n\n![Illo 3](3.jpg)"
    db_session.commit()
    db_session.refresh(ch1)

    assert ch1.image_count == 3


def test_get_thread_returns_image_count(client, db_session):
    thread = Thread(title="Thread with Images", source_type="syosetu")
    db_session.add(thread)
    db_session.commit()
    db_session.refresh(thread)

    ch_plain = Chapter(
        thread_id=thread.id,
        order=0,
        title_original="Plain Chapter",
        content_original="No images here."
    )
    ch_illustrated = Chapter(
        thread_id=thread.id,
        order=1,
        title_original="Illustrated Chapter",
        content_original="Text with illustration: ![Insert](https://img.example/insert.png)"
    )
    db_session.add_all([ch_plain, ch_illustrated])
    db_session.commit()

    res = client.get(f"/api/threads/{thread.id}")
    assert res.status_code == 200
    data = res.json()
    assert len(data["chapters"]) == 2

    assert data["chapters"][0]["image_count"] == 0
    assert data["chapters"][1]["image_count"] == 1
