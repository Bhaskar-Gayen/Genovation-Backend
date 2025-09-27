from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.database import Base
from datetime import datetime
import enum

class EnumMessageStatus(enum.Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    PROCESSING="PROCESSING"
    FAILED = "FAILED"

class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, index=True)
    content = Column(String, nullable=False)
    is_from_user = Column(Boolean, default=True)
    parent_message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id"), nullable=True)
    chatroom_id = Column(UUID(as_uuid=True), ForeignKey("chatrooms.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.now)
    status = Column(Enum(EnumMessageStatus), nullable=False, default=EnumMessageStatus.PENDING)

    chatroom = relationship("Chatroom", back_populates="messages")
    parent = relationship("Message", remote_side=[id], back_populates="children")
    children = relationship("Message", back_populates="parent")
    user = relationship("User") 