"""
Tests must never write the git-tracked runtime file backend/data/adaptive_selectors.json
(ADR-120 residual): running pytest used to rewrite it, which then got committed by accident.
"""
from pathlib import Path

from services.scrapers import adaptive_dom

TRACKED_STORE = Path(__file__).resolve().parents[2] / "data" / "adaptive_selectors.json"


def test_adaptive_store_is_redirected_away_from_tracked_file():
    assert adaptive_dom._DEFAULT_STORE_PATH.resolve() != TRACKED_STORE.resolve()


def test_adaptive_memory_cache_starts_empty_for_each_test():
    assert adaptive_dom._SIGNATURE_MEMORY_CACHE == {}
