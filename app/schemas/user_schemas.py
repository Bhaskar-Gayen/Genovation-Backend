from datetime import datetime
from pydantic import BaseModel, Field, EmailStr, constr
from typing import Optional
from uuid import UUID

class UserRegister(BaseModel):
    mobile_number: constr(pattern=r'^\+?[1-9]\d{1,14}$')
    password: constr(min_length=8)
    full_name: Optional[str]
    email: Optional[EmailStr]

class UserLogin(BaseModel):
    mobile_number: constr(pattern=r'^\+?[1-9]\d{1,14}$')
    password: str

class UserProfile(BaseModel):
    id: UUID
    mobile_number: str
    full_name: Optional[str]
    email: Optional[EmailStr]
    is_active: bool
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    model_config = {
        "from_attributes": True,  
        "json_encoders": {
            datetime: lambda v: v.isoformat()
        }
    }

class UserUpdate(BaseModel):
    full_name: Optional[str]
    email: Optional[EmailStr]
    two_factor_enabled: Optional[bool]

class OTPRequest(BaseModel):
    mobile_number: constr(pattern=r'^\+?[1-9]\d{1,14}$')

class OTPVerify(BaseModel):
    mobile_number: constr(pattern=r'^\+?[1-9]\d{1,14}$')
    otp: constr(min_length=6, max_length=6)

class PasswordChange(BaseModel):
    old_password: str
    new_password: constr(min_length=8)

class UserResponse(BaseModel):
    id: UUID
    mobile_number: str
    full_name: Optional[str]
    email: Optional[EmailStr]
    is_active: bool
    two_factor_enabled: bool | None = None
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat()  
        }
    }

class OTPResponse(BaseModel):
    message: str
    otp: Optional[str] = None 
    expires_in: int
class ErrorResponse(BaseModel):
    detail: str 

# Token refresh schemas
class RefreshRequest(BaseModel):
    refresh_token: str

class TokenRefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"