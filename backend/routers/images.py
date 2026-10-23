import asyncio
import hashlib
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session
from database import get_db, Thread, get_db_workspace, make_workspace_key, normalize_workspace, resolve_workspace
from services.task_registry import spawn_background_task
from services.image_fetcher import fetch_image_adaptive
from services.image_cacher import (
    CACHE_DIR,
    ACTIVE_IMAGE_JOBS,
    guess_image_ext_from_bytes,
    sniff_raster_ext,
    get_cached_image,
    is_safe_cache_path,
    get_thread_remote_image_urls,
    count_cached_images,
    run_thread_image_caching_job,
    get_thread_images,
)

router = APIRouter(prefix="/api", tags=["Images"])

# Konten yang disajikan same-origin tidak boleh dieksekusi sebagai dokumen aktif.
IMAGE_HARDENING_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; sandbox",
}


@router.get("/images/proxy")
async def proxy_image(
    request: Request,
    url: str = Query(..., description="Remote image URL to proxy and cache"),
    force: bool = Query(False, description="Force invalidate cache and redownload fresh image from source")
):
    """
    High-performance image proxy with automatic disk caching and security checks.
    Bypasses CORS/hotlink protection and delivers cached images in <5ms.
    Supports force=True to invalidate cache and re-download broken/stuck images.
    """
    if not url or not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid image URL protocol")

    # Filesystem security invariant: reject NUL bytes
    if "\x00" in url:
        raise HTTPException(status_code=400, detail="Invalid characters in URL")

    # SSRF guard: block requests to internal/private IPs
    from services.security import validate_external_url
    validate_external_url(url)

    # 1. Check local cache first (unless force=True)
    if force:
        url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()
        for existing in CACHE_DIR.glob(f"{url_hash}.*"):
            if existing.is_file() and is_safe_cache_path(existing):
                try:
                    existing.unlink(missing_ok=True)
                except Exception:
                    pass
    else:
        cached = get_cached_image(url)
        if cached:
            data, ext, _ = cached
            # Cache lama dapat berisi SVG/HTML (bukan raster) -> perlakukan sebagai miss
            if sniff_raster_ext(data):
                return Response(
                    content=data,
                    media_type=f"image/{sniff_raster_ext(data)}",
                    headers={
                        **IMAGE_HARDENING_HEADERS,
                        "Cache-Control": "public, max-age=31536000, immutable",
                        "X-Cache-Status": "HIT",
                    }
                )

    # 2. Skip obvious dummy/placeholder domains
    if any(d in url.lower() for d in ["example.com", "placeholder", "test.com"]):
        raise HTTPException(status_code=404, detail="Placeholder URL cannot be proxied")

    # 3. Not in cache; fetch over network
    try:
        # Eskalasi bertingkat (httpx -> curl_cffi -> browser stealth) untuk host berlindung Cloudflare.
        fetched = await fetch_image_adaptive(url, workspace=resolve_workspace(request))
        if fetched is None:
            raise HTTPException(status_code=404, detail="Remote image not found")

        data, ext = fetched
        url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()
        cache_file = (CACHE_DIR / f"{url_hash}.{ext}").resolve()

        if is_safe_cache_path(cache_file):
            cache_file.write_bytes(data)

        return Response(
            content=data,
            media_type=f"image/{ext}",
            headers={
                **IMAGE_HARDENING_HEADERS,
                "Cache-Control": "public, max-age=31536000, immutable",
                "X-Cache-Status": "MISS",
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Failed to retrieve image: {type(e).__name__}")


@router.post("/threads/{thread_id}/cache-images")
async def start_thread_image_cache(thread_id: int, db: Session = Depends(get_db)):
    """
    Scan all chapters in thread and spawn a non-blocking background job to download and cache all illustrations.
    """
    thread = db.get(Thread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    ws = normalize_workspace(get_db_workspace(db))
    job = ACTIVE_IMAGE_JOBS.get(make_workspace_key(ws, thread_id))
    if job and job.get("status") == "running":
        return {
            "status": "already_running",
            "total": job.get("total", 0),
            "cached": job.get("cached", 0),
            "already_cached": job.get("already_cached", 0),
        }

    urls = get_thread_remote_image_urls(db, thread_id)
    already_cached = count_cached_images(urls)

    if not urls:
        return {
            "status": "completed",
            "total": 0,
            "cached": 0,
            "already_cached": 0,
            "message": "No remote illustrations found in thread"
        }

    if already_cached >= len(urls):
        completed_entry = {
            "status": "completed",
            "total": len(urls),
            "cached": already_cached,
            "already_cached": already_cached,
            "errors": 0,
            "error": None
        }
        ACTIVE_IMAGE_JOBS[make_workspace_key(ws, thread_id)] = completed_entry
        return {
            "status": "completed",
            "total": len(urls),
            "cached": already_cached,
            "already_cached": already_cached,
            "message": "All images are already cached on disk"
        }

    # Spawn background task
    spawn_background_task(run_thread_image_caching_job(thread_id, urls, workspace=ws))

    return {
        "status": "started",
        "total": len(urls),
        "cached": already_cached,
        "already_cached": already_cached,
    }


@router.get("/threads/{thread_id}/cache-images/status")
def get_thread_image_cache_status(thread_id: int, db: Session = Depends(get_db)):
    """
    Get current progress and cache statistics for a thread's illustrations.
    """
    thread = db.get(Thread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    ws = normalize_workspace(get_db_workspace(db))
    job = ACTIVE_IMAGE_JOBS.get(make_workspace_key(ws, thread_id))
    if job:
        total = job.get("total", 0)
        cached = job.get("cached", 0)
        return {
            "status": job.get("status", "idle"),
            "total": total,
            "cached": cached,
            "already_cached": job.get("already_cached", 0),
            "is_all_cached": cached >= total and total > 0,
            "percent": int((cached / total) * 100) if total > 0 else 100,
            "error": job.get("error"),
        }

    # If no job has been run this session, calculate disk state on demand
    urls = get_thread_remote_image_urls(db, thread_id)
    total = len(urls)
    cached = count_cached_images(urls) if total > 0 else 0

    return {
        "status": "completed" if total > 0 and cached >= total else "idle",
        "total": total,
        "cached": cached,
        "already_cached": cached,
        "is_all_cached": cached >= total and total > 0,
        "percent": int((cached / total) * 100) if total > 0 else 100,
        "error": None,
    }


@router.get("/threads/{thread_id}/images")
def list_thread_images(thread_id: int, db: Session = Depends(get_db)):
    """
    List all illustrations present in a thread novel, organized with chapter metadata.
    """
    thread = db.get(Thread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    images = get_thread_images(db, thread_id)
    return {
        "thread_id": thread_id,
        "total_images": len(images),
        "images": images,
    }


def format_bytes(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    else:
        return f"{size / (1024 * 1024 * 1024):.2f} GB"


@router.get("/cache/images/stats")
async def get_image_cache_stats():
    """Return total number and size of cached images on disk."""
    total_count = 0
    total_bytes = 0

    if CACHE_DIR.exists():
        for file in CACHE_DIR.glob("*"):
            if file.is_file() and is_safe_cache_path(file):
                total_count += 1
                try:
                    total_bytes += file.stat().st_size
                except Exception:
                    pass

    return {
        "count": total_count,
        "total_bytes": total_bytes,
        "formatted_size": format_bytes(total_bytes),
    }


@router.post("/cache/images/clear")
def clear_image_cache(db: Session = Depends(get_db)):
    """Safely delete cached images from disk and clear active image jobs for the current workspace."""
    deleted_count = 0
    freed_bytes = 0

    if CACHE_DIR.exists():
        for file in CACHE_DIR.glob("*"):
            if file.is_file() and is_safe_cache_path(file):
                try:
                    size = file.stat().st_size
                    file.unlink()
                    deleted_count += 1
                    freed_bytes += size
                except Exception:
                    pass

    ws = getattr(db, "_workspace", "main").lower()
    for key in list(ACTIVE_IMAGE_JOBS.keys()):
        if isinstance(key, tuple) and len(key) > 0 and str(key[0]).lower() == ws:
            ACTIVE_IMAGE_JOBS.pop(key, None)
        elif not isinstance(key, tuple):
            ACTIVE_IMAGE_JOBS.pop(key, None)

    return {
        "status": "success",
        "deleted_count": deleted_count,
        "freed_bytes": freed_bytes,
        "formatted_freed": format_bytes(freed_bytes),
    }
