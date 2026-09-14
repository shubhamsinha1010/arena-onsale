from collections.abc import Iterable
from typing import Any, Protocol

from arena_onsale.catalog.models import SeatStatus


class SeatView(Protocol):
    section: str
    row: str
    number: str
    status: SeatStatus


def assemble_seat_map(
    *,
    match_id: str,
    slug: str,
    seats: Iterable[SeatView],
    ga_available: int | None,
    ga_capacity: int | None,
    ttl_seconds: int,
    from_cache: bool = False,
) -> dict[str, Any]:
    """Build the display-only stadium map. Callers must not book from this."""
    sections: dict[str, dict[str, list[dict[str, str]]]] = {}
    available = 0
    total = 0
    for seat in seats:
        total += 1
        if seat.status is SeatStatus.AVAILABLE:
            available += 1
        rows = sections.setdefault(seat.section, {})
        rows.setdefault(seat.row, []).append({"number": seat.number, "status": seat.status.value})
    ga = (
        None
        if ga_available is None or ga_capacity is None
        else {
            "available": ga_available,
            "capacity": ga_capacity,
            "approximate": True,
        }
    )
    return {
        "match_id": match_id,
        "slug": slug,
        "approximate": True,
        "from_cache": from_cache,
        "ttl_seconds": ttl_seconds,
        "assigned_available": available,
        "assigned_total": total,
        "ga": ga,
        "sections": {code: dict(rows) for code, rows in sorted(sections.items())},
    }
