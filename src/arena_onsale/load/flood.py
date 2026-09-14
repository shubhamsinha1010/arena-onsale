"""Enqueue a million waiting-room arrivals directly into Redis.

This is the honest 1M-user story: almost nobody reaches checkout.
HTTP join would be the slow path; batched ZADD is how we fill the room.

Usage:
    uv run python -m arena_onsale.load.flood --count 1000000
"""

from __future__ import annotations

import argparse
import asyncio
import time

from arena_onsale.shared.redis import create_redis
from arena_onsale.shared.settings import get_settings
from arena_onsale.waiting_room.keys import QUEUE_KEY, SEQ_KEY


def visitor_id(index: int, prefix: str = "fan") -> str:
    return f"{prefix}-{index:07d}"


def batch_ranges(count: int, batch_size: int) -> list[tuple[int, int]]:
    if count < 0:
        msg = "count must be >= 0"
        raise ValueError(msg)
    if batch_size <= 0:
        msg = "batch_size must be >= 1"
        raise ValueError(msg)
    return [(start, min(start + batch_size, count)) for start in range(0, count, batch_size)]


async def flood_queue(
    *,
    count: int,
    batch_size: int = 5_000,
    prefix: str = "fan",
) -> int:
    ranges = batch_ranges(count, batch_size)
    if not ranges:
        return 0
    settings = get_settings()
    redis = create_redis(settings)
    added = 0
    try:
        seq_end = int(await redis.incrby(SEQ_KEY, count))
        seq_start = seq_end - count
        for start, end in ranges:
            mapping = {
                visitor_id(index, prefix): float(seq_start + index + 1)
                for index in range(start, end)
            }
            result = await redis.zadd(QUEUE_KEY, mapping, nx=True)
            added += result if isinstance(result, int) else 0
        queued = int(await redis.zcard(QUEUE_KEY))
        print(f"enqueued {added} new visitors; queue depth {queued}")
        return added
    finally:
        await redis.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=1_000_000)
    parser.add_argument("--batch-size", type=int, default=5_000)
    parser.add_argument("--prefix", default="fan")
    args = parser.parse_args()
    started = time.perf_counter()
    added = asyncio.run(
        flood_queue(count=args.count, batch_size=args.batch_size, prefix=args.prefix)
    )
    elapsed = time.perf_counter() - started
    rate = added / elapsed if elapsed else 0
    print(f"done in {elapsed:.2f}s ({rate:,.0f} joins/s)")


if __name__ == "__main__":
    main()
