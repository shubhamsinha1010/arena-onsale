from uuid import UUID


class SeatUnavailableError(Exception):
    def __init__(self, seat_ids: list[UUID]) -> None:
        self.seat_ids = seat_ids
        super().__init__("one or more seats are not available")


class HoldConflictError(Exception):
    """Idempotency key reused by a different session."""


class GaUnavailableError(Exception):
    """GA pool could not satisfy the request after optimistic retries."""


class GaNotFoundError(Exception):
    """No general-admission pool for this match."""


class GaQuantityError(Exception):
    def __init__(self, quantity: int, maximum: int) -> None:
        self.quantity = quantity
        self.maximum = maximum
        super().__init__("quantity is outside the allowed range")
