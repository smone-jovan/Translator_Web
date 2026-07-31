"""
Cultivation Rank Preset System (ADR-073).

Pre-built lorebook templates for common Chinese web novel power/rank systems.
Users can apply a preset to seed their thread's lorebook with consistent terminology.
Presets are ADDITIVE — they don't overwrite existing lorebook entries.
"""

from sqlalchemy import select, func
from sqlalchemy.orm import Session
from database import LorebookEntry


# ---------------------------------------------------------------------------
# Preset Definitions
# Each preset is a list of (original_term, translated_term, notes) tuples.
# ---------------------------------------------------------------------------

CULTIVATION_XIANXIA_STANDARD = [
    # Core Cultivation Ranks (most common xianxia hierarchy)
    ("炼气", "Qi Refining", "First stage of cultivation, absorbing ambient spiritual energy"),
    ("筑基", "Foundation Establishment", "Building the foundation for higher cultivation"),
    ("金丹", "Core Formation", "Forming a golden core (金丹) in the dantian"),
    ("元婴", "Nascent Soul", "Birthing a nascent soul within the golden core"),
    ("化神", "Deity Transformation", "Transforming one's nascent soul toward divinity"),
    ("炼虚", "Void Refining", "Refining the void to transcend mortal limitations"),
    ("合体", "Body Integration", "Merging body and soul into a unified whole"),
    ("大乘", "Mahayana", "The great vehicle stage, nearing immortality"),
    ("渡劫", "Tribulation Transcendence", "Surviving heavenly tribulation to ascend"),
    # Core Concepts
    ("修炼", "Cultivation", "The practice of cultivating spiritual energy for power"),
    ("丹田", "Dantian", "Energy center in the lower abdomen where qi is stored"),
    ("经脉", "Meridians", "Energy channels in the body through which qi flows"),
    ("灵根", "Spiritual Root", "Innate talent for cultivation, determines affinity"),
    ("灵气", "Spiritual Energy", "Ambient energy in the world used for cultivation"),
    ("灵石", "Spirit Stone", "Crystallized spiritual energy used as currency/power source"),
    ("天劫", "Heavenly Tribulation", "Divine lightning trial before major breakthroughs"),
    ("突破", "Breakthrough", "Advancing to the next cultivation stage"),
    ("瓶颈", "Bottleneck", "Barrier preventing cultivation advancement"),
    # Sect/Organization
    ("宗门", "Sect", "Cultivation organization/school"),
    ("长老", "Elder", "Senior sect member with authority"),
    ("宗主", "Sect Master", "Leader of a cultivation sect"),
    ("掌门", "Sect Leader", "Head/leader of a sect (alternative to 宗主)"),
    ("老祖", "Patriarch", "Ancient powerful founder or ancestor of a sect"),
    ("弟子", "Disciple", "Student of a sect or master"),
    ("内门弟子", "Inner Disciple", "Elite disciple with access to core teachings"),
    ("外门弟子", "Outer Disciple", "Regular disciple with basic access"),
    ("真传弟子", "True Disciple", "Personally taught disciple of an elder/master"),
    # Relationships
    ("师兄", "Senior Brother", "Male fellow disciple who joined earlier"),
    ("师姐", "Senior Sister", "Female fellow disciple who joined earlier"),
    ("师弟", "Junior Brother", "Male fellow disciple who joined later"),
    ("师妹", "Junior Sister", "Female fellow disciple who joined later"),
    ("师父", "Master", "Teacher/mentor in cultivation"),
    ("道友", "Fellow Daoist", "Polite address between cultivators"),
    # Items
    ("法宝", "Magical Treasure", "Powerful cultivator weapon/tool"),
    ("灵丹", "Spirit Pill", "Medicinal pill made from spiritual herbs"),
    ("功法", "Cultivation Technique", "Method/manual for cultivating spiritual energy"),
    ("阵法", "Formation", "Magical array/formation with various effects"),
    ("灵兽", "Spirit Beast", "Spiritually-empowered animal/creature"),
    ("储物戒", "Storage Ring", "Spatial ring for carrying items"),
]

