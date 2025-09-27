import asyncio
from uuid import UUID

from app.celery_app import celery_app
from app.config import settings
from app.database import SessionLocal
from app.integrations.llama_client import LlamaClient
from app.models.message import Message, EnumMessageStatus
from app.services.message_service import MessageService
import logging

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def process_llm_message(self, message_id: str, chatroom_id: str, user_id: str, prompt: str, context: list):
    logger.info(f"Processing LLM message: {message_id}")
    try:
        result = asyncio.run(_process_llm(message_id, chatroom_id, user_id, prompt, context))
        return result
    except Exception as exc:
        logger.error(f"LLM task failed: {exc}")
        asyncio.run(_mark_message_failed(message_id, str(exc)))
        raise self.retry(exc=exc, countdown=180)



async def _process_llm(message_id: str, chatroom_id: str, user_id: str, prompt: str, context: list):
    async with SessionLocal() as db:
        try:
            # 1. Update original user message status to PROCESSING
            user_msg = await db.get(Message, UUID(message_id))
            if not user_msg:
                logger.error(f"Message {message_id} not found")
                return {"status": "error", "message": "Original message not found"}

            user_msg.status = EnumMessageStatus.PROCESSING
            await db.commit()

            # 2. Format context for LLM
            formatted_context = _format_context_for_llama(context)

            # 3. Call Llama API
            llama = LlamaClient(api_key=settings.replicate_api_token)
            response = await llama.send_prompt(prompt, formatted_context)
            logger.info(f"Llama give back the response:{response}")

            # 4. Create NEW AI response message
            ai_message = await MessageService.create_ai_message(
                db=db,
                chatroom_id=UUID(chatroom_id),
                user_id=UUID(user_id),
                content=response,
                original_message_id=user_msg.id
            )

            # 5. Update original user message status to COMPLETED
            user_msg.status = EnumMessageStatus.COMPLETED

            # 6. Commit both updates
            await db.commit()

            logger.info(f"Created AI response {ai_message.id} for user message {message_id}")
            return {
                "status": "success",
                "user_message_id": message_id,
                "ai_message_id": str(ai_message.id)
            }

        except Exception as e:
            await db.rollback()
            logger.error(f"LLM processing failed for message {message_id}: {e}")
            raise


async def _mark_message_failed(message_id: str, error_message: str):
    """Mark user message as failed"""
    async with SessionLocal() as db:
        try:
            msg = await db.get(Message, UUID(message_id))
            if msg:
                msg.status = EnumMessageStatus.FAILED
                await db.commit()
                logger.info(f"Marked message {message_id} as failed")
        except Exception as e:
            logger.error(f"Failed to mark message as failed: {e}")


def _format_context_for_llama(context: list) -> str:
    """Format conversation context for Llama API"""
    if not context:
        return ""

    formatted = "Previous conversation:\n"
    for msg in context[-5:]:  
        role = "User" if msg.get("role") == "user" else "Assistant"
        content = msg.get("content", "")
        formatted += f"{role}: {content}\n"

    formatted += "\nCurrent message:\n"
    return formatted

@celery_app.task
def hello(test: str):
    print("Hello from Celery!")
    return {"message": "Hello, world!", "test": test}