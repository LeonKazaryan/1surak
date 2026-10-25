"""Knowledge base entries: one short passage or claim, always with its source (docs/09-living-knowledge-base.md)."""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal
from urllib.parse import urlparse

Topic = Literal["visa", "event", "transport", "hotel", "price", "safety", "weather", "tip", "guide", "food"]
TOPICS: tuple[str, ...] = Topic.__args__

# How long a fact stays fresh, by topic. Time-sensitive topics expire fast so the agent re-checks them.
FRESH_FOR: dict[str, timedelta] = {
    "price": timedelta(days=3),
    "weather": timedelta(days=1),
    "safety": timedelta(days=7),
    "event": timedelta(days=14),
    "visa": timedelta(days=30),
    "transport": timedelta(days=30),
    "hotel": timedelta(days=180),
    "tip": timedelta(days=180),
    "guide": timedelta(days=180),
    "food": timedelta(days=180),
}
TIME_SENSITIVE = {"price", "weather", "safety", "event", "visa", "transport"}

MAX_TEXT_CHARS = 1500

# Official: governments, embassies, carriers, airports. Media: established news outlets. The rest: community.
OFFICIAL_HOSTS = re.compile(
    r"(\.gov(\.[a-z]{2})?$|\.gob\.|\.go\.[a-z]{2}$|\.gouv\.|^gov\.|\.gov\.ru$|mid\.ru$|kdmid\.ru$|"
    r"gosuslugi\.ru$|rzd\.ru$|aeroflot\.ru$|pobeda\.aero$|s7\.ru$|uralairlines\.ru$|immigration\.go\.th$|"
    r"mfa\.|embassy|consulat|visitdubai\.com$|u\.ae$|tourism\.)",
)
MEDIA_HOSTS = re.compile(
    r"(rbc\.ru|ria\.ru|tass\.ru|kommersant\.ru|interfax\.ru|vedomosti\.ru|rg\.ru|lenta\.ru|iz\.ru|"
    r"forbes\.ru|frontier\.ru|atorus\.ru|tourdom\.ru|reuters\.com|apnews\.com|bbc\.|"
    r"wikipedia\.org|wikivoyage\.org)$"
)
CONFIDENCE = {"official": "verified", "media": "secondary", "community": "unverified"}


def source_tier(url: str) -> str:
    host = (urlparse(url).hostname or "").removeprefix("www.")
    if OFFICIAL_HOSTS.search(host):
        return "official"
    if MEDIA_HOSTS.search(host):
        return "media"
    return "community"


def clean_text(text: str) -> str:
    """Web text is data: collapse whitespace, drop markdown images and links' targets, cap the size."""
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[#*_`>|]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_TEXT_CHARS]


def content_hash(text: str) -> str:
    return hashlib.sha256(re.sub(r"\W+", "", text.casefold()).encode()).hexdigest()[:32]


@dataclass
class Entry:
    text: str
    topic: str
    source_url: str
    fetched_at: datetime
    kind: str = "guide"  # fact (one claim), guide (a passage), observation (a dated price or availability)
    source_title: str | None = None
    place_id: str | None = None
    country: str | None = None
    attributes: dict = field(default_factory=dict)
    published_at: str | None = None
    lang: str = "ru"
    created_by: str = "agent"
    query: str | None = None
    source_tier: str | None = None
    valid_until: datetime | None = None
    id: int | None = None
    status: str = "active"
    similarity: float | None = None  # how close in meaning to the last search query; set by search only

    def __post_init__(self):
        if not self.source_url.startswith(("https://", "http://")):
            raise ValueError("no source, no write: source_url must be an http(s) link")
        if self.topic not in TOPICS:
            raise ValueError(f"unknown topic {self.topic!r}")
        self.text = clean_text(self.text)
        if not self.text:
            raise ValueError("empty text")
        if self.fetched_at.tzinfo is None:
            self.fetched_at = self.fetched_at.replace(tzinfo=UTC)
        self.source_tier = self.source_tier or source_tier(self.source_url)
        if self.valid_until is None:
            self.valid_until = self.fetched_at + FRESH_FOR[self.topic]

    @property
    def confidence(self) -> str:
        return CONFIDENCE[self.source_tier]

    @property
    def hash(self) -> str:
        return content_hash(self.text)

    @property
    def entities(self) -> list[dict]:
        found = [{"type": "place", "id": self.place_id}] if self.place_id else []
        return found + ([{"type": "country", "id": self.country}] if self.country else [])

    def fresh(self, now: datetime) -> bool:
        return self.valid_until is None or self.valid_until > now
