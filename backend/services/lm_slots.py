"""
How many requests the local LM Studio model accepts at once. LM Studio fixes the number of parallel slots when
a model is loaded and reports it through `GET /api/v1/models` (`loaded_instances[].config.parallel`); a model
that is not loaded yet has no value. Anything unexpected means "unknown" and the caller sends one at a time.
"""
from typing import Optional

import httpx

MAX_CROP_CONCURRENCY = 8
PROBE_TIMEOUT_SECONDS = 3.0


def parallel_from_models(payload: object, model: str) -> Optional[int]:
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return None
    for entry in models:
        if not isinstance(entry, dict) or entry.get("key") != model:
            continue
        for instance in entry.get("loaded_instances") or []:
            config = instance.get("config") if isinstance(instance, dict) else None
            parallel = config.get("parallel") if isinstance(config, dict) else None
            if type(parallel) is int and parallel > 0:
                return parallel
    return None


def resolve_concurrency(parallel: Optional[int]) -> int:
    if not parallel or parallel < 1:
        return 1
    return min(parallel, MAX_CROP_CONCURRENCY)


def _api_root(base_url: str) -> str:
    root = base_url.rstrip("/")
    return root[: -len("/v1")] if root.endswith("/v1") else root


async def detect_parallel(base_url: str, model: str, *, transport: Optional[httpx.AsyncBaseTransport] = None) -> Optional[int]:
    """Parallel slots of the loaded `model`, or None when LM Studio does not say (or is not reachable)."""
    try:
        async with httpx.AsyncClient(transport=transport, timeout=PROBE_TIMEOUT_SECONDS) as client:
            response = await client.get(f"{_api_root(base_url)}/api/v1/models")
            response.raise_for_status()
            return parallel_from_models(response.json(), model)
    except Exception:
        return None
