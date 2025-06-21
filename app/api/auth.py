from fastapi import APIRouter, HTTPException, status
from app.services.auth import generate_api_key, validate_api_key, revoke_api_key, list_company_api_keys
from uuid import UUID
from typing import List

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/generate")
async def create_api_key(company_id: UUID, name: str):
    result = await generate_api_key(company_id, name)
    return result

@router.post("/validate")
async def check_api_key(api_key: str):
    result = await validate_api_key(api_key)
    if not result:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return result

@router.post("/revoke")
async def revoke_key(api_key_id: UUID):
    success = await revoke_api_key(api_key_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found or already revoked")
    return {"status": "revoked"}

@router.get("/list/{company_id}", response_model=List[dict])
async def list_keys(company_id: UUID):
    keys = await list_company_api_keys(company_id)
    return [key.dict() for key in keys] 