from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db

from app.models.user import User
from app.schemas.chatroom_schemas import (
    ChatroomCreate, ChatroomUpdate, ChatroomResponse, MessageCreate, MessageResponse,
    PaginatedChatrooms
)
from app.schemas.pagination import Pagination, PaginatedResponse 
from app.schemas.response import BaseResponse 

from app.services.chatroom_service import ChatroomService
from app.services.llama_service import LlamaService
from app.services.message_service import MessageService

from app.middlewares.auth_middleware import get_current_user
from uuid import UUID
from fastapi.responses import JSONResponse
from typing import Any, List, Dict

from app.services.usage_service import UsageService
import logging

from app.utils.queue_utils import get_task_status, get_task_result, get_queue_health

logger=logging.getLogger(__name__)

router = APIRouter(prefix="/chatroom", tags=["chatrooms"])


@router.post(
    "/",
    response_model=BaseResponse[ChatroomResponse],
    status_code=201
)
async def create_chatroom(
    data: ChatroomCreate,
    current_user: Any = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        chatroom_orm = await ChatroomService.create_chatroom(db, current_user.id, data)
        return BaseResponse(
            success=True,
            message="Chatroom created",
            data=ChatroomResponse.model_validate(chatroom_orm)
        )
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content=BaseResponse(success=False, message=e.detail, errors=e.detail).model_dump()
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=BaseResponse(success=False, message="Internal server error", errors=str(e)).model_dump()
        )


# --- List Chatrooms ---
@router.get(
    "/",
    response_model=BaseResponse[PaginatedChatrooms]
)
async def list_chatroom(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: Any = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        pagination_params = Pagination(page=page, size=size)
        paginated_data = await ChatroomService.list_user_chatrooms(db, current_user.id, pagination_params)

        paginated_data["items"] = [ChatroomResponse.model_validate(c) for c in paginated_data["items"]]

        return BaseResponse(
            success=True,
            message="Chatrooms fetched",
            data=PaginatedChatrooms(**paginated_data)
        )
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content=BaseResponse(success=False, message=e.detail, errors=e.detail).model_dump()
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=BaseResponse(success=False, message="Internal server error", errors=str(e)).model_dump()
        )

@router.post(
    "/{chatroom_id}/message",
    response_model=BaseResponse[MessageResponse],
    status_code=201
)
async def send_message(
        chatroom_id: UUID,
        data: MessageCreate,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    try:
        logger.info("Message API Call")
        # 1. Verify chatroom ownership
        chatroom = await ChatroomService.get_chatroom(db, current_user.id, chatroom_id)
        if not chatroom:
            raise HTTPException(
                status_code=404,
                detail="Chatroom not found or access denied"
            )
        logger.info(f"chatroom found {chatroom}")



        # 5. Create user message with chatroom_id
        user_message = await MessageService.create_user_message(
            db=db,
            chatroom_id=chatroom_id,
            user_id=current_user.id,
            data=data
        )

        # 6. Increment usage counter for Basic users
        await UsageService.increment_daily_usage(current_user.id)

        # 7. Queue LLM API call asynchronously
        task_id = await LlamaService.queue_llama_processing(
            db=db,
            message_id=user_message.id,
            chatroom_id=chatroom_id,
            user_id=current_user.id,
            content=data.content
        )

        logger.info(f"Task created with id {task_id}")

        # 8. Update message with task ID
        await MessageService.update_message_task_id(db, user_message.id, task_id)

        return BaseResponse(
            success=True,
            message="Message sent successfully",
            data=MessageResponse.model_validate(user_message)
        )

    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content=BaseResponse(
                success=False,
                message=e.detail,
                errors=[e.detail] 
            ).model_dump()
        )
    except ValidationError as e:
        logger.error(f"Pydantic Validation Error: {e.errors()}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=BaseResponse(
                success=False,
                message="Data validation failed",
                errors=[str(error) for error in e.errors()] 
            ).model_dump()
        )
    except Exception as e:
        logger.error(f"Unexpected error in send_message: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=BaseResponse(
                success=False,
                message="Failed to send message",
                errors=["Internal server error"]
            ).model_dump()
        )


class ChatroomDetailsResponse(BaseModel):
    chatroom: ChatroomResponse
    messages: PaginatedResponse[MessageResponse] 

