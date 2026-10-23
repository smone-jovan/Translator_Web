import asyncio
import hashlib
from pathlib import Path
import re
from typing import Callable, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from database import Chapter, make_workspace_key
from services.security import validate_external_url
from services.image_fetcher import fetch_image_adaptive, sniff_raster_ext

CACHE_DIR = (Path("uploads") / "cache" / "images").resolve()
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# In-memory progress tracking for background thread image caching jobs
# Key: (workspace, thread_id) -> { "status": str, "total": int, "cached": int, "already_cached": int, "errors": int, "error": str | None }
ACTIVE_IMAGE_JOBS: dict[tuple[str, int] | int, dict] = {}



def guess_image_ext_from_bytes(data: bytes) -> str:
    """Inspect magic bytes to determine image format."""
    return sniff_raster_ext(data) or "jpeg"


def is_safe_cache_path(candidate: Path) -> bool:
    """Validate that candidate path resides safely within CACHE_DIR without traversal."""
    try:
        resolved = candidate.resolve()
        return resolved.is_relative_to(CACHE_DIR)
    except Exception:
        return False


def get_cached_image(url: str) -> Optional[tuple[bytes, str, Path]]:
    """Check if an image URL is already cached on disk safely."""
    if "\x00" in url:
        return None

    url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()
    for existing in CACHE_DIR.glob(f"{url_hash}.*"):
        if existing.is_file() and existing.stat().st_size > 0:
            if is_safe_cache_path(existing):
                try:
                    data = existing.read_bytes()
                    ext = guess_image_ext_from_bytes(data) or existing.suffix.lstrip(".") or "jpeg"
                    return data, ext, existing
                except Exception:
                    pass
    return None


async def warm_cover_cache(url: Optional[str], workspace: Optional[str] = None) -> bool:
    """
    Best-effort: unduh cover remote sekali (dengan eskalasi anti-Cloudflare penuh) dan simpan ke
    disk cache, sehingga /api/images/proxy langsung HIT. Tidak pernah melempar; return True bila
    cover sudah/berhasil ter-cache.
    """
    if not url or not url.startswith(("http://", "https://")) or "\x00" in url:
        return False
    if get_cached_image(url):
        return True
    try:
        fetched = await fetch_image_adaptive(url, workspace=workspace)
        if not fetched:
            return False
        data, ext = fetched
        url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()
        cache_file = (CACHE_DIR / f"{url_hash}.{ext}").resolve()
        if not is_safe_cache_path(cache_file):
            return False
        cache_file.write_bytes(data)
        return True
    except Exception as e:
        print(f"[ImageCacher] Cover warm-up skipped ({url[:60]}...: {type(e).__name__})")
        return False


async def prefetch_remote_images(
    urls: List[str],
    on_progress: Optional[Callable[[int, int], None]] = None
) -> dict[str, tuple[bytes, str]]:
    """
    Download and cache remote images concurrently with resilience to dead/fake URLs.
    Thread-safe and async non-blocking.
    """
    if not urls:
        return {}

    sem = asyncio.Semaphore(10)
    results: dict[str, tuple[bytes, str]] = {}
    completed_count = 0

    async def _fetch_one(url: str):
        nonlocal completed_count
        # Skip obvious dummy/placeholder URLs without network call
        if any(d in url.lower() for d in ["example.com", "placeholder", "test.com"]):
            completed_count += 1
            if on_progress:
                on_progress(completed_count, len(urls))
            return

        # SSRF Protection: Validate external URL before network call
        try:
            validate_external_url(url)
        except Exception as e:
            print(f"[ImageCacher] SSRF validation blocked URL: {url} ({e})")
            completed_count += 1
            if on_progress:
                on_progress(completed_count, len(urls))
            return

        # Check cache on disk first
        cached = get_cached_image(url)
        if cached:
            data, ext, _ = cached
            results[url] = (data, ext)
            completed_count += 1
            if on_progress:
                on_progress(completed_count, len(urls))
            return

        url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()

        # Not in cache; fetch with tiered escalation (httpx -> curl_cffi). Browser tier is
        # disabled here: bulk prefetch must not spawn a browser per illustration.
        async with sem:
            try:
                fetched = await fetch_image_adaptive(url, allow_browser=False)
                if fetched:
                    data, ext = fetched
                    cache_file = (CACHE_DIR / f"{url_hash}.{ext}").resolve()
                    if is_safe_cache_path(cache_file):
                        cache_file.write_bytes(data)
                    results[url] = (data, ext)
                else:
                    print(f"[Export] Notice: Image skipped ({url[:60]}... not retrievable)")
            except Exception as e:
                print(f"[Export] Notice: Image skipped ({url[:60]}... unreachable: {type(e).__name__})")
            finally:
                completed_count += 1
                if on_progress:
                    on_progress(completed_count, len(urls))

    await asyncio.gather(*[_fetch_one(u) for u in urls])

    return results


