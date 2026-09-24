from fastapi import APIRouter, HTTPException

from app.store import BASELINE, list_baselines

router = APIRouter()


@router.get("/baseline")
def get_all_baselines():
    return {"baselines": list_baselines(), "prototype": True}


@router.get("/baseline/{region}")
def get_baseline(region: str):
    record = BASELINE.get(region)
    if not record:
        raise HTTPException(status_code=404, detail="Unknown region_key")
    return record
