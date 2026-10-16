"""
Regresi: MetadataScraperEngine harus meneruskan workspace request ke NovalpieAdapter
(CLAUDE.md invariant #2), bukan jatuh ke variabel proses global ACTIVE_WORKSPACE.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from database import Thread, get_db
from services.scrapers.engine import MetadataScraperEngine
from services.scrapers.novalpie import NovalpieAdapter


def _ok_result():
    res = MagicMock()
    res.success = True
    res.title = "Hit"
    return res


@pytest.mark.asyncio
async def test_engine_scrape_uses_explicit_workspace_for_novalpie():
    engine = MetadataScraperEngine()
    seen = []

    async def fake_scrape_metadata(self, query, **kwargs):
        seen.append(self.workspace)
        return _ok_result()

    with patch.object(NovalpieAdapter, "scrape_metadata", fake_scrape_metadata):
        await engine.scrape("https://novalpie.cc/book/1", source="novalpie", workspace="ghost")

    assert seen == ["ghost"]


@pytest.mark.asyncio
async def test_engine_scrape_derives_workspace_from_db_session(db_session):
    db_session._workspace = "ghost"
    engine = MetadataScraperEngine()
    seen = []

    async def fake_scrape_metadata(self, query, **kwargs):
        seen.append(self.workspace)
        return _ok_result()

    with patch.object(NovalpieAdapter, "scrape_metadata", fake_scrape_metadata):
        await engine.scrape("https://novalpie.cc/book/1", source="novalpie", db_session=db_session)

    assert seen == ["ghost"]


@pytest.mark.asyncio
async def test_engine_scrape_candidates_uses_workspace():
    engine = MetadataScraperEngine()
    seen = []

    async def fake_candidates(self, query, **kwargs):
        seen.append(self.workspace)
        return []

    with patch.object(NovalpieAdapter, "scrape_candidates", fake_candidates):
        await engine.scrape_candidates("https://novalpie.cc/book/1", source="novalpie", workspace="ghost")

    assert seen == ["ghost"]


def test_scrape_metadata_route_passes_db_workspace_explicitly(db_session, default_global_settings):
    from main import app
    import routers.scrape as scrape_router

    db_session._workspace = "ghost"
    thread = Thread(title="T", source_url="https://novalpie.cc/book/9")
    db_session.add(thread)
    db_session.commit()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch.object(scrape_router.scraper_engine, "scrape", new_callable=AsyncMock) as mock_scrape:
            mock_scrape.return_value = MagicMock(
                success=True, original_title="o", title="t", genres=None, tags=None,
                synopsis=None, status_coo=None, status=None, cover_image=None,
                author=None, detail_url=None,
            )
            with TestClient(app) as c:
                res = c.post(
                    f"/api/threads/{thread.id}/scrape_metadata",
                    json={"source": "novalpie"},
                    headers={"X-Workspace": "ghost"},
                )
            assert res.status_code == 200, res.text
            assert mock_scrape.call_args.kwargs.get("workspace") == "ghost"
    finally:
        app.dependency_overrides.clear()
