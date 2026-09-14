from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Shopper:
    visitor_id: str
    token: str
    expires_at: float


class WaitingRoomStore(Protocol):
    async def next_score(self) -> float:
        """Monotonic join order. Lower is closer to the front."""

    async def enqueue(self, visitor_id: str, score: float) -> bool:
        """True when the visitor was newly queued."""

    async def rank(self, visitor_id: str) -> int | None:
        """0-based index from the front, or None if not queued."""

    async def queue_size(self) -> int: ...

    async def pop_front(self, n: int) -> list[str]: ...

    async def put_shopper(self, shopper: Shopper, ttl_seconds: int) -> None: ...

    async def get_shopper(self, visitor_id: str) -> Shopper | None: ...

    async def visitor_for_token(self, token: str) -> str | None: ...

    async def gc_shoppers(self, now: float) -> None: ...

    async def shopper_count(self, now: float) -> int: ...

    async def take_rate_tokens(self, epoch_second: int, limit: int, wanted: int) -> int:
        """Grant up to ``wanted`` admits without exceeding ``limit`` this second."""
