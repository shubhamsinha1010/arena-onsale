import json
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from arena_onsale.catalog.map_view import assemble_seat_map
from arena_onsale.catalog.models import Match
from arena_onsale.catalog.repository import CatalogRepository
from arena_onsale.shared.redis import RedisClient
from arena_onsale.shared.settings import Settings

SEAT_MAP_CACHE_PREFIX = "catalog:map:"


class CatalogService:
    def __init__(
        self,
        session: AsyncSession,
        redis: RedisClient,
        settings: Settings,
    ) -> None:
        self._repo = CatalogRepository(session)
        self._redis = redis
        self._settings = settings

    async def list_matches(self) -> list[Match]:
        return await self._repo.list_matches()

    async def get_match(self, match_id: UUID) -> Match | None:
        return await self._repo.get_match(match_id)

    async def seat_map(self, match_id: UUID) -> dict[str, Any] | None:
        """Approximate map for display. Booking must not trust this payload."""
        match = await self._repo.get_match(match_id)
        if match is None:
            return None
        cache_key = f"{SEAT_MAP_CACHE_PREFIX}{match_id}"
        cached = await self._redis.get(cache_key)
        if cached is not None:
            payload: dict[str, Any] = json.loads(cached)
            payload["from_cache"] = True
            return payload
        payload = await self._build_map(match)
        await self._redis.set(
            cache_key,
            json.dumps(payload, separators=(",", ":")),
            ex=self._settings.seat_map_ttl_seconds,
        )
        return payload

    async def _build_map(self, match: Match) -> dict[str, Any]:
        seats = await self._repo.list_seats(match.id)
        ga = match.ga
        return assemble_seat_map(
            match_id=str(match.id),
            slug=match.slug,
            seats=seats,
            ga_available=None if ga is None else ga.available,
            ga_capacity=None if ga is None else ga.capacity,
            ttl_seconds=self._settings.seat_map_ttl_seconds,
            from_cache=False,
        )
