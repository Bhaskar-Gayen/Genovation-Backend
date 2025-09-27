
from __future__ import annotations

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.sqltypes import NULLTYPE

from app.models.message import Message, EnumMessageStatus
from app.schemas.chatroom_schemas import MessageCreate
from uuid import UUID
from datetime import datetime

logger = logging.getLogger(__name__)


class MessageService:
    @staticmethod
    async def create_user_message(
            db: AsyncSession,
            chatroom_id: UUID,
            user_id: UUID,
            data: MessageCreate
    ) -> Message:
        """Create a user message"""
        try:
            message = Message(
                chatroom_id=chatroom_id,
                user_id=user_id,
                parent_message_id=None,
                content=data.content,
                is_from_user=True,
                status=EnumMessageStatus.PENDING
            )

            db.add(message)
            await db.commit()
            await db.refresh(message)

            logger.info(f"Created user message {message.id}")
            return message

        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to create user message: {e}")
            raise

    @staticmethod
    async def create_ai_message(
            db: AsyncSession,
            chatroom_id: UUID,
            user_id: UUID,
            content: str,
            original_message_id: UUID = None
    ) -> Message:
        """Create an AI response message"""
        try:
            message = Message(
                chatroom_id=chatroom_id,
                user_id=user_id,
                content=content,
                parent_message_id=original_message_id,
                is_from_user=False,
                status=EnumMessageStatus.COMPLETED
            )

            db.add(message)
            await db.commit()
            await db.refresh(message)

            logger.info(f"Created AI message {message.id}")
            return message

        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to create AI message: {e}")
            raise

    @staticmethod
    async def update_message_task_id(
            db: AsyncSession,
            message_id: UUID,
            task_id: str
    ) -> bool:
        """Update message with Celery task ID"""
        try:
            message = await db.get(Message, message_id)
            if not message:
                logger.error(f"Message {message_id} not found")
                return False

            message.task_id = task_id
            message.status = EnumMessageStatus.PROCESSING

            await db.commit()
            logger.info(f"Updated message {message_id} with task ID {task_id}")
            return True

        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to update message task ID: {e}")
            return False

    @staticmethod
    async def get_conversation_context(
            db: AsyncSession,
            chatroom_id: UUID,
            limit: int = 10
    ) -> list:
        """Get recent messages for conversation context"""
        try:
            result = await db.execute(
                select(Message)
                .where(Message.chatroom_id == chatroom_id)
                .order_by(Message.created_at.desc())
                .limit(limit)
            )
            messages = result.scalars().all()

            # Return in chronological order
            return list(reversed(messages))

        except Exception as e:
            logger.error(f"Failed to get conversation context: {e}")
            return []

    @staticmethod
    async def get_messages_by_chatroom(
            db: AsyncSession,
            chatroom_id: UUID,
            user_id: UUID,
            skip: int = 0,
            limit: int = 50
    ) -> list[Message]:
        """Get paginated messages for a chatroom"""
        try:
            result = await db.execute(
                select(Message)
                .where(Message.chatroom_id == chatroom_id)
                .order_by(Message.created_at.asc())
                .offset(skip)
                .limit(limit)
            )
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Failed to get messages: {e}")
            return []

    @staticmethod
    async def update_message_status(
            db: AsyncSession,
            message_id: UUID,
            status: EnumMessageStatus,
            error_message: str = None
    ) -> bool:
        """Update message status"""
        try:
            message = await db.get(Message, message_id)
            if not message:
                return False

            message.status = status
            if error_message:
                message.error_message = error_message
            message.updated_at = datetime.utcnow()

            await db.commit()
            return True

        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to update message status: {e}")
            return False

    @staticmethod
    async def get_conversation_pairs(
            db: AsyncSession,
            chatroom_id: UUID,
            user_id: UUID
    ) -> list[Message]:
        """Get all user messages with their AI responses for conversation pairs"""
        try:
            result = await db.execute(
                select(Message)
                .options(selectinload(Message.children))
                .where(
                    Message.chatroom_id == chatroom_id,
                    Message.is_from_user == True,
                    Message.parent_message_id.is_(None)  # Only root messages (user messages)
                )
                .order_by(Message.created_at.asc())
            )

            user_messages = result.scalars().all()
            logger.info(f"Retrieved {len(user_messages)} conversation pairs for chatroom {chatroom_id}")
            return user_messages

        except Exception as e:
            logger.error(f"Failed to get conversation pairs: {e}")
            return []

    @staticmethod
    async def get_message_with_children(
            db: AsyncSession,
            message_id: UUID,
            chatroom_id: UUID,
            user_id: UUID
    ) -> Message | None:
        """Get a specific message with its children (AI responses)"""
        try:
            result = await db.execute(
                select(Message)
                .options(selectinload(Message.children))
                .where(
                    Message.id == message_id,
                    Message.chatroom_id == chatroom_id
                )
            )

            message = result.scalar_one_or_none()
            if message:
                logger.info(f"Retrieved message {message_id} with {len(message.children)} children")
            else:
                logger.warning(f"Message {message_id} not found in chatroom {chatroom_id}")

            return message

        except Exception as e:
            logger.error(f"Failed to get message with children: {e}")
            return None

    @staticmethod
    async def get_messages_with_relationships(
            db: AsyncSession,
            chatroom_id: UUID,
            user_id: UUID,
            skip: int = 0,
            limit: int = 50,
            include_parent: bool = False,
            include_children: bool = False
    ) -> list[Message]:
        """Get messages with optional parent-child relationships"""
        try:
            query = select(Message).where(Message.chatroom_id == chatroom_id)

            # Add relationship loading based on parameters
            if include_parent and include_children:
                query = query.options(
                    selectinload(Message.parent),
                    selectinload(Message.children)
                )
            elif include_parent:
                query = query.options(selectinload(Message.parent))
            elif include_children:
                query = query.options(selectinload(Message.children))

            query = query.order_by(Message.created_at.asc()).offset(skip).limit(limit)

            result = await db.execute(query)
            messages = result.scalars().all()

            logger.info(f"Retrieved {len(messages)} messages with relationships for chatroom {chatroom_id}")
            return messages

        except Exception as e:
            logger.error(f"Failed to get messages with relationships: {e}")
            return []

    @staticmethod
    async def get_message_with_response(
            db: AsyncSession,
            message_id: UUID,
            chatroom_id: UUID,
            user_id: UUID
    ) -> tuple[Message | None, Message | None]:
        """Get a user message and its AI response (if exists)"""
        try:
            message = await MessageService.get_message_with_children(
                db, message_id, chatroom_id, user_id
            )

            if not message:
                return None, None

            ai_response = message.children[0] if message.children else None
            return message, ai_response

        except Exception as e:
            logger.error(f"Failed to get message with response: {e}")
            return None, None

    @staticmethod
    async def check_message_status_with_response(
            db: AsyncSession,
            message_id: UUID,
            chatroom_id: UUID,
            user_id: UUID
    ) -> dict:
        """Check message status and AI response availability"""
        try:
            message, ai_response = await MessageService.get_message_with_response(
                db, message_id, chatroom_id, user_id
            )

            if not message:
                return {
                    "found": False,
                    "error": "Message not found"
                }

            status_info = {
                "found": True,
                "message_id": str(message.id),
                "status": message.status.value,
                "has_ai_response": ai_response is not None,
                "ai_response_id": str(ai_response.id) if ai_response else None,
                "is_processing": message.status == EnumMessageStatus.PROCESSING,
                "is_completed": message.status == EnumMessageStatus.COMPLETED,
                "is_failed": message.status == EnumMessageStatus.FAILED,
                "created_at": message.created_at.isoformat()
            }

            if ai_response:
                status_info["ai_response_created_at"] = ai_response.created_at.isoformat()

            return status_info

        except Exception as e:
            logger.error(f"Failed to check message status: {e}")
            return {
                "found": False,
                "error": str(e)
            }