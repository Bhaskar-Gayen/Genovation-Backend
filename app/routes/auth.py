from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.response import BaseResponse
from app.schemas.user_schemas import (
    UserRegister,
    UserLogin,
    OTPRequest,
    OTPVerify,
    PasswordChange,
    UserResponse,
    OTPResponse,
    ErrorResponse,
    RefreshRequest,
    TokenRefreshResponse,
)
from app.services.user_service import UserService
from app.services.otp_service import OTPService
from app.utils.jwt import create_access_token, create_refresh_token, verify_token, is_refresh_token_payload
from app.middlewares.auth_middleware import get_current_user
from uuid import UUID
from app.config import settings
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Any

from app.models.user import User
from sqlalchemy.future import select

router = APIRouter(prefix="/auth", tags=["authentication"])

def api_response(success: bool, message: str, data: Any = None, errors: Any = None):
    return {"success": success, "message": message, "data": data, "errors": errors}

@router.post("/signup", response_model=BaseResponse[UserResponse], responses={400: {"model": ErrorResponse}})
async def signup(user: UserRegister, db: AsyncSession = Depends(get_db)):
    try:
        new_user = await UserService.register_user(db, user)
        return BaseResponse(
            success=True,
            message="User registered successfully",
            data=UserResponse(**new_user.__dict__)
        )
    except HTTPException as e:
        return BaseResponse(
            success=False,
            message=e.detail,
            errors=str(e)
        )

@router.post(
    "/login",
    response_model=BaseResponse[dict],
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
async def login(request: UserLogin, db: AsyncSession = Depends(get_db)):
    try:
        user = await UserService.authenticate_user(db, request.mobile_number, request.password)

        if getattr(user, "two_factor_enabled", False):
            result = await OTPService.send_otp(user.mobile_number, db=db, purpose="login")
            return api_response(
                True,
                "Two-factor authentication required. OTP sent.",
                OTPResponse(
                    otp=result["otp"],
                    expires_in=result["expires_in"],
                    message=result["message"]
                ),
                None
            )

        # No 2FA -> issue both access and refresh tokens
        access_token = create_access_token({"sub": str(user.id)})
        refresh_token = create_refresh_token({"sub": str(user.id)})
        return api_response(
            True,
            "Login successful",
            {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "user": UserResponse(**user.__dict__)
            },
            None
        )

    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content=api_response(False, e.detail, None, e.detail)
        )

@router.post(
    "/refresh",
    response_model=BaseResponse[TokenRefreshResponse],
    responses={401: {"model": ErrorResponse}},
)
async def refresh_token_endpoint(data: RefreshRequest):
    """Exchange a valid refresh token for a new access token."""
    try:
        refresh_token = data.refresh_token
        if not refresh_token:
            raise HTTPException(status_code=401, detail="Missing refresh token")

        payload = verify_token(refresh_token)
        if payload is None or not is_refresh_token_payload(payload):
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid refresh token payload")

        new_access = create_access_token({"sub": user_id})
        return api_response(
            True,
            "Token refreshed",
            TokenRefreshResponse(access_token=new_access).model_dump(),
            None,
        )
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content=api_response(False, e.detail, None, e.detail))

@router.post(
    "/verify-otp",
    response_model=BaseResponse[dict],
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse}
    },
)
async def verify_otp(request: OTPVerify, db: AsyncSession = Depends(get_db)):
    try:
        await OTPService.verify_otp(request.mobile_number, request.otp)


        result = await db.execute(
            select(User).where(User.mobile_number == request.mobile_number)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        access_token = create_access_token({"sub": str(user.id)})
        refresh_token = create_refresh_token({"sub": str(user.id)})

        return api_response(
            True,
            "OTP verified",
            {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "user": UserResponse(**user.__dict__)
            },
            None
        )
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content=api_response(False, e.detail, None, e.detail)
        )

@router.post(
    "/forgot-password",
    response_model=BaseResponse[OTPResponse],
    responses={429: {"model": ErrorResponse}},
)
async def forgot_password(request: OTPRequest):
    try:
        result = await OTPService.send_otp(request.mobile_number, purpose="forgot_password")
        return api_response(
            True,
            result["message"],
            OTPResponse(
                otp=result["otp"],
                expires_in=result["expires_in"]
            ),
            None
        )
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content=api_response(False, e.detail, None, e.detail)
        )

@router.post(
    "/change-password",
    response_model=BaseResponse[dict],
    responses={401: {"model": ErrorResponse}},
)
async def change_password(
    data: PasswordChange,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await UserService.change_password(db, current_user.id, data)
        return api_response(True, "Password changed successfully", {}, None)
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content=api_response(False, e.detail, None, e.detail)
        )