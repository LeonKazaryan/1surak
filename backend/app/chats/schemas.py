from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

from app.money import CurrencyCode
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


MAX_HISTORY = 50  # as many chats as the browser keeps
MAX_FORGET = 60
ForgetKey = Annotated[str, StringConstraints(min_length=1, max_length=120, pattern=r"^[^\x00-\x1f\x7f]+$")]


class ChatRequest(BaseModel):
    query: Query
    chat_id: UUID | None = None
    origin: Origin | None = None
    origin_code: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")] | None = None  # IATA of the city
    # False when the browser could not detect the city and fell back to Moscow: then the agent asks
    origin_known: bool = True
    answers: BriefPatch | None = None  # what the user picked on the question cards
    retry: bool = False  # ask again in place of the last turn, when that turn failed
    # picked on the start screen; None follows the departure city
    currency: CurrencyCode | None = None
    # the browser's other chats: the traveller's earlier trips, offered from memory, never applied
    history: list[UUID] = Field(default_factory=list, max_length=MAX_HISTORY)
    forget: list[ForgetKey] = Field(default_factory=list, max_length=MAX_FORGET)  # facts hidden on screen


class ChatMeta(BaseModel):
    id: str
    title: str | None
    created_at: str
    updated_at: str
    summary: list[str] = []
    passport: dict | None = None  # the trip field by field, for the chat's header (app.trip.passport)
    departure: str | None = None  # «из Астаны»
    priced_at: str | None = None
    stale: bool = False
    dates_passed: bool = False
    nudge: dict | None = None  # {"text", "source"}: a quick reply from the traveller's earlier trips


class MemoryFact(BaseModel):
    key: str
    label: str
    text: str
    source: str
    chat_id: str


class Idea(BaseModel):
    label: str
    query: str | None = None  # sent as the message; None for a trip to open as it is
    chat_id: str | None = None  # an earlier trip this idea opens
    why: str | None = None  # what in memory it comes from: «бронь 1S-ABC234», «помню: вдвоём + ребёнок 6 лет»


class MemoryRequest(BaseModel):
    history: list[UUID] = Field(default_factory=list, max_length=MAX_HISTORY)  # the browser's chats
    forget: list[ForgetKey] = Field(default_factory=list, max_length=MAX_FORGET)


class MemoryResponse(BaseModel):
    facts: list[MemoryFact]
    ideas: list[Idea]


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
