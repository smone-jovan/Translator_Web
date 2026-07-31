"""
FastAPI main entry point — AI Translator Web Backend
"""

import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

import os
import mimetypes
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from database import init_db

from routers import scrape, epub, translate, threads, lorebook, context, export, settings, polish, batch, tools, relationships, discovery, toc, system


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inisialisasi database saat server pertama kali jalan."""
    init_db()
    print("[OK] Database initialized - app.db ready.")
    yield


app = FastAPI(
    title="AI Translator Web — Backend",
    description="API untuk scraping, EPUB parsing, dan translasi via LM Studio lokal.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — izinkan request dari frontend Vite (wildcard acceptable for self-hosted LAN app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
        if header.startswith(b"\xff\xd8"): return "jpeg"
        if header.startswith(b"\x89PNG\r\n\x1a\n"): return "png"
        if header.startswith(b"GIF87a") or header.startswith(b"GIF89a"): return "gif"
        if header.startswith(b"RIFF") and header[8:12] == b"WEBP": return "webp"
    except Exception:
        pass
    return ""

@app.get("/images/{rest_of_path:path}", tags=["Images"])
async def serve_images(rest_of_path: str):
    file_path = os.path.join("uploads", "images", rest_of_path)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Try to guess mime type from extension first
    media_type, _ = mimetypes.guess_type(file_path)
    if not media_type:
        # Check magic bytes if no extension
        ext = guess_image_ext(file_path)
        if ext:
            media_type = f"image/{ext}"
        else:
            media_type = "application/octet-stream"
            
    return FileResponse(file_path, media_type=media_type)


@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok", "message": "AI Translator Backend is running."}


# Register all routers
app.include_router(scrape.router)
app.include_router(epub.router)
app.include_router(translate.router)
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
