import httpx
import pytest

from services.lm_slots import MAX_CROP_CONCURRENCY, detect_parallel, parallel_from_models, resolve_concurrency

LOADED = {
    "models": [
        {
            "key": "index-translate-2b",
            "loaded_instances": [{"id": "index-translate-2b", "config": {"context_length": 65792, "parallel": 4}}],
        },
        {"key": "google/gemma-4-e4b", "loaded_instances": []},
    ]
}


def test_reads_parallel_of_the_loaded_instance():
    assert parallel_from_models(LOADED, "index-translate-2b") == 4


@pytest.mark.parametrize(
    "payload,model",
    [
        (LOADED, "google/gemma-4-e4b"),  # not loaded: the slot count is only fixed at load time
        (LOADED, "unknown"),
        ({"models": [{"key": "m", "loaded_instances": [{"id": "m", "config": {}}]}]}, "m"),
        ({"models": [{"key": "m", "loaded_instances": [{"id": "m", "config": {"parallel": "x"}}]}]}, "m"),
        ({"models": "nope"}, "m"),
        ([], "m"),
    ],
)
def test_unknown_or_malformed_means_none(payload, model):
    assert parallel_from_models(payload, model) is None


@pytest.mark.parametrize("parallel,expected", [(None, 1), (0, 1), (1, 1), (4, 4), (99, MAX_CROP_CONCURRENCY)])
def test_concurrency_is_clamped_and_defaults_to_one(parallel, expected):
    assert resolve_concurrency(parallel) == expected


@pytest.mark.asyncio
async def test_detects_parallel_from_lm_studio_api_root_even_when_url_ends_with_v1():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json=LOADED)

    transport = httpx.MockTransport(handler)
    assert await detect_parallel("http://localhost:1234/v1", "index-translate-2b", transport=transport) == 4
    assert await detect_parallel("http://localhost:1234", "index-translate-2b", transport=transport) == 4
    assert seen == ["http://localhost:1234/api/v1/models"] * 2


@pytest.mark.asyncio
@pytest.mark.parametrize("response", [httpx.Response(404), httpx.Response(200, text="not json")])
async def test_server_without_the_endpoint_or_with_garbage_gives_none(response):
    transport = httpx.MockTransport(lambda _request: response)

    assert await detect_parallel("http://localhost:1234", "m", transport=transport) is None


@pytest.mark.asyncio
async def test_connection_error_gives_none_instead_of_raising():
    def boom(_request):
        raise httpx.ConnectError("down")

    assert await detect_parallel("http://localhost:1234", "m", transport=httpx.MockTransport(boom)) is None
