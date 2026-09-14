from arena_onsale.catalog.layout import CUP26_FINAL, CUP26_FINAL_SMALL, _row_label
from arena_onsale.catalog.map_view import assemble_seat_map
from arena_onsale.catalog.models import SeatStatus
from arena_onsale.catalog.seed import known_layouts
from arena_onsale.shared.settings import Settings


def test_row_labels_use_spreadsheet_letters() -> None:
    assert _row_label(0) == "A"
    assert _row_label(25) == "Z"
    assert _row_label(26) == "AA"


def test_small_layout_counts() -> None:
    seats = list(CUP26_FINAL_SMALL.seats())
    assert CUP26_FINAL_SMALL.assigned_capacity == 88
    assert len(seats) == 88
    assert CUP26_FINAL_SMALL.ga_capacity == 40
    assert seats[0].section == "101"
    assert seats[0].row == "A"
    assert seats[0].number == "1"


def test_full_layout_is_eighty_thousand_tickets() -> None:
    assert CUP26_FINAL.assigned_capacity == 65_000
    assert CUP26_FINAL.ga_capacity == 15_000
    assert CUP26_FINAL.assigned_capacity + CUP26_FINAL.ga_capacity == 80_000


def test_known_layouts() -> None:
    assert set(known_layouts()) == {"full", "small"}


def test_map_is_explicitly_approximate() -> None:
    class _Seat:
        section = "101"
        row = "A"
        number = "12"
        status = SeatStatus.AVAILABLE

    payload = assemble_seat_map(
        match_id="m1",
        slug="cup26-final",
        seats=[_Seat()],
        ga_available=10,
        ga_capacity=40,
        ttl_seconds=3,
    )
    assert payload["approximate"] is True
    assert payload["assigned_available"] == 1
    assert payload["ga"] == {"available": 10, "capacity": 40, "approximate": True}
    assert payload["sections"]["101"]["A"][0]["number"] == "12"


def test_seat_map_ttl_is_a_few_seconds() -> None:
    assert 2 <= Settings().seat_map_ttl_seconds <= 5
