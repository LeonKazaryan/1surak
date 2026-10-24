from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, StringConstraints

MAX_QUERY_CHARS = 12_000

Query = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_QUERY_CHARS)]


class ChatRequest(BaseModel):
    query: Query
    chat_id: UUID | None = None


class ChatMeta(BaseModel):
    id: str
    title: str | None
    created_at: str
    updated_at: str


class ChatMessageOut(BaseModel):
    id: str
    chat_id: str
    role: str
    content: str
    trace: list[dict]
    created_at: str


class ChatListResponse(BaseModel):
    items: list[ChatMeta]


class ChatMessagesResponse(BaseModel):
    messages: list[ChatMessageOut]
