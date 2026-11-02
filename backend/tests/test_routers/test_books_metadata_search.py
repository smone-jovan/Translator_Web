import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, Thread
from main import app
from routers.threads import get_db

TEST_DB_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    Base.metadata.drop_all(bind=test_engine)
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


def test_search_book_metadata_empty_query(client):
    res = client.get("/api/books/search?q=")
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_search_book_metadata_success(client):
    ol_mock_data = {
        "docs": [
            {
                "title": "Lord of the Mysteries",
                "author_name": ["Cuttlefish That Loves Diving"],
                "cover_i": 12345,
                "first_publish_year": 2018,
                "subject": ["Fantasy", "Steampunk", "Mystery"],
            }
        ]
    }
    gb_mock_data = {
        "items": [
            {
                "volumeInfo": {
                    "title": "Lord of the Mysteries Vol 1",
                    "authors": ["Cuttlefish"],
                    "description": "With the rising tide of steam power and machinery...",
                    "publishedDate": "2018-04-01",
                    "categories": ["Fiction", "Fantasy"],
                    "imageLinks": {
                        "thumbnail": "http://books.google.com/books/content?id=xyz"
                    },
                }
            }
        ]
    }

    class MockResponse:
        def __init__(self, status_code, json_data):
            self.status_code = status_code
            self._json = json_data

        def json(self):
            return self._json

    async def mock_get(url, **kwargs):
        if "openlibrary.org" in url:
            return MockResponse(200, ol_mock_data)
        elif "googleapis.com" in url:
            return MockResponse(200, gb_mock_data)
        return MockResponse(404, {})

    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        res = client.get("/api/books/search?q=Lord of the Mysteries")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 2

        # Open Library result check
        ol_item = data[0]
        assert ol_item["title"] == "Lord of the Mysteries"
        assert ol_item["author"] == "Cuttlefish That Loves Diving"
        assert ol_item["cover_url"] == "https://covers.openlibrary.org/b/id/12345-L.jpg"
        assert ol_item["source"] == "openlibrary"

        # Google Books result check
        gb_item = data[1]
        assert gb_item["title"] == "Lord of the Mysteries Vol 1"
        assert gb_item["synopsis"].startswith("With the rising tide")
        assert gb_item["cover_url"].startswith("https://books.google.com")
        assert gb_item["source"] == "googlebooks"


def test_patch_thread_metadata_and_cover(client):
    db = TestingSessionLocal()
    thread = Thread(title="Original Novel Title", source_type="epub")
    db.add(thread)
    db.commit()
    db.refresh(thread)

    update_payload = {
        "title": "Lord of the Mysteries",
        "author": "Cuttlefish",
        "genres": "Fantasy, Steampunk",
        "synopsis": "A glorious steampunk adventure.",
        "cover_image": "https://covers.openlibrary.org/b/id/12345-L.jpg",
    }

    res = client.patch(f"/api/threads/{thread.id}", json=update_payload)
    assert res.status_code == 200
    assert res.json() == {"status": "updated", "thread_id": thread.id}

    db.refresh(thread)
    assert thread.title == "Lord of the Mysteries"
    assert thread.author == "Cuttlefish"
    assert thread.genres == "Fantasy, Steampunk"
    assert thread.synopsis == "A glorious steampunk adventure."
    assert thread.cover_image == "https://covers.openlibrary.org/b/id/12345-L.jpg"


@pytest.mark.asyncio
async def test_search_book_metadata_partial_failure_and_clamping(client):
    class MockResponse:
        def __init__(self, status_code, json_data):
            self.status_code = status_code
            self._json = json_data

        def json(self):
            return self._json

    captured_urls = []

    async def mock_get(url, **kwargs):
        captured_urls.append(url)
        if "openlibrary.org" in url:
            raise Exception("Open Library timeout simulated")
        elif "googleapis.com" in url:
            return MockResponse(200, {
                "items": [
                    {
                        "volumeInfo": {
                            "title": "Solo Leveling",
                            "authors": ["Chugong"],
                            "description": "Hunter Sung Jinwoo...",
                            "imageLinks": {"thumbnail": "http://books.google.com/cover.jpg&edge=curl"}
                        }
                    }
                ]
            })
        return MockResponse(404, {})

    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        # Test negative limit clamped to 1, and long query
        long_query = "A" * 300
        res = client.get(f"/api/books/search?q={long_query}&limit=-5")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        assert data[0]["title"] == "Solo Leveling"
        assert data[0]["source"] == "googlebooks"
        assert data[0]["cover_url"] == "https://books.google.com/cover.jpg"
        
        # Verify limit was clamped to 1 and query was truncated to 200
        assert any("limit=1" in u for u in captured_urls)
        assert any("maxResults=1" in u for u in captured_urls)