CULTIVATION_WUXIA_STANDARD = [
    # Wuxia-specific terms
    ("江湖", "Jianghu", "The martial arts world — a world of wandering fighters and honor"),
    ("武功", "Martial Arts", "Fighting skills and techniques"),
    ("内力", "Internal Energy", "Inner power cultivated through breathing and meditation"),
    ("真气", "True Qi", "Refined internal energy of high purity"),
    ("轻功", "Lightness Skill", "Movement technique for speed and aerial maneuverability"),
    ("暗器", "Hidden Weapons", "Concealed projectile weapons (needles, darts, etc.)"),
    ("穴位", "Acupoint", "Pressure point on the body's meridian system"),
    ("掌法", "Palm Technique", "Open-hand martial arts technique"),
    ("剑法", "Sword Technique", "Swordsmanship form or style"),
    ("拳法", "Fist Technique", "Unarmed combat technique"),
    ("武林", "Martial World", "The community/sphere of martial artists"),
    ("武林盟主", "Martial Alliance Leader", "Supreme leader of the martial arts alliance"),
    ("门派", "School/Sect", "Martial arts organization"),
    ("镖局", "Escort Agency", "Organization providing armed escort services"),
    ("侠客", "Swordsman/Hero", "Chivalrous martial artist"),
    ("大侠", "Great Hero", "Honorific for a renowned righteous martial artist"),
    ("点穴", "Acupoint Sealing", "Technique to disable opponent by striking pressure points"),
    ("毒", "Poison", "Toxic substances used in combat or assassination"),
    ("解药", "Antidote", "Cure for poison"),
    ("秘籍", "Secret Manual", "Hidden martial arts technique scroll"),
]

CULTIVATION_XUANHUAN_STANDARD = [
    # Xuanhuan power system (e.g., Battle Through the Heavens style)
    ("斗之气", "Dou Qi", "Battle energy — the fundamental power in xuanhuan worlds"),
    ("斗者", "Dou Zhe", "Dou Practitioner — entry-level fighter rank"),
    ("斗师", "Dou Shi", "Dou Master — intermediate fighter rank"),
    ("斗灵", "Dou Ling", "Dou Spirit — advanced fighter rank"),
    ("斗王", "Dou Wang", "Dou King — powerful fighter rank"),
    ("斗皇", "Dou Huang", "Dou Emperor — elite fighter rank"),
    ("斗宗", "Dou Zong", "Dou Ancestor — near-peak rank"),
    ("斗尊", "Dou Zun", "Dou Venerable — top-tier rank"),
    ("斗圣", "Dou Saint", "Dou Saint — legendary rank"),
    ("斗帝", "Dou Di", "Dou Emperor/God — supreme rank"),
    ("斗技", "Dou Technique", "Battle technique powered by Dou Qi"),
    ("异火", "Heavenly Flame", "Rare and powerful natural fire phenomenon"),
    ("魔兽", "Magical Beast", "Monsters with innate powers"),
    ("玄气", "Profound Qi", "Mysterious/dark energy variant"),
]

