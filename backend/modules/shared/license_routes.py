from fastapi import APIRouter

from modules.shared.license_state import get_license_state

router = APIRouter()


@router.get("/status")
async def get_local_license_status():
    return {"success": True, "data": get_license_state()}
