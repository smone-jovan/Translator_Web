from fastapi import APIRouter, HTTPException, Response, Request
from pydantic import BaseModel
import database
from database import switch_workspace
from services.background_translator import BackgroundTranslator

router = APIRouter(prefix="/api/system", tags=["system"])

class WorkspaceSwitchRequest(BaseModel):
    workspace: str
    pin: str | None = None

@router.post("/workspace")
async def switch_workspace_endpoint(req: WorkspaceSwitchRequest, response: Response, request: Request):
    if req.workspace not in ["main", "ghost", "toggle"]:
        raise HTTPException(status_code=400, detail="Invalid workspace")

    # Fetch expected PIN from main workspace global settings
    from database import SessionLocalMain, GlobalSetting
    with SessionLocalMain() as db_main:
        gs = db_main.query(GlobalSetting).first()
        expected_pin = gs.ghost_pin if (gs and gs.ghost_pin) else "03697"

    # Both directions require valid PIN
    if req.pin != expected_pin:
        raise HTTPException(status_code=401, detail="Invalid PIN")

    try:
        # Determine target
        target = req.workspace
        if target == "toggle":
            current_ws = database.resolve_workspace(request)
            target = "main" if current_ws == "ghost" else "ghost"

        switch_workspace(target)
        response.set_cookie(key="readomni_workspace", value=target, httponly=False, samesite="lax", path="/", max_age=2592000)
        return {"status": "ok", "workspace": target}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/workspace/current")
async def get_current_workspace(request: Request):
    ws = database.resolve_workspace(request)
    return {"workspace": ws}
