from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.llm import LLM


def get_sessionmaker(request: Request) -> async_sessionmaker[AsyncSession]:
    return request.app.state.sessionmaker


def get_llm(request: Request) -> LLM:
    return request.app.state.llm


SessionFactory = Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)]
Llm = Annotated[LLM, Depends(get_llm)]


async def get_db(sessionmaker: SessionFactory) -> AsyncIterator[AsyncSession]:
    async with sessionmaker() as session:
        yield session


Db = Annotated[AsyncSession, Depends(get_db)]
