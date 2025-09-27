from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime

class ChatroomBase(BaseModel):
    title: str
    description: Optional[str] = None

class ChatroomCreate(ChatroomBase):
    pass

class ChatroomUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None

class Chatroom(ChatroomBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    class Config:
        from_attributes = True 