@router.get(
    "/{chatroom_id}",
    response_model=BaseResponse[ChatroomDetailsResponse] 
)
async def get_chatroom(
    chatroom_id: UUID,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: Any = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        pagination_params = Pagination(page=page, size=size)
        result = await ChatroomService.get_chatroom_with_messages(db, current_user.id, chatroom_id, pagination_params)

        # Convert ORM objects to Pydantic
        chatroom_pydantic = ChatroomResponse.model_validate(result["chatroom"])
        messages_items_pydantic = [MessageResponse.model_validate(m) for m in result["messages"]["items"]]

        # Create PaginatedResponse[MessageResponse] instance for messages
        paginated_messages = PaginatedResponse[MessageResponse](
            total=result["messages"]["total"],
            page=result["messages"]["page"],
            size=result["messages"]["size"],
            items=messages_items_pydantic
        )

        # Create ChatroomDetailsResponse instance
        details_data = ChatroomDetailsResponse(
            chatroom=chatroom_pydantic,
            messages=paginated_messages
        )

        return BaseResponse(
            success=True,
            message="Chatroom details fetched",
            data=details_data
        )
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content=BaseResponse(success=False, message=e.detail, errors=e.detail).model_dump()
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=BaseResponse(success=False, message="Internal server error", errors=str(e)).model_dump()
        )



@router.put(
    "/{chatroom_id}",
    response_model=BaseResponse[ChatroomResponse] 
)
async def update_chatroom(
    chatroom_id: UUID,
    data: ChatroomUpdate,
    current_user: Any = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        chatroom_orm = await ChatroomService.update_chatroom(db, current_user.id, chatroom_id, data)
        return BaseResponse(
            success=True,
            message="Chatroom updated",
            data=ChatroomResponse.model_validate(chatroom_orm)
        )
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content=BaseResponse(success=False, message=e.detail, errors=e.detail).model_dump()
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=BaseResponse(success=False, message="Internal server error", errors=str(e)).model_dump()
        )


@router.delete("/{chatroom_id}", status_code=204)
async def delete_chatroom(
    chatroom_id: UUID,
    current_user: Any = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        await ChatroomService.delete_chatroom(db, current_user.id, chatroom_id)
        return JSONResponse(status_code=204, content=None)
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content=BaseResponse(success=False, message=e.detail, errors=e.detail).model_dump()
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=BaseResponse(success=False, message="Internal server error", errors=str(e)).model_dump()
        )



