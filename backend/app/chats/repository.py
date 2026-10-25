from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import chat_messages, chats, trip_briefs


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime) -> str:
    return (value if value.tzinfo else value.replace(tzinfo=UTC)).isoformat()


def _chat_row(row) -> dict:
    return {
        "id": row.id,
        "title": row.title,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
        "brief": row.brief,
    }


def _with_brief():
    return select(chats, trip_briefs.c.brief).outerjoin(trip_briefs, trip_briefs.c.chat_id == chats.c.id)


def _message_row(row) -> dict:
    return {
        "id": row.id,
        "chat_id": row.chat_id,
        "role": row.role,
        "content": row.content,
        "trace": row.trace or [],
        "created_at": _iso(row.created_at),
    }


async def ensure_chat(db: AsyncSession, chat_id: str, title: str) -> str:
    existing = (await db.execute(select(chats.c.title).where(chats.c.id == chat_id))).first()
    if existing:
        return existing.title
    now = _now()
    await db.execute(insert(chats).values(id=chat_id, title=title, created_at=now, updated_at=now))
    return title


async def get_chat(db: AsyncSession, chat_id: str) -> dict | None:
    row = (await db.execute(_with_brief().where(chats.c.id == chat_id))).first()
    return _chat_row(row) if row else None


async def list_chats(db: AsyncSession, chat_ids: list[str]) -> list[dict]:
    query = _with_brief().where(chats.c.id.in_(chat_ids)).order_by(chats.c.updated_at.desc())
    return [_chat_row(row) for row in (await db.execute(query)).all()]


async def list_messages(db: AsyncSession, chat_id: str) -> list[dict]:
    query = (
        select(chat_messages).where(chat_messages.c.chat_id == chat_id).order_by(chat_messages.c.created_at)
    )
    return [_message_row(row) for row in (await db.execute(query)).all()]


async def recent_turns(db: AsyncSession, chat_id: str, limit: int) -> list[dict]:
    query = (
        select(chat_messages.c.role, chat_messages.c.content)
        .where(chat_messages.c.chat_id == chat_id)
        .order_by(chat_messages.c.created_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(query)).all()
    return [{"role": row.role, "content": row.content} for row in reversed(rows)]


async def add_message(
    db: AsyncSession, chat_id: str, role: str, content: str, trace: list[dict] | None = None
) -> dict:
    now = _now()
    row = {"id": str(uuid4()), "chat_id": chat_id, "role": role, "content": content, "trace": trace or []}
    await db.execute(insert(chat_messages).values(**row, created_at=now))
    await db.execute(update(chats).where(chats.c.id == chat_id).values(updated_at=now))
    return {**row, "created_at": _iso(now)}


async def drop_failed_turn(db: AsyncSession, chat_id: str) -> bool:
    """Deletes the last question and its reply when the reply is an agent error, so a retry takes their place."""
    query = (
        select(chat_messages.c.id, chat_messages.c.role, chat_messages.c.trace)
        .where(chat_messages.c.chat_id == chat_id)
        .order_by(chat_messages.c.created_at.desc())
        .limit(2)
    )
    rows = (await db.execute(query)).all()
    if len(rows) < 2:
        return False
    reply, question = rows
    failed = reply.role == "assistant" and any(e.get("type") == "error" for e in reply.trace or [])
    if not failed or question.role != "user":
        return False
    await db.execute(delete(chat_messages).where(chat_messages.c.id.in_([reply.id, question.id])))
    return True


async def get_brief(db: AsyncSession, chat_id: str) -> dict | None:
    row = (await db.execute(select(trip_briefs.c.brief).where(trip_briefs.c.chat_id == chat_id))).first()
    return row.brief if row else None


async def save_brief(db: AsyncSession, chat_id: str, brief: dict) -> None:
    values = {"brief": brief, "updated_at": _now()}
    result = await db.execute(update(trip_briefs).where(trip_briefs.c.chat_id == chat_id).values(**values))
    if result.rowcount == 0:
        await db.execute(insert(trip_briefs).values(chat_id=chat_id, **values))


async def delete_chat(db: AsyncSession, chat_id: str) -> bool:
    await db.execute(delete(trip_briefs).where(trip_briefs.c.chat_id == chat_id))
    await db.execute(delete(chat_messages).where(chat_messages.c.chat_id == chat_id))
    result = await db.execute(delete(chats).where(chats.c.id == chat_id))
    return result.rowcount > 0
