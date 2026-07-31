from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import database
from database import switch_workspace
from services.background_translator import BackgroundTranslator

router = APIRouter(prefix="/api/system", tags=["system"])

class WorkspaceSwitchRequest(BaseModel):
    workspace: str
    pin: str | None = None

@router.post("/workspace")
async def switch_workspace_endpoint(req: WorkspaceSwitchRequest):
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
            target = "main" if database.ACTIVE_WORKSPACE == "ghost" else "ghost"

        # Cancel all background tasks before switching to prevent data leakage or DB crashes
        await BackgroundTranslator.stop_all_batches()
        
        switch_workspace(target)
        return {"status": "ok", "workspace": target}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/workspace/current")
async def get_current_workspace():
    return {"workspace": database.ACTIVE_WORKSPACE}
