from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.response import BaseResponse
from app.schemas.user_schemas import UserResponse, UserUpdate, ErrorResponse
from app.services.user_service import UserService
from app.middlewares.auth_middleware import get_current_user
from fastapi.responses import JSONResponse
from typing import Any

router = APIRouter(prefix="/user", tags=["users"])

def api_response(success: bool, message: str, data: Any = None, errors: Any = None):
    return {"success": success, "message": message, "data": data, "errors": errors}

@router.get("/me", response_model=BaseResponse[UserResponse], responses={401: {"model": ErrorResponse}})
async def read_users_me(current_user=Depends(get_current_user)):
    try:
        return api_response(True, "User profile fetched", UserResponse(**current_user.__dict__), None)
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content=api_response(False, e.detail, None, e.detail))

@router.put("/me", response_model=BaseResponse[UserResponse], responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}})
async def update_user_me(
    user_update: UserUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        updated_user = await UserService.update_profile(db, current_user.id, user_update)
        return api_response(True, "User profile updated", UserResponse(**updated_user.__dict__), None)
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content=api_response(False, e.detail, None, e.detail))
