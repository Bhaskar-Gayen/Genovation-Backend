from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from uuid import UUID
from datetime import datetime

class ChatroomCreate(BaseModel):
    title: str
    description: Optional[str] = None

class ChatroomUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None

class ChatroomResponse(BaseModel):
    id: UUID
    title: str
    description: Optional[str]
    user_id: UUID
    created_at: datetime
    updated_at: Optional[datetime]
    is_deleted: Optional[bool] = False

    model_config = ConfigDict(from_attributes=True)

class MessageCreate(BaseModel):
    chatroom_id: UUID
    content: str
    is_from_user: bool = True

class MessageResponse(BaseModel):
    id: UUID
    chatroom_id: UUID
    user_id: UUID
    content: str
    is_from_user: bool
    created_at: datetime
    status: Optional[str] = "completed"
    
    class Config:
        from_attributes = True 

class Pagination(BaseModel):
    page: int = Field(1, ge=1)
    size: int = Field(20, ge=1, le=100)

class PaginatedChatrooms(BaseModel):
    total: int
    page: int
    size: int
    items: List[ChatroomResponse]

class PaginatedMessages(BaseModel):
    total: int
    page: int
    size: int
    items: List[MessageResponse] 