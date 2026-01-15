from fastapi import APIRouter

router = APIRouter()

@router.get("/ping")
def ping_services():
    return {"message": "services route OK"}