def extract_remote_image_urls_from_text(text: str | None) -> set[str]:
    """Extract all remote (http/https) image URLs from markdown or HTML text."""
    if not text:
        return set()
    found = set()
    # 1. Markdown syntax: ![alt](https://...)
    for m in re.finditer(r'!\[.*?\]\((https?://[^\s\)]+)\)', text):
        found.add(m.group(1))
    # 2. HTML syntax: <img ... src="https://..." ...>
    for m in re.finditer(r'<img\s+[^>]*?src=["\'](https?://[^"\']+)["\']', text, flags=re.IGNORECASE):
        found.add(m.group(1))
    # 3. Escaped HTML: &lt;img ... src="https://..." ...&gt;
    for m in re.finditer(r'&lt;img\s+[^>]*?src=["\'](https?://[^"\']+)["\']', text, flags=re.IGNORECASE):
        found.add(m.group(1))
    return found


def get_thread_remote_image_urls(db: Session, thread_id: int) -> list[str]:
    """Scan all chapters in thread for unique remote image URLs."""
    stmt = (
        select(Chapter.content_original, Chapter.content_translated)
        .where(Chapter.thread_id == thread_id)
        .order_by(Chapter.order.asc())
    )
    rows = db.execute(stmt).all()
    all_urls: set[str] = set()
    for row in rows:
        orig, trans = row[0], row[1]
        all_urls.update(extract_remote_image_urls_from_text(orig))
        all_urls.update(extract_remote_image_urls_from_text(trans))
    return sorted(list(all_urls))


def extract_images_with_metadata_from_chapter(
    chapter_id: int,
    chapter_order: int,
    chapter_title: str,
    text: str | None
) -> list[dict]:
    """Extract image tags with URLs, alt texts, and chapter metadata."""
    if not text:
        return []

    results = []
    seen_urls = set()

    # 1. Markdown syntax: ![alt](url)
    for m in re.finditer(r'!\[(.*?)\]\(((?:https?://|/images/)[^\s\)]+)\)', text):
        alt = m.group(1).strip()
        url = m.group(2).strip()
        if url and url not in seen_urls:
            seen_urls.add(url)
            results.append({
                "url": url,
                "chapter_id": chapter_id,
                "chapter_order": chapter_order,
                "chapter_title": chapter_title,
                "alt": alt
            })

    # 2. HTML syntax: <img ... src="url" ...>
    for m in re.finditer(r'<img\s+[^>]*?src=["\']((?:https?://|/images/)[^"\']+)["\']([^>]*?)>', text, flags=re.IGNORECASE):
        url = m.group(1).strip()
        rest = m.group(2)
        alt_match = re.search(r'alt=["\'](.*?)["\']', rest, flags=re.IGNORECASE)
        alt = alt_match.group(1).strip() if alt_match else ""
        if url and url not in seen_urls:
            seen_urls.add(url)
            results.append({
                "url": url,
                "chapter_id": chapter_id,
                "chapter_order": chapter_order,
                "chapter_title": chapter_title,
                "alt": alt
            })

    # 3. Escaped HTML: &lt;img ... src="url" ... &gt;
    for m in re.finditer(r'&lt;img\s+[^>]*?src=["\']((?:https?://|/images/)[^"\']+)["\']([^&]*?)&gt;', text, flags=re.IGNORECASE):
        url = m.group(1).strip()
        rest = m.group(2)
        alt_match = re.search(r'alt=["\'](.*?)["\']', rest, flags=re.IGNORECASE)
        alt = alt_match.group(1).strip() if alt_match else ""
        if url and url not in seen_urls:
            seen_urls.add(url)
            results.append({
                "url": url,
                "chapter_id": chapter_id,
                "chapter_order": chapter_order,
                "chapter_title": chapter_title,
                "alt": alt
            })

    return results


