class CheckoutError(Exception):
    """Base checkout failure."""


class ReservationNotFoundError(CheckoutError):
    pass


class ReservationNotActiveError(CheckoutError):
    pass


class PaymentFailedError(CheckoutError):
    pass


class FinalizeFailedError(CheckoutError):
    """Inventory could not move to SOLD after a captured payment; refund issued."""
