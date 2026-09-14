import pytest

from arena_onsale.load.flood import batch_ranges, flood_queue, visitor_id


def test_visitor_ids_are_stable_and_unique() -> None:
    ids = [visitor_id(i) for i in range(1000)]
    assert ids[0] == "fan-0000000"
    assert ids[-1] == "fan-0000999"
    assert len(set(ids)) == 1000


def test_batch_ranges_cover_the_count_without_overlap() -> None:
    ranges = batch_ranges(12, 5)
    assert ranges == [(0, 5), (5, 10), (10, 12)]
    covered = [index for start, end in ranges for index in range(start, end)]
    assert covered == list(range(12))


def test_batch_ranges_empty_count() -> None:
    assert batch_ranges(0, 5) == []


def test_batch_ranges_reject_bad_sizes() -> None:
    with pytest.raises(ValueError, match="batch_size"):
        batch_ranges(10, 0)
    with pytest.raises(ValueError, match="count"):
        batch_ranges(-1, 5)


@pytest.mark.asyncio
async def test_flood_queue_zero_is_a_noop() -> None:
    assert await flood_queue(count=0) == 0
