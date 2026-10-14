from pathlib import Path
import pytest
from database import normalize_workspace, make_workspace_key


def test_normalize_workspace_values():
    assert normalize_workspace("main") == "main"
    assert normalize_workspace("MAIN") == "main"
    assert normalize_workspace("  ghost ") == "ghost"
    assert normalize_workspace("GHOST") == "ghost"
    assert normalize_workspace("invalid_ws") == "main"
    assert normalize_workspace(None) in ("main", "ghost")


def test_make_workspace_key_produces_strict_compound_tuple():
    key_main = make_workspace_key("main", 42)
    key_ghost = make_workspace_key("GHOST", 42)

    assert key_main == ("main", 42)
    assert key_ghost == ("ghost", 42)
    assert key_main != key_ghost
    assert isinstance(key_main[0], str)
    assert isinstance(key_main[1], int)


def test_claude_md_contains_adr118_and_graphify_directives():
    repo_root = Path(__file__).resolve().parents[2]
    claude_md = (repo_root / "CLAUDE.md").read_text(encoding="utf-8")

    assert "make_workspace_key" in claude_md
    assert "getWorkspaceStorageKey" in claude_md
    assert "GlobalSetting" in claude_md
    assert "graphify-out" in claude_md