def get_thread_images(db: Session, thread_id: int) -> list[dict]:
    """Retrieve all images with chapter location metadata for a thread novel."""
    stmt = (
        select(
            Chapter.id,
            Chapter.order,
            Chapter.title_translated,
            Chapter.title_original,
            Chapter.content_translated,
            Chapter.content_original
        )
        .where(Chapter.thread_id == thread_id, Chapter.image_count > 0)
        .order_by(Chapter.order.asc())
    )
    rows = db.execute(stmt).all()
    all_images = []
    seen_in_thread = set()

    for row in rows:
        ch_id, order, title_trans, title_orig, text_trans, text_orig = row
        title = title_trans or title_orig or f"Chapter {order}"
        imgs_trans = extract_images_with_metadata_from_chapter(ch_id, order, title, text_trans)
        imgs_orig = extract_images_with_metadata_from_chapter(ch_id, order, title, text_orig)
        chapter_imgs = []
        for img in imgs_trans + imgs_orig:
            if img["url"] not in seen_in_thread:
                seen_in_thread.add(img["url"])
                chapter_imgs.append(img)

        total_in_ch = len(chapter_imgs)
        for idx, img in enumerate(chapter_imgs, 1):
            img["image_index"] = idx
            img["total_in_chapter"] = total_in_ch
            all_images.append(img)

    return all_images


def count_cached_images(urls: list[str]) -> int:
    """Return count of URLs that are already cached safely on disk."""
    count = 0
    for u in urls:
        if get_cached_image(u):
            count += 1
    return count


async def run_thread_image_caching_job(thread_id: int, urls: list[str], workspace: str = "main"):
    """Background task to fetch and cache all images for a thread."""
    job_key = make_workspace_key(workspace, thread_id)
    if not urls:
        entry = {
            "status": "completed",
            "total": 0,
            "cached": 0,
            "already_cached": 0,
            "errors": 0,
            "error": None
        }
        ACTIVE_IMAGE_JOBS[job_key] = entry
        return

    already_count = count_cached_images(urls)
    entry = {
        "status": "running",
        "total": len(urls),
        "cached": already_count,
        "already_cached": already_count,
        "errors": 0,
        "error": None
    }
    ACTIVE_IMAGE_JOBS[job_key] = entry

    def on_progress(done: int, total: int):
        current_cached = count_cached_images(urls)
        job = ACTIVE_IMAGE_JOBS.get(job_key)
        if job and job["status"] == "running":
            job["cached"] = current_cached

    try:
        await prefetch_remote_images(urls, on_progress=on_progress)
        final_cached = count_cached_images(urls)
        completed_entry = {
            "status": "completed",
            "total": len(urls),
            "cached": final_cached,
            "already_cached": already_count,
            "errors": len(urls) - final_cached,
            "error": None
        }
        ACTIVE_IMAGE_JOBS[job_key] = completed_entry
    except Exception as e:
        error_entry = {
            "status": "error",
            "total": len(urls),
            "cached": count_cached_images(urls),
            "already_cached": already_count,
            "errors": 0,
            "error": str(e)
        }
        ACTIVE_IMAGE_JOBS[job_key] = error_entry
