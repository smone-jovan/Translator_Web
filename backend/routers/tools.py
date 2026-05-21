import io
import re

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
import urllib.parse

from services.cleaner_tools import CleanerTools


router = APIRouter(prefix="/api/tools", tags=["Tools"])


@router.post("/txt-cleaner-file")
async def clean_txt_file(file: UploadFile = File(...)):
    """Upload .txt, clean noise via rule-based Python, return cleaned .txt for download."""
    if not file.filename or not file.filename.lower().endswith(".txt"):
        raise HTTPException(400, "File must be .txt")

    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("latin-1", errors="ignore")

    cleaned, _ = CleanerTools.clean_text_block(text)
    if not cleaned.strip():
        raise HTTPException(422, "Cleaner removed everything; source file may be invalid or fully noisy.")

    clean_name = re.sub(r"[^\w\-_.]", "_", file.filename.rsplit(".", 1)[0])
    out_name = f"{clean_name}_cleaned.txt"
    payload = io.BytesIO(cleaned.encode("utf-8"))
    
    filename_encoded = urllib.parse.quote(out_name)

    return StreamingResponse(
        payload,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=utf-8''{filename_encoded}"}
    )
