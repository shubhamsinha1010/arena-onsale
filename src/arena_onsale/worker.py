"""Hold and GA reservation expiry worker.

Usage:
    uv run python -m arena_onsale.worker
"""

from __future__ import annotations

import asyncio
import logging

from arena_onsale.checkout.expiry import expire_ga, expire_holds
from arena_onsale.checkout.finalizer import SqlInventoryFinalizer
from arena_onsale.inventory.locking import RedisSeatLockGate
from arena_onsale.shared.runtime import Runtime, build_runtime
from arena_onsale.shared.settings import get_settings

logger = logging.getLogger("arena_onsale.worker")


async def run_once(runtime: Runtime) -> int:
    gate = RedisSeatLockGate(runtime.redis)
    async with runtime.session_factory() as session:
        finalizer = SqlInventoryFinalizer(session)
        now = runtime.clock.now()
        holds = await expire_holds(
            session,
            finalizer,
            gate,
            now=now,
            batch_size=runtime.settings.worker_batch_size,
        )
        ga = await expire_ga(
            session,
            finalizer,
            now=now,
            batch_size=runtime.settings.worker_batch_size,
        )
        admitted = await runtime.waiting_room.admit_tick()
        await session.commit()
        if holds or ga:
            logger.info("expired %s assigned holds and %s ga reservations", holds, ga)
        if admitted:
            logger.info("admitted %s shoppers from the waiting room", admitted)
        return holds + ga + admitted


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    runtime = build_runtime(settings)
    try:
        while True:
            try:
                await run_once(runtime)
            except Exception:
                logger.exception("expiry pass failed")
            await asyncio.sleep(settings.worker_poll_seconds)
    finally:
        await runtime.aclose()


if __name__ == "__main__":
    asyncio.run(main())
