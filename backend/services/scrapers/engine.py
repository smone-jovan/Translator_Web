from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from database import GlobalSetting, get_db_workspace
from services.ai.factory import AIProviderFactory
from services.ai.settings import resolve_active_base_url, resolve_active_model
from services.scrapers.base import BaseScraperAdapter, ScrapedNovelMetadata
from services.scrapers.adaptive_dom import extract_universal_metadata
from services.scrapers.novel_updates import NovelUpdatesAdapter
from services.scrapers.sfacg import SFACGAdapter
from services.scrapers.novalpie import NovalpieAdapter


class UniversalMetadataAdapter(BaseScraperAdapter):
    """
    Universal plug-and-play metadata adapter for arbitrary novel URLs.
    Uses fetch_html_adaptive + extract_universal_metadata (og:novel:*, JSON-LD, OpenGraph, DOM).
    """

    def __init__(self, workspace: Optional[str] = None):
        self.workspace = workspace

    async def scrape_metadata(
        self,
        query: str,
        search_by: str = "original",
        include_cover: bool = True,
    ) -> ScrapedNovelMetadata:
        url = (query or "").strip()
        if not url.startswith(("http://", "https://")):
            return ScrapedNovelMetadata(
                success=False,
                title="",
                original_title=query,
                synopsis="Universal metadata adapter requires an HTTP(S) URL.",
            )
        try:
            from routers.scrape import fetch_html_adaptive
            html_text, final_url = await fetch_html_adaptive(url, workspace=self.workspace)
            meta = extract_universal_metadata(html_text, url=final_url)
            title = meta.get("title") or ""
            if not title:
                return ScrapedNovelMetadata(
                    success=False,
                    title="",
                    original_title=query,
                    synopsis="Could not extract novel metadata from URL.",
                )
            return ScrapedNovelMetadata(
                success=True,
                title=title,
                original_title=meta.get("original_title") or title,
                author=meta.get("author"),
                genres=meta.get("genres"),
                tags=meta.get("tags"),
                synopsis=meta.get("synopsis"),
                status=meta.get("status"),
                status_coo=meta.get("status"),
                cover_image=meta.get("cover_image") if include_cover else None,
                detail_url=meta.get("detail_url") or final_url,
            )
        except Exception as e:
            return ScrapedNovelMetadata(
                success=False,
                title="",
                original_title=query,
                synopsis=f"Universal metadata scrape failed: {e}",
            )


class MetadataScraperEngine:

    """
    Coordinator engine that manages swappable scraper adapters.
    Handles AI-powered title cleaning before initiating the scrape process.
    """
    
    def __init__(self):
        self.adapters = {
            "novelupdates": NovelUpdatesAdapter(),
            "sfacg": SFACGAdapter(),
            "novalpie": NovalpieAdapter(),
            "universal": UniversalMetadataAdapter(),
        }

    def _get_adapter(self, source: str, workspace: Optional[str] = None, db_session: Session | None = None):
        """
        Returns the adapter for `source`. NovalpieAdapter and UniversalMetadataAdapter read
        per-workspace auth/concurrency from GlobalSetting, so they are built per call with the
        request's workspace (CLAUDE.md invariant #2) instead of reusing the shared instance.
        """
        ws = workspace or (get_db_workspace(db_session) if db_session is not None else None)
        if source == "novalpie" and ws:
            return NovalpieAdapter(workspace=ws)
        if source == "universal":
            return UniversalMetadataAdapter(workspace=ws)
        return self.adapters.get(source)

    @staticmethod
    def _resolve_source(query: str, source: Optional[str]) -> str:
        src = (source or "novelupdates").strip().lower()
        q = (query or "").strip()
        if src == "novalpie" or "novalpie.cc" in q:
            return "novalpie"
        if src == "sfacg" or "sfacg.com" in q:
            return "sfacg"
        if src == "universal":
            return "universal"
        if q.startswith(("http://", "https://")) and "novelupdates.com" not in q:
            return "universal"
        return "novelupdates"

    async def clean_title_with_ai(
        self,
        raw_title: str,
        base_url: str,
        model: str | None = None,
        db_session: Session | None = None,
    ) -> str:
        """Use active LLM provider to clean up raw novel titles."""
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
            provider = AIProviderFactory.get_provider(base_url=base_url, model=model, db_session=db_session)
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

    async def scrape_candidates(
        self,
        query: str,
        source: str = "novelupdates",
        search_by: str = "original",
        include_cover: bool = True,
        db_session: Session = None,
        workspace: Optional[str] = None,
    ) -> List[ScrapedNovelMetadata]:
        """
        Coordinates title cleaning and triggers the chosen scraper adapter to return candidates.
        """
        # 1. Resolve base_url and active_model for AI title cleaning
        lm_url = "http://localhost:1234"
        active_model = None
        if db_session:
            gs_stmt = select(GlobalSetting)
            gs = db_session.execute(gs_stmt).scalar_one_or_none()
            if gs:
                lm_url = resolve_active_base_url(gs)
                active_model = resolve_active_model(gs)

        # 2. Check source bypass/override based on query content
        active_source = self._resolve_source(query, source)

        # 3. Clean query title if not a direct URL/ID
        cleaned_query = query
        if active_source == "novelupdates" and not query.startswith(("http://", "https://")):
            cleaned_query = await self.clean_title_with_ai(query, lm_url, model=active_model, db_session=db_session)
            print(f"✨ [Engine] Raw query: '{query}' -> Cleaned query: '{cleaned_query}'")

        # 4. Trigger active adapter
        adapter = self._get_adapter(active_source, workspace=workspace, db_session=db_session)
        if not adapter:
            return []

        return await adapter.scrape_candidates(cleaned_query, search_by=search_by, include_cover=include_cover)

    async def scrape(
        self,
        query: str,
        source: str = "novelupdates",
        search_by: str = "original",
        include_cover: bool = True,
        db_session: Session = None,
        workspace: Optional[str] = None,
    ) -> ScrapedNovelMetadata:
        """
        Coordinates title cleaning and triggers the chosen scraper adapter.
        """
        # 1. Resolve base_url and active_model for AI title cleaning
        lm_url = "http://localhost:1234"
        active_model = None
        if db_session:
            gs_stmt = select(GlobalSetting)
            gs = db_session.execute(gs_stmt).scalar_one_or_none()
            if gs:
                lm_url = resolve_active_base_url(gs)
                active_model = resolve_active_model(gs)

        # 2. Check source bypass/override based on query content
        active_source = self._resolve_source(query, source)

        # 3. Clean query title if not a direct URL/ID
        cleaned_query = query
        if active_source == "novelupdates" and not query.startswith(("http://", "https://")):
            cleaned_query = await self.clean_title_with_ai(query, lm_url, model=active_model, db_session=db_session)
            print(f"✨ [Engine] Raw query: '{query}' -> Cleaned query: '{cleaned_query}'")

        # 4. Trigger active adapter
        adapter = self._get_adapter(active_source, workspace=workspace, db_session=db_session)
        if not adapter:
            return ScrapedNovelMetadata(
                success=False,
                title="",
                original_title=query,
                synopsis=f"Unsupported scraper source: {active_source}"
            )
            
        return await adapter.scrape_metadata(cleaned_query, search_by=search_by, include_cover=include_cover)
