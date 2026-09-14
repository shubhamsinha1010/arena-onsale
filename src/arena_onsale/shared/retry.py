import asyncio
from typing import Protocol


class Sleeper(Protocol):
    async def sleep(self, seconds: float) -> None:
        """Pause between optimistic retries. Must not hold a DB transaction."""


class AsyncioSleeper:
    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)
