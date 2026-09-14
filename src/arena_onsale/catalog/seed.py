from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from arena_onsale.catalog.layout import LAYOUTS, StadiumLayout
from arena_onsale.catalog.models import GeneralAdmission, Match, Seat, SeatStatus
from arena_onsale.catalog.repository import CatalogRepository

_INSERT_CHUNK = 5_000


async def seed_cup26(
    session: AsyncSession,
    *,
    layout_name: str = "small",
    starts_at: datetime | None = None,
) -> Match:
    try:
        layout = LAYOUTS[layout_name]
    except KeyError as exc:
        msg = f"unknown layout {layout_name!r}; choose from {sorted(LAYOUTS)}"
        raise ValueError(msg) from exc
    return await seed_layout(
        session,
        layout,
        starts_at=starts_at or datetime(2026, 7, 19, 18, 0, tzinfo=UTC),
    )


async def seed_layout(
    session: AsyncSession,
    layout: StadiumLayout,
    *,
    starts_at: datetime,
) -> Match:
    repo = CatalogRepository(session)
    existing = await repo.get_match_by_slug(layout.slug)
    if existing is not None:
        return existing
    match = await repo.add_match(
        slug=layout.slug,
        name=layout.name,
        venue=layout.venue,
        starts_at=starts_at,
    )
    await _insert_seats(session, match_id=match.id, layout=layout)
    await repo.add_ga(
        GeneralAdmission(
            match_id=match.id,
            capacity=layout.ga_capacity,
            available=layout.ga_capacity,
            version=1,
        )
    )
    await session.commit()
    reloaded = await repo.get_match_by_slug(layout.slug)
    if reloaded is None:
        msg = f"failed to reload seeded match {layout.slug}"
        raise RuntimeError(msg)
    return reloaded


async def _insert_seats(
    session: AsyncSession,
    *,
    match_id: UUID,
    layout: StadiumLayout,
) -> None:
    chunk: list[dict[str, object]] = []
    for spec in layout.seats():
        chunk.append(
            {
                "id": uuid4(),
                "match_id": match_id,
                "section": spec.section,
                "row": spec.row,
                "number": spec.number,
                "status": SeatStatus.AVAILABLE,
                "version": 1,
            }
        )
        if len(chunk) >= _INSERT_CHUNK:
            await session.execute(insert(Seat), chunk)
            chunk = []
    if chunk:
        await session.execute(insert(Seat), chunk)


def known_layouts() -> Sequence[str]:
    return sorted(LAYOUTS)
