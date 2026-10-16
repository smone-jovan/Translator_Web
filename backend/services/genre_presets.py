"""
Cultivation Rank & Genre Preset System (ADR-073).

Pre-built lorebook templates for common Chinese web novel power/rank systems.
Supports bilingual output (English & Indonesian) synchronized with GlobalSetting.target_language.
Presets are ADDITIVE — they do not overwrite existing lorebook entries.
"""

from sqlalchemy import select, func
from sqlalchemy.orm import Session
from database import LorebookEntry, GlobalSetting


# ---------------------------------------------------------------------------
# Preset Definitions (English Standard)
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

CULTIVATION_XIANXIA_INDONESIAN = [
    # Core Cultivation Ranks (Indonesian localization)
    ("炼气", "Pemurnian Qi", "Tahap awal kultivasi, menyerap energi spiritual alam"),
    ("筑基", "Pembentukan Fondasi", "Membangun fondasi kultivasi tingkat lanjut"),
    ("金丹", "Pembentukan Inti Emas", "Membentuk Inti Emas (Jin Dan) di dalam Dantian"),
    ("元婴", "Jiwa Nascent", "Melahirkan Jiwa Nascent (Yuan Ying) di dalam Inti Emas"),
    ("化神", "Transformasi Dewa", "Mengubah Jiwa Nascent menuju ranah ilahi"),
    ("炼虚", "Pemurnian Kehampaan", "Memurnikan kehampaan untuk melampaui batas fana"),
    ("合体", "Integrasi Tubuh", "Menyatukan tubuh dan jiwa menjadi satu kesatuan utuh"),
    ("大乘", "Mahayana", "Tahap kendaraan agung, mendekati keabadian"),
    ("渡劫", "Transendensi Tribulasi", "Bertahan dari tribulasi surgawi untuk naik ke alam abadi"),
    # Core Concepts
    ("修炼", "Kultivasi", "Praktik melatih energi spiritual demi mencapai kekuatan dan keabadian"),
    ("丹田", "Dantian", "Pusat energi di perut bagian bawah tempat Qi disimpan"),
    ("经脉", "Meridian", "Jalur saluran energi di dalam tubuh tempat mengalirnya Qi"),
    ("灵根", "Akar Spiritual", "Bakat bawaan kultivasi yang menentukan afinitas elemen"),
    ("灵气", "Energi Spiritual", "Energi alam semesta yang diserap untuk kultivasi"),
    ("灵石", "Batu Roh", "Kristal energi spiritual yang digunakan sebagai mata uang dan sumber energi"),
    ("天劫", "Tribulasi Surgawi", "Ujian petir langit sebelum menembus ranah besar"),
    ("突破", "Terobosan", "Naik ke tingkat kultivasi berikutnya"),
    ("瓶颈", "Kemacetan Kultivasi", "Batas penghalang yang menghambat kenaikan ranah"),
    # Sect/Organization
    ("宗门", "Sekte", "Organisasi atau perguruan kultivasi"),
    ("长老", "Tetua", "Anggota senior sekte yang memiliki wewenang tinggi"),
    ("宗主", "Ketua Sekte", "Pemimpin tertinggi sebuah sekte kultivasi"),
    ("掌门", "Pemimpin Sekte", "Kepala perguruan atau sekte"),
    ("老祖", "Leluhur Tua", "Pendiri atau leluhur kuno sekte yang sangat kuat"),
    ("弟子", "Murid", "Pengikut atau pelajar di dalam sekte"),
    ("内门弟子", "Murid Dalam", "Murid elit dengan akses ke ajaran inti sekte"),
    ("外门弟子", "Murid Luar", "Murid reguler dengan akses dasar"),
    ("真传弟子", "Murid Inti", "Murid warisan langsung yang dibimbing oleh Tetua atau Ketua Sekte"),
    # Relationships
    ("师兄", "Kakak Senior", "Saudara seperguruan laki-laki yang lebih senior (Shixiong)"),
    ("师姐", "Kakak Senior", "Saudara seperguruan perempuan yang lebih senior (Shijie)"),
    ("师弟", "Adik Junior", "Saudara seperguruan laki-laki yang lebih junior (Shidi)"),
    ("师妹", "Adik Junior", "Saudara seperguruan perempuan yang lebih junior (Shimei)"),
    ("师父", "Guru", "Guru atau mentor pembimbing kultivasi (Shifu)"),
    ("道友", "Rekan Taois", "Sapaan sopan antar sesama kultivator"),
    # Items
    ("法宝", "Pusaka Sakti", "Senjata atau artefak kultivator berkekuatan magis"),
    ("灵丹", "Pil Roh", "Pil obat yang diracik dari tanaman herbal spiritual"),
    ("功法", "Teknik Kultivasi", "Kitab atau metode olah napas untuk menyerap energi spiritual"),
    ("阵法", "Formasi", "Susunan formasi mantra dengan berbagai efek magis"),
    ("灵兽", "Binatang Roh", "Makhluk atau binatang yang memiliki kekuatan spiritual"),
    ("储物戒", "Cincin Penyimpanan", "Cincin dimensi ruang untuk menyimpan barang"),
]

