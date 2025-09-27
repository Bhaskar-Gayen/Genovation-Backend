from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime

class MessageBase(BaseModel):
    content: str
    is_from_user: Optional[bool] = True

class MessageCreate(MessageBase):
    chatroom_id: UUID
    user_id: UUID

class Message(MessageBase):
    id: UUID
    chatroom_id: UUID
    user_id: UUID
    created_at: datetime
    class Config:
        from_attributes = True 