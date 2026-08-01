import pytest
from services.genre_presets import list_presets, apply_preset
from database import Thread, LorebookEntry

def test_list_presets():
    """Test that list_presets returns the expected array of dictionaries."""
    presets = list_presets()
    assert isinstance(presets, list)
    assert len(presets) > 0
    assert "key" in presets[0]
    assert "name" in presets[0]
    
    # Verify our main cultivation preset exists
    keys = [p["key"] for p in presets]
    assert "xianxia" in keys

def test_apply_preset_additive_behavior(db_session):
    """Test that apply_preset adds new terms but does not overwrite existing ones."""
    # Setup thread
    thread = Thread(title="Test Novel", original_title="测试", genres="cultivation")
    db_session.add(thread)
    db_session.commit()
    
    # Pre-add an entry that also exists in the preset to test collision avoidance
    # Let's say "筑基" (Foundation Establishment) is translated manually as "Base Building"
    existing_entry = LorebookEntry(
        thread_id=thread.id,
        original_term="筑基",
        translated_term="Base Building",
        notes="Manual translation"
    )
    db_session.add(existing_entry)
    db_session.commit()
    
    # Apply the xianxia preset
    result = apply_preset(db_session, thread.id, "xianxia")
    
    # Verify result counts
    assert "error" not in result
    assert result["added"] > 0
    assert result["skipped"] >= 1  # Our existing '筑基' should be skipped
    
    # Verify the existing entry was NOT overwritten
    db_session.refresh(existing_entry)
    assert existing_entry.translated_term == "Base Building"
    
    # Verify a new entry from the preset WAS added (e.g., "金丹")
    new_entry = db_session.query(LorebookEntry).filter_by(
        thread_id=thread.id, original_term="金丹"
    ).first()
    assert new_entry is not None
    assert "Core" in new_entry.translated_term  # Usually 'Core Formation' or 'Golden Core'