CULTIVATION_WUXIA_STANDARD = [
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

CULTIVATION_WUXIA_INDONESIAN = [
    ("江湖", "Jianghu", "Dunia persilatan — komunitas pendekar pengembara dan kehormatan"),
    ("武功", "Ilmu Silat", "Keahlian dan teknik bela diri"),
    ("内力", "Tenaga Dalam", "Kekuatan batin yang dilatih melalui pernapasan dan meditasi"),
    ("真气", "Qi Sejati", "Tenaga dalam murni tingkat tinggi"),
    ("轻功", "Ilmu Meringankan Tubuh", "Teknik gerakan cepat dan lompatan ringan di udara (Qinggong)"),
    ("暗器", "Senjata Rahasia", "Senjata lempar tersembunyi seperti jarum atau pisau terbang"),
    ("穴位", "Titik Akupunktur", "Titik tekan pada jalur meridian tubuh"),
    ("掌法", "Jurus Tapak", "Teknik bela diri menggunakan telapak tangan terbuka"),
    ("剑法", "Jurus Pedang", "Teknik dan aliran ilmu berpedang"),
    ("拳法", "Jurus Tinju", "Teknik pertarungan tangan kosong"),
    ("武林", "Dunia Persilatan", "Kalangan dan masyarakat pendekar bela diri (Wulin)"),
    ("武林盟主", "Ketua Aliansi Persilatan", "Pemimpin tertinggi aliansi dunia persilatan"),
    ("门派", "Perguruan", "Aliran atau organisasi bela diri"),
    ("镖局", "Biro Pengawal", "Lembaga jasa pengawalan bersenjata"),
    ("侠客", "Pendekar", "Praktisi bela diri berjiwa kesatria"),
    ("大侠", "Pendekar Besar", "Gelar kehormatan bagi pendekar berbudi luhur yang terkenal"),
    ("点穴", "Totok Jalan Darah", "Teknik melumpuhkan lawan dengan menekan titik meridian"),
    ("毒", "Racun", "Zat mematikan yang digunakan dalam pertarungan atau pembunuhan"),
    ("解药", "Penawar Racun", "Obat penyembuh racun"),
    ("秘籍", "Kitab Pusaka", "Gulungan atau kitab rahasia ilmu bela diri"),
]

CULTIVATION_XUANHUAN_STANDARD = [
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

CULTIVATION_XUANHUAN_INDONESIAN = [
    ("斗之气", "Dou Qi", "Energi Tempur — kekuatan dasar di dunia xuanhuan"),
    ("斗者", "Dou Zhe", "Praktisi Dou — tingkat petarung pemula"),
    ("斗师", "Dou Shi", "Master Dou — tingkat petarung menengah"),
    ("斗灵", "Dou Ling", "Roh Dou — tingkat petarung lanjut"),
    ("斗王", "Dou Wang", "Raja Dou — tingkat petarung kuat"),
    ("斗皇", "Dou Huang", "Kaisar Dou — tingkat petarung elit"),
    ("斗宗", "Dou Zong", "Leluhur Dou — tingkat mendekati puncak"),
    ("斗尊", "Dou Zun", "Yang Mulia Dou — tingkat papan atas"),
    ("斗圣", "Dou Sheng", "Orang Suci Dou — tingkat legendaris"),
    ("斗帝", "Dou Di", "Dewa Kaisar Dou — tingkat tertinggi"),
    ("斗技", "Teknik Dou", "Jurus bertarung yang digerakkan oleh Dou Qi"),
    ("异火", "Api Surgawi", "Fenomena api alam langka berkekuatan dahsyat"),
    ("魔兽", "Binatang Buas Magis", "Monster dengan kekuatan magis bawaan"),
    ("玄气", "Qi Mendalam", "Varian energi mistis mendalam"),
]

IMPERIAL_COURT_STANDARD = [
    ("皇帝", "Emperor", "Supreme ruler of the empire"),
    ("皇后", "Empress", "Primary wife of the Emperor"),
    ("太后", "Empress Dowager", "Mother of the current Emperor"),
    ("太子", "Crown Prince", "Heir apparent to the throne"),
    ("王爷", "Prince", "Royal prince, usually son of the Emperor"),
    ("公主", "Princess", "Daughter of the Emperor"),
    ("丞相", "Prime Minister", "Highest-ranking official in the imperial court"),
    ("将军", "General", "Military commander"),
    ("太监", "Eunuch", "Castrated male servant of the imperial palace"),
    ("皇贵妃", "Imperial Noble Consort", "Highest concubine rank, just below Empress"),
    ("贵妃", "Noble Consort", "Senior concubine rank"),
    ("妃", "Consort", "Middle concubine rank"),
    ("嫔", "Imperial Concubine", "Lower-middle concubine rank"),
    ("贵人", "Noble Lady", "Lower concubine rank"),
    ("常在", "Attendant", "Minor concubine rank"),
    ("答应", "First Attendant", "Lowest formal concubine rank"),
    ("朝堂", "Imperial Court", "The formal government assembly"),
    ("后宫", "Inner Palace", "The women's quarters of the imperial palace"),
    ("龙椅", "Dragon Throne", "The Emperor's throne"),
    ("圣旨", "Imperial Edict", "Official decree from the Emperor"),
    ("大臣", "Minister", "Government official serving the Emperor"),
    ("侍卫", "Imperial Guard", "Personal bodyguard of royalty"),
]

IMPERIAL_COURT_INDONESIAN = [
    ("皇帝", "Kaisar", "Penguasa tertinggi kekaisaran"),
    ("皇后", "Permaisuri", "Istri utama Kaisar"),
    ("太后", "Ibu Suri", "Ibu dari Kaisar yang sedang bertahta"),
    ("太子", "Putra Mahkota", "Pewaris resmi tahta kekaisaran"),
    ("王爷", "Pangeran", "Bangsawan kerajaan, putra atau saudara Kaisar"),
    ("公主", "Putri", "Anak perempuan Kaisar"),
    ("丞相", "Perdana Menteri", "Pejabat tertinggi di istana kekaisaran"),
    ("将军", "Jenderal", "Panglima militer kekaisaran"),
    ("太监", "Kasim", "Pelayan istana kekaisaran"),
    ("皇贵妃", "Selir Agung Kekaisaran", "Tingkat selir tertinggi tepat di bawah Permaisuri"),
    ("贵妃", "Selir Mulia", "Tingkat selir senior"),
    ("妃", "Selir Utama", "Tingkat selir menengah atas"),
    ("嫔", "Selir Kekaisaran", "Tingkat selir menengah"),
    ("贵人", "Wanita Mulia", "Tingkat selir rendah"),
    ("常在", "Dayang Kehormatan", "Tingkat selir minor"),
    ("答应", "Dayang Istana", "Tingkat selir formal terendah"),
    ("朝堂", "Balairung Istana", "Sidang pemerintahan resmi kekaisaran"),
    ("后宫", "Istana Dalam", "Kediaman para permaisuri dan selir Kaisar (Harem Istana)"),
    ("龙椅", "Tahta Naga", "Singgasana Kaisar"),
    ("圣旨", "Titah Kaisar", "Dekrit resmi dari Kaisar"),
    ("大臣", "Menteri", "Pejabat tinggi istana yang melayani Kaisar"),
    ("侍卫", "Pengawal Kekaisaran", "Pengawal pribadi keluarga kerajaan"),
]


PRESETS = {
    "xianxia": {
        "name": "Xianxia / Cultivation (Standard)",
        "description": "Standard cultivation rank system used in most xianxia novels. Includes Qi Refining → Foundation Establishment → Core Formation → Nascent Soul → Deity Transformation → etc.",
        "entries": CULTIVATION_XIANXIA_STANDARD,
        "entries_id": CULTIVATION_XIANXIA_INDONESIAN,
    },
    "wuxia": {
        "name": "Wuxia / Martial Arts",
        "description": "Jianghu martial arts terminology. Includes internal energy, lightness skills, acupoints, weapons, and martial world organizations.",
        "entries": CULTIVATION_WUXIA_STANDARD,
        "entries_id": CULTIVATION_WUXIA_INDONESIAN,
    },
    "xuanhuan": {
        "name": "Xuanhuan / High Fantasy (Battle Through the Heavens style)",
        "description": "Xuanhuan power rank system based on Dou Qi. Includes Dou Zhe → Dou Shi → Dou Wang → Dou Huang → Dou Zong → Dou Zun → Dou Saint → Dou Di.",
        "entries": CULTIVATION_XUANHUAN_STANDARD,
        "entries_id": CULTIVATION_XUANHUAN_INDONESIAN,
    },
    "imperial": {
        "name": "Imperial Court / Historical Dynasty",
        "description": "Imperial court titles, concubine ranks, and dynasty terminology for historical/court novels.",
        "entries": IMPERIAL_COURT_STANDARD,
        "entries_id": IMPERIAL_COURT_INDONESIAN,
    },
}


def list_presets() -> list[dict]:
    """Return a list of available presets with their metadata."""
    return [
        {
            "key": key,
            "name": preset["name"],
            "description": preset["description"],
            "entry_count": len(preset["entries"]),
            "languages": ["Indonesian", "English"],
        }
        for key, preset in PRESETS.items()
    ]


def apply_preset(
    db: Session,
    thread_id: int,
    preset_key: str,
    target_language: str | None = None,
    lock_entries: bool = True,
) -> dict:
    """
    Apply a preset to a thread's lorebook. ADDITIVE — does not overwrite existing entries.
    Automatically selects Indonesian or English terminology when target_language is provided.
    Returns a summary dict with counts of added and skipped entries.
    """
    preset = PRESETS.get(preset_key)
    if not preset:
        return {"error": f"Unknown preset: {preset_key}", "added": 0, "skipped": 0}

    use_indonesian = False
    if target_language and str(target_language).strip().lower() in ("indonesian", "id", "bahasa indonesia"):
        use_indonesian = True

    entries_source = preset["entries_id"] if use_indonesian else preset["entries"]
    resolved_lang = "Indonesian" if use_indonesian else "English"

    added = 0
    skipped = 0

    for original_term, translated_term, notes in entries_source:
        exists_stmt = select(LorebookEntry).where(
            LorebookEntry.thread_id == thread_id,
            func.lower(func.trim(LorebookEntry.original_term)) == original_term.lower().strip()
        )
        existing = db.execute(exists_stmt).scalars().first()

        if existing:
            if existing.is_archived:
                existing.is_archived = False
                if not existing.notes:
                    existing.notes = f"{notes} (Preset: {preset['name']})"
                added += 1
            else:
                skipped += 1
            continue

        new_entry = LorebookEntry(
            thread_id=thread_id,
            original_term=original_term,
            translated_term=translated_term,
            notes=f"{notes} (Preset: {preset['name']})",
            is_locked=bool(lock_entries),
            is_archived=False,
            # ADR-122: unlocked preset terms must not be the first ones archived at the limit
            usage_count=1,
            last_used_at=func.now(),
        )
        db.add(new_entry)
        added += 1

    if added > 0:
        db.commit()
        from services.context_engine import ContextEngine
        ContextEngine.enforce_context_limit(db, thread_id)
        print(f"[PRESET] Applied '{preset['name']}' ({resolved_lang}) to thread {thread_id}: {added} added, {skipped} skipped.")

    return {
        "preset": preset["name"],
        "language": resolved_lang,
        "added": added,
        "skipped": skipped,
        "total_in_preset": len(entries_source),
    }
