"""
FastAPI main entry point — AI Translator Web Backend
"""

import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from routers import scrape, epub, translate, threads, lorebook, context, export

app = FastAPI(
    title="AI Translator Web — Backend",
    description="API untuk scraping, EPUB parsing, dan translasi via LM Studio lokal.",
    version="0.1.0",
)

# CORS — izinkan request dari frontend Vite
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    """Inisialisasi database saat server pertama kali jalan."""
    init_db()
    print("[OK] Database initialized - app.db ready.")


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