@router.get(
    "/{chatroom_id}/conversation",
    response_model=BaseResponse[List[dict]]
)
async def get_conversation_pairs(
        chatroom_id: UUID,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """Get conversation as user-AI message pairs"""
    try:
        chatroom = await ChatroomService.get_chatroom(db, current_user.id, chatroom_id)
        if not chatroom:
            raise HTTPException(status_code=404, detail="Chatroom not found")
        user_messages = await MessageService.get_conversation_pairs(
            db=db,
            chatroom_id=chatroom_id,
            user_id=current_user.id
        )

        conversation_pairs = []
        for user_msg in user_messages:
            ai_response = user_msg.children[0] if user_msg.children else None

            pair = {
                "user_message": {
                    "id": str(user_msg.id),
                    "content": user_msg.content,
                    "is_from_user": True,
                    "status": user_msg.status.value,
                    "created_at": user_msg.created_at.isoformat(),
                },
                "ai_response": None
            }

            if ai_response:
                pair["ai_response"] = {
                    "id": str(ai_response.id),
                    "content": ai_response.content,
                    "is_from_user": False,
                    "status": ai_response.status.value,
                    "created_at": ai_response.created_at.isoformat(),
                    "parent_message_id": str(ai_response.parent_message_id)
                }

            conversation_pairs.append(pair)

        return BaseResponse(
            success=True,
            message=f"Retrieved {len(conversation_pairs)} conversation pairs",
            data=conversation_pairs
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation pairs: {e}")
        raise HTTPException(status_code=500, detail="Failed to get conversation pairs")



@router.get(
    "/{chatroom_id}/messages",
    response_model=BaseResponse[List[dict]]
)
async def get_chatroom_messages(
        chatroom_id: UUID,
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        include_parent: bool = Query(False, description="Include parent message info"),
        include_children: bool = Query(False, description="Include children messages info"),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """Get all messages in a chatroom with optional parent-child context"""
    try:
        chatroom = await ChatroomService.get_chatroom(db, current_user.id, chatroom_id)
        if not chatroom:
            raise HTTPException(status_code=404, detail="Chatroom not found")
        messages = await MessageService.get_messages_with_relationships(
            db=db,
            chatroom_id=chatroom_id,
            user_id=current_user.id,
            skip=skip,
            limit=limit,
            include_parent=include_parent,
            include_children=include_children
        )

        message_responses = []
        for msg in messages:
            response_data = {
                "id": str(msg.id),
                "content": msg.content,
                "is_from_user": msg.is_from_user,
                "status": msg.status.value,
                "created_at": msg.created_at.isoformat(),
                "chatroom_id": str(msg.chatroom_id),
                "user_id": str(msg.user_id)
            }

            if include_parent:
                response_data["parent_message_id"] = str(msg.parent_message_id) if msg.parent_message_id else None
                if hasattr(msg, 'parent') and msg.parent:
                    response_data["parent_content"] = msg.parent.content
            if include_children:
                response_data["has_children"] = len(msg.children) > 0 if hasattr(msg, 'children') else False
                response_data["children_count"] = len(msg.children) if hasattr(msg, 'children') else 0

            message_responses.append(response_data)

        return BaseResponse(
            success=True,
            message=f"Retrieved {len(message_responses)} messages",
            data=message_responses
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting messages: {e}")
        raise HTTPException(status_code=500, detail="Failed to get messages")



@router.get(
    "/{chatroom_id}/messages/{message_id}",
    response_model=BaseResponse[dict]
)
async def get_message_with_response(
        chatroom_id: UUID,
        message_id: UUID,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """Get a specific message with its AI response (if exists)"""
    try:
        # Verify chatroom ownership
        chatroom = await ChatroomService.get_chatroom(db, current_user.id, chatroom_id)
        if not chatroom:
            raise HTTPException(status_code=404, detail="Chatroom not found")

        # Use MessageService method
        message, ai_response = await MessageService.get_message_with_response(
            db=db,
            message_id=message_id,
            chatroom_id=chatroom_id,
            user_id=current_user.id
        )

        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        # Build response
        response_data = {
            "message": {
                "id": str(message.id),
                "content": message.content,
                "is_from_user": message.is_from_user,
                "status": message.status.value,
                "created_at": message.created_at.isoformat(),
                "parent_message_id": str(message.parent_message_id) if message.parent_message_id else None
            },
            "ai_response": None,
            "has_response": False
        }

        # Add AI response if exists
        if ai_response:
            response_data["ai_response"] = {
                "id": str(ai_response.id),
                "content": ai_response.content,
                "is_from_user": False,
                "status": ai_response.status.value,
                "created_at": ai_response.created_at.isoformat(),
                "parent_message_id": str(ai_response.parent_message_id)
            }
            response_data["has_response"] = True

        return BaseResponse(
            success=True,
            message="Message retrieved successfully",
            data=response_data
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting message: {e}")
        raise HTTPException(status_code=500, detail="Failed to get message")



@router.get(
    "/{chatroom_id}/messages/{message_id}/status",
    response_model=BaseResponse[dict]
)
async def check_message_status(
        chatroom_id: UUID,
        message_id: UUID,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """Check if a user message has received an AI response (for polling)"""
    try:
        # Verify chatroom ownership
        chatroom = await ChatroomService.get_chatroom(db, current_user.id, chatroom_id)
        if not chatroom:
            raise HTTPException(status_code=404, detail="Chatroom not found")

        # Use MessageService method
        status_info = await MessageService.check_message_status_with_response(
            db=db,
            message_id=message_id,
            chatroom_id=chatroom_id,
            user_id=current_user.id
        )

        if not status_info["found"]:
            raise HTTPException(status_code=404, detail=status_info.get("error", "Message not found"))

        return BaseResponse(
            success=True,
            message="Message status retrieved successfully",
            data=status_info
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking message status: {e}")
        raise HTTPException(status_code=500, detail="Failed to check message status")



@router.get(
    "/{chatroom_id}/conversation-tree",
    response_model=BaseResponse[List[dict]]
)
async def get_conversation_tree(
        chatroom_id: UUID,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """Get conversation as a hierarchical tree structure"""
    try:
        # Verify chatroom ownership
        chatroom = await ChatroomService.get_chatroom(db, current_user.id, chatroom_id)
        if not chatroom:
            raise HTTPException(status_code=404, detail="Chatroom not found")

        # Get conversation pairs
        user_messages = await MessageService.get_conversation_pairs(
            db=db,
            chatroom_id=chatroom_id,
            user_id=current_user.id
        )

        conversation_tree = []
        for user_msg in user_messages:
            tree_node = {
                "id": str(user_msg.id),
                "content": user_msg.content,
                "is_from_user": True,
                "status": user_msg.status.value,
                "created_at": user_msg.created_at.isoformat(),
                "children": []
            }

            # Add AI responses as children
            for child in user_msg.children:
                tree_node["children"].append({
                    "id": str(child.id),
                    "content": child.content,
                    "is_from_user": False,
                    "status": child.status.value,
                    "created_at": child.created_at.isoformat(),
                    "parent_id": str(child.parent_message_id)
                })

            conversation_tree.append(tree_node)

        return BaseResponse(
            success=True,
            message=f"Retrieved conversation tree with {len(conversation_tree)} nodes",
            data=conversation_tree
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation tree: {e}")
        raise HTTPException(status_code=500, detail="Failed to get conversation tree")


@router.get("/task-status/{task_id}")
def check_task_status(task_id: str):
    status = get_task_status(task_id)
    result = get_task_result(task_id)
    queue_health_data=get_queue_health()
    return {"task_id": task_id, "status": status, "result": result, "queue_health":queue_health_data}

