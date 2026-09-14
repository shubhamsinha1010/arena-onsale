from collections.abc import Iterator
from dataclasses import dataclass


@dataclass(frozen=True)
class SeatSpec:
    section: str
    row: str
    number: str


@dataclass(frozen=True)
class SectionSpec:
    code: str
    rows: int
    seats_per_row: int


@dataclass(frozen=True)
class StadiumLayout:
    slug: str
    name: str
    venue: str
    sections: tuple[SectionSpec, ...]
    ga_capacity: int

    @property
    def assigned_capacity(self) -> int:
        return sum(section.rows * section.seats_per_row for section in self.sections)

    def seats(self) -> Iterator[SeatSpec]:
        for section in self.sections:
            for row_index in range(section.rows):
                row = _row_label(row_index)
                for seat_n in range(1, section.seats_per_row + 1):
                    yield SeatSpec(section=section.code, row=row, number=str(seat_n))


def _row_label(index: int) -> str:
    label = ""
    remaining = index + 1
    while remaining:
        remaining, remainder = divmod(remaining - 1, 26)
        label = chr(65 + remainder) + label
    return label


# Fast local/CI seed. Enough seats to contend on, small enough to insert quickly.
CUP26_FINAL_SMALL = StadiumLayout(
    slug="cup26-final",
    name="Cup26 Final",
    venue="Harbor Arena",
    sections=(
        SectionSpec("101", rows=5, seats_per_row=8),
        SectionSpec("102", rows=5, seats_per_row=8),
        SectionSpec("VIP", rows=2, seats_per_row=4),
    ),
    ga_capacity=40,
)

# ~80k inventory: 65,000 assigned + 15,000 GA.
CUP26_FINAL = StadiumLayout(
    slug="cup26-final",
    name="Cup26 Final",
    venue="Harbor Arena",
    sections=tuple(
        SectionSpec(code=str(100 + n), rows=25, seats_per_row=130) for n in range(1, 21)
    ),
    ga_capacity=15_000,
)

LAYOUTS: dict[str, StadiumLayout] = {
    "small": CUP26_FINAL_SMALL,
    "full": CUP26_FINAL,
}
