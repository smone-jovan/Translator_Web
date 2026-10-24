"""
FastAPI main entry point — AI Translator Web Backend
"""

import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

import ipaddress
import os
from pathlib import Path
import mimetypes
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from database import init_db
from services.image_fetcher import sniff_raster_ext

from routers import scrape, epub, translate, image_translate, pdf_translate, image_batch_translate, threads, lorebook, context, export, settings, polish, batch, tools, relationships, discovery, toc, system, images


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inisialisasi database saat server pertama kali jalan."""
    init_db(target="all")
    try:
        from database import SessionLocalMain, SessionLocalGhost, Chapter
        from sqlalchemy import update
        for session_factory, db_name in [(SessionLocalMain, "app.db"), (SessionLocalGhost, "ghost.db")]:
            try:
                with session_factory() as db:
                    db.execute(
                        update(Chapter)
                        .where(Chapter.translation_status == "processing")
                        .values(translation_status="idle")
                    )
                    db.commit()
            except Exception as ex:
                print(f"[WARN] Failed to reset stale processing chapters in {db_name}: {ex}")
    except Exception as e:
        print(f"[WARN] Failed to reset stale processing chapters: {e}")
    print("[OK] Database initialized - all databases ready.")
    yield
    print("🛑 [Shutdown] Stopping background tasks and cleaning up resources...")
    try:
        from services.background_translator import BackgroundTranslator
        await BackgroundTranslator.stop_all_batches()
    except Exception as e:
        print(f"[WARN] Error stopping background translation batches: {e}")
    try:
        from services.scrapers.novalpie import _cleanup_all_browsers
        _cleanup_all_browsers()
    except Exception as e:
        print(f"[WARN] Error cleaning up browser processes: {e}")


app = FastAPI(
    title="AI Translator Web — Backend",
    description="API untuk scraping, EPUB parsing, dan translasi via LM Studio lokal.",
    version="0.1.0",
    lifespan=lifespan,
)

_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
_extra_allowed_hosts = {h.strip().lower() for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h.strip()}


def is_allowed_host(host_header: str) -> bool:
    """Tolak Host berupa nama domain asing (DNS rebinding, A-02). Literal IP, localhost, *.local, dan ALLOWED_HOSTS lolos."""
    host = host_header.strip().lower()
    if host.startswith("["):
        host = host[1:].split("]", 1)[0]
    elif host.count(":") == 1:
        host = host.rsplit(":", 1)[0]
    if not host:
        return False
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        pass
    return host in _LOOPBACK_HOSTS or host.endswith(".local") or host in _extra_allowed_hosts


@app.middleware("http")
async def reject_foreign_host(request, call_next):
    if not is_allowed_host(request.headers.get("host", "")):
        return JSONResponse({"detail": "Invalid host header"}, status_code=400)
    return await call_next(request)


# CORS — Restrict to loopback, private LAN (RFC 1918), and local mDNS to prevent arbitrary internet origin abuse
allowed_origins_env = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]
cors_origin_regex = (
    r"^https?://(localhost|127\.0\.0\.1|"
    r"192\.168\.\d{1,3}\.\d{1,3}|"
    r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
    r"172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|"
    r"[a-zA-Z0-9-]+\.local)(:\d+)?$"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins_env if allowed_origins_env else [],
    allow_origin_regex=cors_origin_regex if not allowed_origins_env else None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

os.makedirs("uploads/images", exist_ok=True)

def guess_image_ext(file_path: str) -> str:
    try:
        with open(file_path, "rb") as f:
            header = f.read(12)
        return sniff_raster_ext(header) or ""
    except Exception:
        return ""

@app.get("/images/{rest_of_path:path}", tags=["Images"])
async def serve_images(rest_of_path: str):
    if "\x00" in rest_of_path or not rest_of_path.strip():
        raise HTTPException(status_code=403, detail="Access denied")

    base_dir = Path("uploads/images").resolve()
    try:
        cleaned_rel = rest_of_path.lstrip("/\\")
        # Drive-letter paths (C:/...) are absolute on Windows; reject them on every OS for consistency.
        if len(cleaned_rel) >= 2 and cleaned_rel[1] == ":" and cleaned_rel[0].isalpha():
            raise HTTPException(status_code=403, detail="Access denied")
        candidate = (base_dir / cleaned_rel).resolve()
        is_safe = candidate.is_relative_to(base_dir)
    except Exception:
        raise HTTPException(status_code=403, detail="Access denied")

    if not is_safe or candidate == base_dir:
        raise HTTPException(status_code=403, detail="Access denied")

    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="Image not found")

    # Tipe ditentukan dari magic bytes (bukan ekstensi); selain raster -> 404 (cegah stored XSS via SVG/HTML).
    ext = guess_image_ext(str(candidate))
    if not ext:
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(
        str(candidate),
        media_type=f"image/{ext}",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )


@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok", "message": "AI Translator Backend is running."}


# Register all routers
app.include_router(scrape.router)
app.include_router(epub.router)
app.include_router(translate.router)
app.include_router(image_translate.router)
app.include_router(pdf_translate.router)
app.include_router(image_batch_translate.router)
app.include_router(threads.router)
app.include_router(lorebook.router)
app.include_router(context.router)
app.include_router(export.router)
app.include_router(settings.router)
app.include_router(polish.router)
app.include_router(batch.router)
app.include_router(tools.router)
app.include_router(relationships.router)
app.include_router(discovery.router)
app.include_router(toc.router)
app.include_router(system.router)
app.include_router(images.router)
