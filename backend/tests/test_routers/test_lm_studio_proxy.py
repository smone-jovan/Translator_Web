import pytest
import httpx
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, GlobalSetting
from routers.settings import get_lm_studio_models, load_lm_studio_model, LMStudioLoadRequest

@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    gs = GlobalSetting(
        lm_url="http://localhost:1234",
        lm_model="qwen2.5-7b-instruct",
    )
    session.add(gs)
    session.commit()

    try:
        yield session
    finally:
        session.close()


@pytest.mark.asyncio
async def test_get_lm_studio_models_success(db_session):
    mock_models_response = {
        "data": [
            {"id": "qwen2.5-7b-instruct", "object": "model"},
            {"id": "deepseek-r1-distill-qwen-7b", "object": "model"}
        ]
    }

    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json = MagicMock(return_value=mock_models_response)

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        res = await get_lm_studio_models(url=None, db=db_session)
        assert res["status"] == "connected"
        assert len(res["data"]) == 2
        assert res["data"][0]["id"] == "qwen2.5-7b-instruct"
        assert res["data"][1]["id"] == "deepseek-r1-distill-qwen-7b"


@pytest.mark.asyncio
async def test_get_lm_studio_models_unreachable(db_session):
    with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("Connection refused")):
        res = await get_lm_studio_models(url=None, db=db_session)
        assert res["status"] == "error"
        assert res["data"] == []
        assert "Ensure LM Studio is running" in res["detail"]


@pytest.mark.asyncio
async def test_load_lm_studio_model_success(db_session):
    req = LMStudioLoadRequest(model="deepseek-r1-distill-qwen-7b")

    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json = MagicMock(return_value={"status": "ok"})

    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        res = await load_lm_studio_model(req=req, db=db_session)
        assert res["status"] == "ok"
        assert res["model"] == "deepseek-r1-distill-qwen-7b"

        # Check DB was updated
        gs = db_session.query(GlobalSetting).first()
        assert gs.lm_model == "deepseek-r1-distill-qwen-7b"
