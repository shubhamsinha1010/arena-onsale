"""Load Cup26 catalog data. Idempotent on match slug.

Usage:
    uv run python -m arena_onsale.catalog.seed --layout small
"""

from __future__ import annotations

import argparse
import asyncio

from arena_onsale.catalog.seed import known_layouts, seed_cup26
from arena_onsale.shared.db import create_engine, create_session_factory
from arena_onsale.shared.settings import get_settings


async def _run(layout: str) -> None:
    settings = get_settings()
    engine = create_engine(settings, admin=True)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            match = await seed_cup26(session, layout_name=layout)
            ga = match.ga
            ga_note = "no GA" if ga is None else f"{ga.available}/{ga.capacity} GA"
            print(f"seeded {match.slug} ({match.id}) — {ga_note}")
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layout", choices=list(known_layouts()), default="small")
    args = parser.parse_args()
    asyncio.run(_run(args.layout))


if __name__ == "__main__":
    main()
