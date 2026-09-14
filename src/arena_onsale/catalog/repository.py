from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from arena_onsale.catalog.models import GeneralAdmission, Match, Seat, SeatStatus


class CatalogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_match_by_slug(self, slug: str) -> Match | None:
        result = await self._session.execute(
            select(Match).options(selectinload(Match.ga)).where(Match.slug == slug)
        )
        return result.scalar_one_or_none()

    async def get_match(self, match_id: UUID) -> Match | None:
        result = await self._session.execute(
            select(Match).options(selectinload(Match.ga)).where(Match.id == match_id)
        )
        return result.scalar_one_or_none()

    async def list_matches(self) -> list[Match]:
        result = await self._session.execute(
            select(Match).options(selectinload(Match.ga)).order_by(Match.starts_at)
        )
        return list(result.scalars())

    async def seat_status_counts(self, match_id: UUID) -> dict[SeatStatus, int]:
        result = await self._session.execute(
            select(Seat.status, func.count()).where(Seat.match_id == match_id).group_by(Seat.status)
        )
        return {status: count for status, count in result.all()}

    async def list_seats(self, match_id: UUID) -> list[Seat]:
        result = await self._session.execute(
            select(Seat)
            .where(Seat.match_id == match_id)
            .order_by(Seat.section, Seat.row, Seat.number)
        )
        return list(result.scalars())

    async def add_match(
        self,
        *,
        slug: str,
        name: str,
        venue: str,
        starts_at: datetime,
    ) -> Match:
        match = Match(slug=slug, name=name, venue=venue, starts_at=starts_at)
        self._session.add(match)
        await self._session.flush()
        return match

    async def add_seats(self, seats: list[Seat]) -> None:
        self._session.add_all(seats)
        await self._session.flush()

    async def add_ga(self, ga: GeneralAdmission) -> None:
        self._session.add(ga)
        await self._session.flush()