IMPERIAL_COURT_STANDARD = [
    # Imperial/historical titles
    ("皇帝", "Emperor", "Supreme ruler of the empire"),
    ("皇后", "Empress", "Primary wife of the Emperor"),
    ("太后", "Empress Dowager", "Mother of the current Emperor"),
    ("太子", "Crown Prince", "Heir apparent to the throne"),
    ("王爷", "Prince", "Royal prince, usually son of the Emperor"),
    ("公主", "Princess", "Daughter of the Emperor"),
    ("丞相", "Prime Minister", "Highest-ranking official in the imperial court"),
    ("将军", "General", "Military commander"),
    ("太监", "Eunuch", "Castrated male servant of the imperial palace"),
    # Concubine ranks (high to low)
    ("皇贵妃", "Imperial Noble Consort", "Highest concubine rank, just below Empress"),
    ("贵妃", "Noble Consort", "Senior concubine rank"),
    ("妃", "Consort", "Middle concubine rank"),
    ("嫔", "Imperial Concubine", "Lower-middle concubine rank"),
    ("贵人", "Noble Lady", "Lower concubine rank"),
    ("常在", "Attendant", "Minor concubine rank"),
    ("答应", "First Attendant", "Lowest formal concubine rank"),
    # Court terminology
    ("朝堂", "Imperial Court", "The formal government assembly"),
    ("后宫", "Inner Palace", "The women's quarters of the imperial palace"),
    ("龙椅", "Dragon Throne", "The Emperor's throne"),
    ("圣旨", "Imperial Edict", "Official decree from the Emperor"),
    ("大臣", "Minister", "Government official serving the Emperor"),
    ("侍卫", "Imperial Guard", "Personal bodyguard of royalty"),
]


# ---------------------------------------------------------------------------
# All presets registry
# ---------------------------------------------------------------------------

PRESETS = {
    "xianxia": {
        "name": "Xianxia / Cultivation (Standard)",
        "description": "Standard cultivation rank system used in most xianxia novels. Includes Qi Refining → Foundation Establishment → Core Formation → Nascent Soul → Deity Transformation → etc.",
        "entries": CULTIVATION_XIANXIA_STANDARD,
    },
    "wuxia": {
        "name": "Wuxia / Martial Arts",
        "description": "Jianghu martial arts terminology. Includes internal energy, lightness skills, acupoints, weapons, and martial world organizations.",
        "entries": CULTIVATION_WUXIA_STANDARD,
    },
    "xuanhuan": {
        "name": "Xuanhuan / High Fantasy (Battle Through the Heavens style)",
        "description": "Xuanhuan power rank system based on Dou Qi. Includes Dou Zhe → Dou Shi → Dou Wang → Dou Huang → Dou Zong → Dou Zun → Dou Saint → Dou Di.",
        "entries": CULTIVATION_XUANHUAN_STANDARD,
    },
    "imperial": {
        "name": "Imperial Court / Historical Dynasty",
        "description": "Imperial court titles, concubine ranks, and dynasty terminology for historical/court novels.",
        "entries": IMPERIAL_COURT_STANDARD,
    },
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_presets() -> list[dict]:
    """Return a list of available presets with their metadata."""
    return [
        {
            "key": key,
            "name": preset["name"],
            "description": preset["description"],
            "entry_count": len(preset["entries"]),
        }
        for key, preset in PRESETS.items()
    ]


def apply_preset(db: Session, thread_id: int, preset_key: str) -> dict:
    """
    Apply a preset to a thread's lorebook. ADDITIVE — does not overwrite existing entries.

    Returns a summary dict with counts of added and skipped entries.
    """
    preset = PRESETS.get(preset_key)
    if not preset:
        return {"error": f"Unknown preset: {preset_key}", "added": 0, "skipped": 0}

    added = 0
    skipped = 0

    for original_term, translated_term, notes in preset["entries"]:
        # Check if this term already exists (case-insensitive)
        exists_stmt = select(LorebookEntry).where(
            LorebookEntry.thread_id == thread_id,
            func.lower(func.trim(LorebookEntry.original_term)) == original_term.lower().strip()
        )
        existing = db.execute(exists_stmt).scalars().first()

        if existing:
            skipped += 1
            continue

        new_entry = LorebookEntry(
            thread_id=thread_id,
            original_term=original_term,
            translated_term=translated_term,
            notes=f"{notes} (Preset: {preset['name']})",
            is_locked=True,  # Lock preset entries to prevent auto-archival
        )
        db.add(new_entry)
        added += 1

    if added > 0:
        db.commit()
        print(f"[PRESET] Applied '{preset['name']}' to thread {thread_id}: {added} added, {skipped} skipped.")

    return {
        "preset": preset["name"],
        "added": added,
        "skipped": skipped,
        "total_in_preset": len(preset["entries"]),
    }
