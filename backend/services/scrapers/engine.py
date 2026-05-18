from sqlalchemy.orm import Session
from sqlalchemy import select

from database import GlobalSetting
from services.ai.factory import AIProviderFactory
from services.scrapers.base import ScrapedNovelMetadata
from services.scrapers.novel_updates import NovelUpdatesAdapter
from services.scrapers.sfacg import SFACGAdapter

class MetadataScraperEngine:
    """
    Coordinator engine that manages swappable scraper adapters.
    Handles AI-powered title cleaning before initiating the scrape process.
    """
    
    def __init__(self):
        self.adapters = {
            "novelupdates": NovelUpdatesAdapter(),
            "sfacg": SFACGAdapter()
        }

    async def clean_title_with_ai(self, raw_title: str, base_url: str) -> str:
        """Use local LLM to clean up raw Chinese titles."""
        if not raw_title:
            return ""
            
        sys_prompt = (
            "You are an expert Chinese web novel database assistant.\n"
            "Your task is to take a raw, messy Chinese novel title (which may contain extra words, descriptive text, "
            "parentheses, tags, or chapter details) and return ONLY the clean, official Chinese title of the novel.\n"
            "Rules:\n"
            "1. Strip all annotations, brackets like 【】, tags like (无女主) or (轻松) or (变百), and ads.\n"
            "2. Respond with ONLY the cleaned Chinese title characters. Do not include any greeting, markdown, note, or translation.\n"
            "3. If the input is already clean or contains English, return it clean without explaining.\n"
            "Example Input: 我怎么可能是圣女？（无女主，变百，轻松）\n"
            "Example Output: 我怎么可能是圣女？"
        )
        user_prompt = f"Please clean this title: {raw_title}"
        
        try:
            provider = AIProviderFactory.get_provider(base_url=base_url)
            messages = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt}
            ]
            cleaned_title = await provider.chat_completion(messages=messages, temperature=0.3)
            cleaned_title = cleaned_title.strip()
            if cleaned_title and len(cleaned_title) <= 200:
                return cleaned_title
        except Exception as e:
            print(f"⚠️ [Engine] Failed to clean title using AI: {e}. Falling back to original.")
            
        return raw_title

    async def scrape(
        self,
        query: str,
        source: str = "novelupdates",
        search_by: str = "original",
        include_cover: bool = True,
        db_session: Session = None
    ) -> ScrapedNovelMetadata:
        """
        Coordinates title cleaning and triggers the chosen scraper adapter.
        """
        # 1. Resolve base_url for AI title cleaning
        lm_url = "http://localhost:1234"
        if db_session:
            gs_stmt = select(GlobalSetting)
            gs = db_session.execute(gs_stmt).scalar_one_or_none()
            if gs:
                lm_url = gs.lm_url

        # 2. Check source bypass/override based on query content
        is_sfacg = (source == "sfacg") or ("sfacg.com" in query)
        active_source = "sfacg" if is_sfacg else "novelupdates"
        
        # 3. Clean query title if not a direct URL/ID
        cleaned_query = query
        if active_source == "novelupdates" and not query.startswith(("http://", "https://")):
            cleaned_query = await self.clean_title_with_ai(query, lm_url)
            print(f"✨ [Engine] Raw query: '{query}' -> Cleaned query: '{cleaned_query}'")

        # 4. Trigger active adapter
        adapter = self.adapters.get(active_source)
        if not adapter:
            return ScrapedNovelMetadata(
                success=False,
                title="",
                original_title=query,
                synopsis=f"Unsupported scraper source: {active_source}"
            )
            
        return await adapter.scrape_metadata(cleaned_query, search_by=search_by, include_cover=include_cover)
