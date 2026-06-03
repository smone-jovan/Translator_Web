from fastapi import APIRouter

router = APIRouter(prefix="/api/discover", tags=["Discovery"])

@router.get("/popular")
def get_popular_novels():
    """
    Placeholder endpoint for fetching popular novels.
    Future implementation will integrate with the MetadataScraperEngine.
    """
    return {"status": "ok", "data": []}

@router.get("/search")
def search_novels(q: str):
    """
    Placeholder endpoint for searching novels.
    Future implementation will integrate with the MetadataScraperEngine.
    """
    return {"status": "ok", "data": [], "query": q}
