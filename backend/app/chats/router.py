import json
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse

from app.chats import repository, service
from app.chats.schemas import ChatListResponse, ChatMessagesResponse, ChatMeta, ChatRequest
from app.deps import Db, FlightPrices, Llm, SessionFactory, Tools

router = APIRouter(prefix="/api", tags=["Chats"])

MAX_LISTED_CHATS = 50


def _parse_uuid(value: str) -> str | None:
    try:
        return str(UUID(value))
    except ValueError:
        return None


def _require_uuid(value: str) -> str:
    parsed = _parse_uuid(value)
    if parsed is None:
        raise HTTPException(status_code=400, detail="Invalid chat ID")
    return parsed


async def _ndjson(events: AsyncIterator[dict]) -> AsyncIterator[bytes]:
    async for event in events:
        yield (json.dumps(event, ensure_ascii=False) + "\n").encode()


@router.post("/chat/stream")
async def chat_stream(
    body: ChatRequest, sessionmaker: SessionFactory, llm: Llm, tools: Tools, flights: FlightPrices
) -> StreamingResponse:
    chat_id = str(body.chat_id or uuid4())
    events = service.stream_reply(
        sessionmaker, llm, chat_id, body.query, body.origin, tools, body.answers, body.origin_code, flights
    )
    return StreamingResponse(_ndjson(events), media_type="application/x-ndjson")


@router.get("/chats", response_model=ChatListResponse)
async def list_chats(db: Db, ids: str = "") -> ChatListResponse:
    parsed = [p for p in (_parse_uuid(i.strip()) for i in ids.split(",") if i.strip()) if p]
    if not parsed:
        return ChatListResponse(items=[])
    return ChatListResponse(items=await repository.list_chats(db, parsed[:MAX_LISTED_CHATS]))


@router.get("/chats/{chat_id}", response_model=ChatMeta)
async def get_chat(chat_id: str, db: Db) -> ChatMeta:
    chat = await repository.get_chat(db, _require_uuid(chat_id))
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    return ChatMeta(**chat)


@router.get("/chats/{chat_id}/messages", response_model=ChatMessagesResponse)
async def get_chat_messages(chat_id: str, db: Db) -> ChatMessagesResponse:
    return ChatMessagesResponse(messages=await repository.list_messages(db, _require_uuid(chat_id)))


@router.delete("/chats/{chat_id}", status_code=204)
async def delete_chat(chat_id: str, db: Db) -> Response:
    deleted = await repository.delete_chat(db, _require_uuid(chat_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Chat not found")
    await db.commit()
    return Response(status_code=204)
