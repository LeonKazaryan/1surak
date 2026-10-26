from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.flights import Flights
from app.hotels import HotelSource
from app.llm import LLM
from app.tools import ToolRegistry


def get_sessionmaker(request: Request) -> async_sessionmaker[AsyncSession]:
    return request.app.state.sessionmaker


def get_llm(request: Request) -> LLM:
    return request.app.state.llm


def get_tools(request: Request) -> ToolRegistry:
    return request.app.state.tools


def get_flights(request: Request) -> Flights:
    return request.app.state.flights


def get_hotels(request: Request) -> HotelSource:
    return request.app.state.hotels


def rate_limited(request: Request) -> None:
    request.app.state.rate_limit.hit(request.client.host if request.client else "unknown")


SessionFactory = Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)]
Llm = Annotated[LLM, Depends(get_llm)]
Tools = Annotated[ToolRegistry, Depends(get_tools)]
FlightPrices = Annotated[Flights, Depends(get_flights)]
Hotels = Annotated[HotelSource, Depends(get_hotels)]


async def get_db(sessionmaker: SessionFactory) -> AsyncIterator[AsyncSession]:
    async with sessionmaker() as session:
        yield session


Db = Annotated[AsyncSession, Depends(get_db)]
