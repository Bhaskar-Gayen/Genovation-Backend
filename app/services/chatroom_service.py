from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.chatroom import Chatroom
from app.models.message import Message
from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException, status
from app.schemas.chatroom_schemas import ChatroomCreate, ChatroomUpdate, Pagination
from app.services.cache_service import CacheService
from sqlalchemy import func

class ChatroomService:
    @staticmethod
    async def create_chatroom(db: AsyncSession, user_id: UUID, data: ChatroomCreate) -> Chatroom:
        try:
            chatroom = Chatroom(title=data.title, description=data.description, user_id=user_id)
            db.add(chatroom)
            await db.flush() 
            await db.refresh(chatroom) 
            await db.commit()
            await CacheService.invalidate_user_chatrooms_cache(user_id)
            return chatroom
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to create chatroom: {e}")

    @staticmethod
    async def list_user_chatrooms(db: AsyncSession, user_id: UUID, pagination: Pagination):
        cached = await CacheService.get_user_chatrooms_cache(user_id)
        if cached:
            return cached
        query = select(Chatroom).where(Chatroom.user_id == user_id, Chatroom.is_deleted == False)
        total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
        result = await db.execute(query.offset((pagination.page-1)*pagination.size).limit(pagination.size))
        items = result.scalars().all()
        resp = {"total": total, "page": pagination.page, "size": pagination.size, "items": items}
        await CacheService.set_user_chatrooms_cache(user_id, resp)
        return resp

    @staticmethod
    async def get_chatroom(db: AsyncSession, user_id: UUID, chatroom_id: UUID) -> Chatroom:
        chatroom = await db.get(Chatroom, chatroom_id)
        if not chatroom or chatroom.is_deleted or chatroom.user_id != user_id:
            raise HTTPException(status_code=404, detail="Chatroom not found or access denied")
        return chatroom

    @staticmethod
    async def update_chatroom(db: AsyncSession, user_id: UUID, chatroom_id: UUID, data: ChatroomUpdate) -> Chatroom:
        try:
            chatroom = await ChatroomService.get_chatroom(db, user_id, chatroom_id)
            for field, value in data.model_dump(exclude_unset=True).items():
                setattr(chatroom, field, value)
            await db.commit()
            await db.refresh(chatroom)
            await CacheService.invalidate_user_chatrooms_cache(user_id)
            return chatroom
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to update chatroom: {e}")

    @staticmethod
    async def delete_chatroom(db: AsyncSession, user_id: UUID, chatroom_id: UUID) -> None:
        try:
            chatroom = await ChatroomService.get_chatroom(db, user_id, chatroom_id)
            chatroom.is_deleted = True
            await db.commit()
            await CacheService.invalidate_user_chatrooms_cache(user_id)
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to delete chatroom: {e}")

    @staticmethod
    async def validate_ownership(db: AsyncSession, user_id: UUID, chatroom_id: UUID) -> bool:
        chatroom = await db.get(Chatroom, chatroom_id)
        return chatroom and chatroom.user_id == user_id and not chatroom.is_deleted

    @staticmethod
    async def get_chatroom_with_messages(db: AsyncSession, user_id: UUID, chatroom_id: UUID, pagination: Pagination):
        chatroom = await ChatroomService.get_chatroom(db, user_id, chatroom_id)
        query = select(Message).where(Message.chatroom_id == chatroom_id).order_by(Message.created_at.desc())
        total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
        result = await db.execute(query.offset((pagination.page-1)*pagination.size).limit(pagination.size))
        items = result.scalars().all()
        return {"chatroom": chatroom, "messages": {"total": total, "page": pagination.page, "size": pagination.size, "items": items}} 