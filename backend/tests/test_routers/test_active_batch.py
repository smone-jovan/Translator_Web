import pytest
from fastapi.testclient import TestClient
from main import app
from database import get_db
from services.background_translator import active_batches
from unittest.mock import Mock

@pytest.fixture
def client(db_session, default_global_settings):
    def override_get_db():
        yield db_session
        
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture(autouse=True)
def clear_batches():
    active_batches.clear()
    yield
    active_batches.clear()

def test_active_batch_empty(client):
    response = client.get("/api/threads/active-batch")
    assert response.status_code == 200
    assert response.json()["active"] is False

def test_active_batch_one_waiting(client):
    # Arrange
    mock_batch = Mock()
    mock_batch.total = 10
    mock_batch.completed = 0
    mock_batch.current_chapter_id = 1
    mock_batch.current_chapter_title = "Test"
    mock_batch.failed_ids = []
    mock_batch.quota_exhausted = False
    mock_batch.is_waiting = True
    
    # Needs a thread in DB for thread_title, but we can patch or assume thread 1 exists
    active_batches[1] = mock_batch
    
    # Act
    response = client.get("/api/threads/active-batch")
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["active"] is True
    assert data["thread_id"] == 1
    assert data["is_waiting"] is True
    assert data["queue_count"] == 0

def test_active_batch_one_active_one_waiting(client):
    # Arrange
    mock_batch_1 = Mock()
    mock_batch_1.total = 10
    mock_batch_1.completed = 5
    mock_batch_1.current_chapter_id = 1
    mock_batch_1.current_chapter_title = "Test"
    mock_batch_1.failed_ids = []
    mock_batch_1.quota_exhausted = False
    mock_batch_1.is_waiting = False
    
    mock_batch_2 = Mock()
    mock_batch_2.total = 5
    mock_batch_2.completed = 0
    mock_batch_2.current_chapter_id = None
    mock_batch_2.current_chapter_title = ""
    mock_batch_2.failed_ids = []
    mock_batch_2.quota_exhausted = False
    mock_batch_2.is_waiting = True
    
    active_batches[1] = mock_batch_1
    active_batches[2] = mock_batch_2
    
    # Act
    response = client.get("/api/threads/active-batch")
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["active"] is True
    assert data["thread_id"] == 1
    assert data["is_waiting"] is False
    assert data["queue_count"] == 1
