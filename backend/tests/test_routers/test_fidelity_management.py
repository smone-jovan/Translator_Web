import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from main import app
from database import get_db, Thread, Chapter


@pytest.fixture
def client(db_session, default_global_settings):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_get_fidelity_issues_empty(client, db_session):
    thread = Thread(title="Test Novel", source_type="manual")
    db_session.add(thread)
    db_session.commit()

    ch1 = Chapter(thread_id=thread.id, order=1, title_original="Bab 1", content_original="Halo", content_translated="Halo.", translation_status="translated")
    db_session.add(ch1)
    db_session.commit()

    response = client.get(f"/api/threads/{thread.id}/fidelity-issues")
    assert response.status_code == 200
    data = response.json()
    assert data["thread_id"] == thread.id
    assert data["total_chapters"] == 1
    assert data["flagged_chapters_count"] == 0
    assert len(data["issues"]) == 0


def test_get_fidelity_issues_categorized(client, db_session):
    thread = Thread(title="Fidelity Novel", source_type="manual")
    db_session.add(thread)
    db_session.commit()

    # Chapter 1: Truncated
    ch1 = Chapter(
        thread_id=thread.id,
        order=1,
        title_original="Bab 1",
        content_original="Paragraf satu.\n\nParagraf dua.",
        content_translated="Paragraf satu dan dia berkata",
        fidelity_warning="Translation appears to be cut off mid-sentence.",
        translation_status="translated"
    )
    # Chapter 2: Minor warning (0.85 ratio)
    ch2 = Chapter(
        thread_id=thread.id,
        order=2,
        title_original="Bab 2",
        content_original="Baris 1\n\nBaris 2\n\nBaris 3\n\nBaris 4\n\nBaris 5\n\nBaris 6\n\nBaris 7\n\nBaris 8\n\nBaris 9\n\nBaris 10",
        content_translated="Baris 1\n\nBaris 2\n\nBaris 3\n\nBaris 4\n\nBaris 5\n\nBaris 6\n\nBaris 7\n\nBaris 8.",
        fidelity_warning="Minor paragraph variation",
        translation_status="translated"
    )
    db_session.add_all([ch1, ch2])
    db_session.commit()

    response = client.get(f"/api/threads/{thread.id}/fidelity-issues")
    assert response.status_code == 200
    data = response.json()
    assert data["flagged_chapters_count"] == 2
    assert len(data["issues"]) == 2

    issue1 = next(i for i in data["issues"] if i["chapter_id"] == ch1.id)
    assert issue1["is_truncated"] is True
    assert issue1["severity"] == "critical"
    assert "truncated" in issue1["issue_types"]

    issue2 = next(i for i in data["issues"] if i["chapter_id"] == ch2.id)
    assert issue2["severity"] == "minor"
    assert "minor_ratio" in issue2["issue_types"]


def test_get_fidelity_issues_consolidated_paragraphs_not_critical(client, db_session):
    thread = Thread(title="Consolidated Novel", source_type="manual")
    db_session.add(thread)
    db_session.commit()

    # 30 short original lines (avg 15 chars)
    orig = "\n\n".join([f"短行测试第 {i} 句。" for i in range(30)])
    # 5 standard English prose paragraphs (avg 150 chars, char_ratio > 1.0)
    trans = "\n\n".join([
        f"Consolidated narrative paragraph {i} with plenty of context, complete sentences, and proper punctuation."
        for i in range(5)
    ])

    ch = Chapter(
        thread_id=thread.id,
        order=1,
        title_original="Bab 1",
        content_original=orig,
        content_translated=trans,
        fidelity_warning="Paragraph count consolidated: 30 original → 5 translated (ratio: 0.17).",
        translation_status="translated"
    )
    db_session.add(ch)
    db_session.commit()

    response = client.get(f"/api/threads/{thread.id}/fidelity-issues")
    assert response.status_code == 200
    data = response.json()
    assert len(data["issues"]) == 1
    issue = data["issues"][0]
    assert issue["severity"] != "critical"
    assert issue["severity"] == "minor"
    assert "consolidated" in issue["issue_types"]
    assert issue["is_truncated"] is False


def test_batch_dismiss_fidelity(client, db_session):
    thread = Thread(title="Dismiss Novel", source_type="manual")
    db_session.add(thread)
    db_session.commit()

    ch1 = Chapter(thread_id=thread.id, order=1, title_original="Bab 1", fidelity_warning="Warning 1", translation_status="translated")
    ch2 = Chapter(thread_id=thread.id, order=2, title_original="Bab 2", fidelity_warning="Warning 2", translation_status="translated")
    db_session.add_all([ch1, ch2])
    db_session.commit()

    response = client.post(f"/api/threads/{thread.id}/fidelity/dismiss", json={"chapter_ids": [ch1.id]})
    assert response.status_code == 200
    assert response.json()["dismissed_count"] == 1

    db_session.refresh(ch1)
    db_session.refresh(ch2)
    assert ch1.fidelity_warning is None
    assert ch2.fidelity_warning == "Warning 2"


def test_single_dismiss_fidelity(client, db_session):
    thread = Thread(title="Single Dismiss Novel", source_type="manual")
    db_session.add(thread)
    db_session.commit()

    ch = Chapter(thread_id=thread.id, order=1, title_original="Bab 1", fidelity_warning="Cut off", translation_status="translated")
    db_session.add(ch)
    db_session.commit()

    response = client.post(f"/api/threads/{thread.id}/chapters/{ch.id}/dismiss-fidelity")
    assert response.status_code == 200
    assert response.json()["dismissed"] is True

    db_session.refresh(ch)
    assert ch.fidelity_warning is None


@pytest.mark.asyncio
async def test_batch_retranslate_fidelity(client, db_session):
    thread = Thread(title="Retranslate Novel", source_type="manual")
    db_session.add(thread)
    db_session.commit()

    ch1 = Chapter(
        thread_id=thread.id,
        order=1,
        title_original="Bab 1",
        content_original="Asli",
        content_translated="Potong",
        fidelity_warning="Warning cut",
        translation_status="translated"
    )
    db_session.add(ch1)
    db_session.commit()

    with patch("services.background_translator.BackgroundTranslator.start_batch", new_callable=AsyncMock) as mock_start:
        response = client.post(f"/api/threads/{thread.id}/fidelity/retranslate", json={"chapter_ids": [ch1.id]})
        assert response.status_code == 200
        assert response.json()["queued_count"] == 1
        mock_start.assert_awaited_once()

    db_session.refresh(ch1)
    assert ch1.fidelity_warning is None
    assert ch1.translation_status == "idle"
    assert ch1.content_translated is None
