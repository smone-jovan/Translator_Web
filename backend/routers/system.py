from fastapi import APIRouter, HTTPException, Response, Request
from pydantic import BaseModel
import database
from database import switch_workspace
from services.background_translator import BackgroundTranslator
from services import pin

router = APIRouter(prefix="/api/system", tags=["system"])

class WorkspaceSwitchRequest(BaseModel):
    workspace: str
    pin: str | None = None

@router.post("/workspace")
async def switch_workspace_endpoint(req: WorkspaceSwitchRequest, response: Response, request: Request):
    if req.workspace not in ["main", "ghost", "toggle"]:
        raise HTTPException(status_code=400, detail="Invalid workspace")

    client = request.client.host if request.client else "unknown"
    locked_for = pin.seconds_locked(client)
    if locked_for:
        raise HTTPException(status_code=429, detail=f"Terlalu banyak percobaan. Coba lagi dalam {locked_for} detik.")

    # Fetch expected PIN from main workspace global settings
    from database import SessionLocalMain, GlobalSetting
    with SessionLocalMain() as db_main:
        gs = db_main.query(GlobalSetting).first()
        stored_pin = gs.ghost_pin if (gs and gs.ghost_pin) else pin.DEFAULT_GHOST_PIN
        pin_ok = pin.verify_pin(stored_pin, req.pin)
        if pin_ok and gs and not pin.is_hashed(gs.ghost_pin):
            gs.ghost_pin = pin.hash_pin(req.pin or "")  # migrasi plaintext -> scrypt
            db_main.commit()

    # Both directions require valid PIN
    if not pin_ok:
        pin.record_failure(client)
        raise HTTPException(status_code=401, detail="Invalid PIN")
    pin.clear_failures(client)

    try:
        # Determine target
        target = req.workspace
        if target == "toggle":
            current_ws = database.resolve_workspace(request)
            target = "main" if current_ws == "ghost" else "ghost"

        switch_workspace(target)
        response.set_cookie(key="readomni_workspace", value=target, httponly=False, samesite="lax", path="/", max_age=2592000)
        if target == "ghost":
            token = database.issue_ghost_session()
            response.set_cookie(
                key=database.GHOST_SESSION_COOKIE, value=token, httponly=True, samesite="strict",
                path="/", max_age=database.GHOST_SESSION_TTL_SECONDS,
            )
        else:
            database.revoke_ghost_session(request.cookies.get(database.GHOST_SESSION_COOKIE))
            response.delete_cookie(database.GHOST_SESSION_COOKIE, path="/")
        return {"status": "ok", "workspace": target}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/workspace/current")
async def get_current_workspace(request: Request):
    ws = database.resolve_workspace(request)
    return {"workspace": ws}
