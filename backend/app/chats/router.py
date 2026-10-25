import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse

from app.chats import booking, repository, service
from app.chats.schemas import (
    BookingRequest,
    ChatListResponse,
    ChatMessageOut,
    ChatMessagesResponse,
    ChatMeta,
    ChatRequest,
    RefreshResponse,
)
from app.deps import Db, FlightPrices, Llm, SessionFactory, Tools, rate_limited

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


@router.post("/chat/stream", dependencies=[Depends(rate_limited)])
async def chat_stream(
    body: ChatRequest, sessionmaker: SessionFactory, llm: Llm, tools: Tools, flights: FlightPrices
) -> StreamingResponse:
    chat_id = str(body.chat_id or uuid4())
    events = service.stream_reply(
        sessionmaker,
        llm,
        chat_id,
        body.query,
        body.origin,
        tools,
        body.answers,
        body.origin_code,
        flights,
        body.retry,
    )
    return StreamingResponse(_ndjson(events), media_type="application/x-ndjson")


@router.get("/chats", response_model=ChatListResponse)
async def list_chats(db: Db, ids: str = "") -> ChatListResponse:
    parsed = [p for p in (_parse_uuid(i.strip()) for i in ids.split(",") if i.strip()) if p]
    if not parsed:
        return ChatListResponse(items=[])
    chats = await repository.list_chats(db, parsed[:MAX_LISTED_CHATS])
    return ChatListResponse(items=[ChatMeta(**service.chat_meta(c)) for c in chats])


@router.get("/chats/{chat_id}", response_model=ChatMeta)
async def get_chat(chat_id: str, db: Db) -> ChatMeta:
    chat = await repository.get_chat(db, _require_uuid(chat_id))
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    return ChatMeta(**service.chat_meta(chat))


@router.get("/chats/{chat_id}/messages", response_model=ChatMessagesResponse)
async def get_chat_messages(chat_id: str, db: Db) -> ChatMessagesResponse:
    return ChatMessagesResponse(messages=await repository.list_messages(db, _require_uuid(chat_id)))


@router.post("/chats/{chat_id}/refresh", response_model=RefreshResponse, dependencies=[Depends(rate_limited)])
async def refresh_chat(
    chat_id: str, db: Db, sessionmaker: SessionFactory, flights: FlightPrices
) -> RefreshResponse:
    chat_id = _require_uuid(chat_id)
    if await repository.get_chat(db, chat_id) is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    message = await service.refresh_prices(sessionmaker, flights, chat_id)
    if message is None:
        raise HTTPException(
            status_code=409, detail="Nothing to refresh: no cards yet, or their prices are still fresh"
        )
    chat = await repository.get_chat(db, chat_id)
    return RefreshResponse(message=message, chat=ChatMeta(**service.chat_meta(chat)))


@router.post("/chats/{chat_id}/booking", response_model=ChatMessageOut)
async def book_trip(
    chat_id: str, body: BookingRequest, db: Db, sessionmaker: SessionFactory
) -> ChatMessageOut:
    chat_id = _require_uuid(chat_id)
    if await repository.get_chat(db, chat_id) is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    try:
        saved = await booking.book(sessionmaker, chat_id, body.extras, body.holder, datetime.now(UTC).date())
    except booking.DatesPassed:
        raise HTTPException(status_code=409, detail="The trip dates have passed") from None
    if saved is None:
        raise HTTPException(status_code=404, detail="No trip plan to book yet")
    return ChatMessageOut(**saved)


@router.delete("/chats/{chat_id}", status_code=204)
async def delete_chat(chat_id: str, db: Db) -> Response:
    deleted = await repository.delete_chat(db, _require_uuid(chat_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Chat not found")
    await db.commit()
    return Response(status_code=204)
