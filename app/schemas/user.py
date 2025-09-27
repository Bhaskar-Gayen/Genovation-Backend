from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime
import re


class MobileNumber(BaseModel):
    mobile_number: str = Field(..., description="Mobile number with country code")
    
    @classmethod
    def validate_mobile_number(cls, v):
        if not re.match(r'^\+?[1-9]\d{1,14}$', v):
            raise ValueError('Invalid mobile number format')
        return v


class UserBase(BaseModel):
    mobile_number: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    is_active: Optional[bool] = True


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    mobile_number: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class UserInDB(UserBase):
    id: UUID
    password_hash: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class User(UserBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True



class SendOTPRequest(MobileNumber):
    pass


class SendOTPResponse(BaseModel):
    message: str
    otp: str
    expires_in: int


class VerifyOTPRequest(BaseModel):
    mobile_number: str
    otp: str


class VerifyOTPResponse(BaseModel):
    message: str
    access_token: str
    token_type: str
    user: User


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    mobile_number: Optional[str] = None
