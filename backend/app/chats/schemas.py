from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

from app.trip import BriefPatch

MAX_QUERY_CHARS = 12_000
MAX_ORIGIN_CHARS = 64

Query = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_QUERY_CHARS)]
Origin = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=MAX_ORIGIN_CHARS, pattern=r"^[^\x00-\x1f\x7f  ]+$"
    ),
]


class ChatRequest(BaseModel):
    query: Query
    chat_id: UUID | None = None
    origin: Origin | None = None
    origin_code: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")] | None = None  # IATA of the city
    answers: BriefPatch | None = None  # what the user picked on the question cards
    retry: bool = False  # ask again in place of the last turn, when that turn failed


class ChatMeta(BaseModel):
    id: str
    title: str | None
    created_at: str
    updated_at: str
    summary: list[str] = []
    departure: str | None = None  # «из Астаны»
    priced_at: str | None = None
    stale: bool = False
    dates_passed: bool = False


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


class RefreshResponse(BaseModel):
    message: ChatMessageOut
    chat: ChatMeta


Holder = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=2, max_length=80, pattern=r"^[^\x00-\x1f\x7f<>]+$"),
]


ExtraId = Annotated[
    str, StringConstraints(pattern=r"^(early_check_in|late_check_out):[a-z0-9_]{1,40}-h\d{1,3}$")
]


class BookingRequest(BaseModel):
    extras: list[ExtraId] = Field(default_factory=list, max_length=6)  # one fix id per stop and kind
    holder: Holder  # the lead traveller, as on the booking
