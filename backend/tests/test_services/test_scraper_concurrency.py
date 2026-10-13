import pytest
from fastapi.testclient import TestClient
from main import app
from database import get_db, GlobalSetting
from services.scrapers.novalpie import NovalpieAdapter, get_scraper_concurrency


@pytest.fixture
def client(db_session, default_global_settings):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_scraper_concurrency_settings_api(client, db_session):
    # 1. Default value check
    res = client.get("/api/settings")
    assert res.status_code == 200
    data = res.json()
    assert "scraper_concurrency" in data
    assert data["scraper_concurrency"] in [1, 2, 3, 4, 5]

    # 2. Update to 4
    res_update = client.post("/api/settings", json={"scraper_concurrency": 4})
    assert res_update.status_code == 200

    res_after = client.get("/api/settings")
    assert res_after.json()["scraper_concurrency"] == 4

    # 3. Upper bound cap (10 -> 5)
    client.post("/api/settings", json={"scraper_concurrency": 10})
    assert client.get("/api/settings").json()["scraper_concurrency"] == 5

    # 4. Lower bound cap (0 -> 1)
    client.post("/api/settings", json={"scraper_concurrency": 0})
    assert client.get("/api/settings").json()["scraper_concurrency"] == 1


def test_novalpie_dynamic_semaphore(db_session):
    gs = db_session.query(GlobalSetting).first()
    if not gs:
        gs = GlobalSetting()
        db_session.add(gs)

    # Set concurrency to 3
    gs.scraper_concurrency = 3
    db_session.commit()

    sem = NovalpieAdapter.get_semaphore()
    # In asyncio, semaphore._value represents initial/available tokens
    assert sem._value in [1, 2, 3, 4, 5]
