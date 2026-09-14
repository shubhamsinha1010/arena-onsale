from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from arena_onsale.api.deps import get_runtime, get_session
from arena_onsale.catalog.models import Match
from arena_onsale.catalog.schemas import GaSummary, MatchSummary, SeatMapResponse
from arena_onsale.catalog.service import CatalogService
from arena_onsale.shared.runtime import Runtime

router = APIRouter(prefix="/matches", tags=["catalog"])


def _service(
    session: Annotated[AsyncSession, Depends(get_session)],
    runtime: Annotated[Runtime, Depends(get_runtime)],
) -> CatalogService:
    return CatalogService(session, runtime.redis, runtime.settings)


def _summary(match: Match) -> MatchSummary:
    ga = match.ga
    return MatchSummary(
        id=match.id,
        slug=match.slug,
        name=match.name,
        venue=match.venue,
        starts_at=match.starts_at,
        ga=None if ga is None else GaSummary(available=ga.available, capacity=ga.capacity),
    )


@router.get("", response_model=list[MatchSummary])
async def list_matches(
    service: Annotated[CatalogService, Depends(_service)],
) -> list[MatchSummary]:
    matches = await service.list_matches()
    return [_summary(match) for match in matches]


@router.get("/{match_id}", response_model=MatchSummary)
async def get_match(
    match_id: UUID,
    service: Annotated[CatalogService, Depends(_service)],
) -> MatchSummary:
    match = await service.get_match(match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="match not found")
    return _summary(match)


@router.get("/{match_id}/map", response_model=SeatMapResponse)
async def get_seat_map(
    match_id: UUID,
    service: Annotated[CatalogService, Depends(_service)],
) -> dict[str, Any]:
    payload = await service.seat_map(match_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="match not found")
    return payload
