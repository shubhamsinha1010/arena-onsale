from uuid import UUID


class SeatUnavailableError(Exception):
    def __init__(self, seat_ids: list[UUID]) -> None:
        self.seat_ids = seat_ids
        super().__init__("one or more seats are not available")


class HoldConflictError(Exception):
    """Idempotency key reused by a different session."""
