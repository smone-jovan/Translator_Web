from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel

class ScrapedNovelMetadata(BaseModel):
    success: bool
    title: str
    original_title: str
    author: Optional[str] = None
    genres: Optional[str] = None
    tags: Optional[str] = None
    synopsis: Optional[str] = None
    status: Optional[str] = None
    status_coo: Optional[str] = None
    cover_image: Optional[str] = None
    detail_url: Optional[str] = None

class BaseScraperAdapter(ABC):
    """
    Port definition for all metadata scrapers.
    Concrete adapters implement this to scrape specific websites.
    """
    @abstractmethod
    async def scrape_metadata(self, query: str, search_by: str = "original", include_cover: bool = True) -> ScrapedNovelMetadata:
        """
        Scrapes a single novel's metadata using the provided query (can be title, URL or ID).
        """
        pass
