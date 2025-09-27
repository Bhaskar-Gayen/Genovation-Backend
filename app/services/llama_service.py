import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.message import Message
from app.services.message_service import MessageService
from app.utils.llm_formatter import clean_input
from app.workers.llm_tasks import process_llm_message

logger = logging.getLogger(__name__)


class LlamaService:
    @staticmethod
    async def queue_llama_processing(
            db: AsyncSession,
            message_id: UUID,
            chatroom_id: UUID,
            user_id: UUID,
            content: str
    ) -> str:
        """Queue Llama processing task and return task ID"""
        try:
            # Clean and format input
            cleaned_content = clean_input(content)

            # Get conversation context (last 10 messages)
            context = await LlamaService.get_conversation_context(db, chatroom_id)
            logger.info(f"Get context of the conversation: {context}", )

            # Queue Celery task for  API
            task=process_llm_message.apply_async(
                args=[str(message_id), str(chatroom_id), str(user_id), cleaned_content, context],
                queue="llm"
            )

            logger.info(f"Queued Llama task {task.id} for message {message_id}")
            return task.id

        except Exception as e:
            logger.error(f"Failed to queue Llama processing: {e}")
            raise

    @staticmethod
    async def get_conversation_context(db: AsyncSession, chatroom_id: UUID, limit: int = 10) -> list:
        """Get conversation context for Llama API"""
        try:
            result = await db.execute(
                select(Message)
                .where(Message.chatroom_id == chatroom_id)
                .order_by(Message.created_at.desc())
                .limit(limit)
            )
            messages = result.scalars().all()

            # Convert to list of dictionaries for JSON serialization in Chronological order
            context = []
            for msg in reversed(messages):  
                context.append({
                    "role": "user" if msg.is_from_user else "assistant",
                    "content": msg.content,
                    "timestamp": msg.created_at.isoformat()
                })

            return context

        except Exception as e:
            logger.error(f"Failed to get conversation context: {e}")
            return []

    @staticmethod
    async def update_message_status(
            db: AsyncSession,
            message_id: UUID,
            status: str,
            content: str = None,
            error_message: str = None
    ):
        """Update message status and content"""
        try:
            msg = await db.get(Message, message_id)
            if not msg:
                logger.error(f"Message {message_id} not found for status update")
                return False

            msg.status = status
            if content:
                msg.content = content
            if error_message:
                msg.error_message = error_message

            await db.commit()
            logger.info(f"Updated message {message_id} status to {status}")
            return True

        except Exception as e:
            logger.error(f"Failed to update message status: {e}")
            await db.rollback()
            return False

    @staticmethod
    async def create_ai_response(
            db: AsyncSession,
            chatroom_id: UUID,
            user_id: UUID,
            ai_content: str,
            original_message_id: UUID
    ) -> Message:
        """Create AI response message"""
        try:
            ai_message = await MessageService.create_ai_message(
                db=db,
                chatroom_id=chatroom_id,
                user_id=user_id,
                content=ai_content,
                original_message_id=original_message_id
            )

            logger.info(f"Created AI response message {ai_message.id}")
            return ai_message

        except Exception as e:
            logger.error(f"Failed to create AI response: {e}")
            raise

    @staticmethod
    def handle_llama_error(error: Exception) -> str:
        """Handle different types of Llama API errors"""
        error_str = str(error).lower()

        if "quota" in error_str or "rate limit" in error_str:
            return "API quota exceeded. Please try again later."
        elif "invalid api key" in error_str or "unauthorized" in error_str:
            return "Invalid Llama API key. Contact support."
        elif "content policy" in error_str or "safety" in error_str:
            return "Message violates content policy. Please rephrase your message."
        elif "timeout" in error_str:
            return "Request timeout. Please try again."
        elif "network" in error_str or "connection" in error_str:
            return "Network error. Please check your connection and try again."
        else:
            return "AI service temporarily unavailable. Please try again later."