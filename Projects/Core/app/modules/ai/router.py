from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.core.auth.dependency import require_principal
from app.core.auth.principal import Principal
from app.core.config import settings
from app.modules.loader import get_module_instance
from app.modules.ai.providers import AIProviderUnavailable
from app.modules.ai.repository import (
    ConversationNotFound,
    SqliteAIConversationRepository,
)

router = APIRouter(prefix="/ai", tags=["AI Assistant"])


class AIResponseRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=16000)
    conversation_id: str | None = None


class AIResponse(BaseModel):
    conversation_id: str
    response: str


class AIMessage(BaseModel):
    role: str
    content: str


class AIConversation(BaseModel):
    conversation_id: str
    messages: list[AIMessage]


class AIConversationSummary(BaseModel):
    conversation_id: str
    created_at: str
    message_count: int


class AIConversationList(BaseModel):
    conversations: list[AIConversationSummary]
    limit: int
    offset: int


def get_ai_conversation_repository() -> SqliteAIConversationRepository:
    database_path = Path(__file__).resolve().parents[5] / "Databases" / "core_ai.db"
    return SqliteAIConversationRepository(database_path)


@router.get("/status")
def get_ai_status():
    assistant = get_module_instance("AI Assistant")
    return assistant.status_details()


@router.get("/conversations", response_model=AIConversationList)
def list_ai_conversations(
    limit: int = 20,
    offset: int = 0,
    principal: Principal = Depends(require_principal),
    repository: SqliteAIConversationRepository = Depends(
        get_ai_conversation_repository
    ),
):
    try:
        conversations = repository.list_conversations(
            principal.principal_id, limit=limit, offset=offset
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return AIConversationList(
        conversations=[
            AIConversationSummary(**conversation)
            for conversation in conversations
        ],
        limit=limit,
        offset=offset,
    )


@router.get(
    "/conversations/{conversation_id}",
    response_model=AIConversation,
)
def get_ai_conversation(
    conversation_id: str,
    principal: Principal = Depends(require_principal),
    repository: SqliteAIConversationRepository = Depends(
        get_ai_conversation_repository
    ),
):
    try:
        messages = repository.list_messages(
            conversation_id, principal.principal_id
        )
    except ConversationNotFound as error:
        raise HTTPException(status_code=404, detail="Conversation was not found.") from error

    return AIConversation(
        conversation_id=conversation_id,
        messages=[
            AIMessage(role=role, content=content)
            for role, content in messages
        ],
    )


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_ai_conversation(
    conversation_id: str,
    principal: Principal = Depends(require_principal),
    repository: SqliteAIConversationRepository = Depends(
        get_ai_conversation_repository
    ),
):
    try:
        repository.delete_conversation(
            conversation_id, principal.principal_id
        )
    except ConversationNotFound as error:
        raise HTTPException(status_code=404, detail="Conversation was not found.") from error

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/respond", response_model=AIResponse)
def create_ai_response(
    request: AIResponseRequest,
    principal: Principal = Depends(require_principal),
    repository: SqliteAIConversationRepository = Depends(
        get_ai_conversation_repository
    ),
):
    assistant = get_module_instance("AI Assistant")
    conversation_id = request.conversation_id

    try:
        allowed = repository.claim_request_quota(
            principal.principal_id,
            maximum=settings.ai_requests_per_minute,
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="AI request limit exceeded.",
                headers={"Retry-After": "60"},
            )
        if conversation_id is None:
            history = ()
        else:
            history = repository.list_messages(
                conversation_id,
                principal.principal_id,
                limit=settings.ai_history_message_limit,
            )
        response = assistant.respond(request.prompt, history=history)
        if conversation_id is None:
            conversation_id = repository.create_conversation(
                principal.principal_id
            )
        repository.append_exchange(
            conversation_id,
            principal.principal_id,
            request.prompt.strip(),
            response,
        )
    except ConversationNotFound as error:
        raise HTTPException(status_code=404, detail="Conversation was not found.") from error
    except AIProviderUnavailable as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI provider is unavailable.",
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI provider returned an invalid response.",
        ) from error

    return AIResponse(conversation_id=conversation_id, response=response)
