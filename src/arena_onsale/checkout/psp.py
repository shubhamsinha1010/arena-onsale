from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ChargeResult:
    ok: bool
    psp_ref: str | None
    message: str | None = None


class PaymentProvider(Protocol):
    async def charge(self, *, amount_cents: int, idempotency_key: str) -> ChargeResult:
        """Charge or return the stored result for this idempotency key."""

    async def refund(self, *, psp_ref: str, idempotency_key: str) -> ChargeResult:
        """Refund a captured charge. Same key is a no-op replay."""


class MockPsp:
    """In-process PSP. Duplicate keys never create a second capture."""

    def __init__(self) -> None:
        self._charges: dict[str, ChargeResult] = {}
        self._refunds: dict[str, ChargeResult] = {}
        self.capture_count = 0
        self.refund_count = 0
        self.fail_next_charges = 0

    async def charge(self, *, amount_cents: int, idempotency_key: str) -> ChargeResult:
        del amount_cents
        existing = self._charges.get(idempotency_key)
        if existing is not None:
            return existing
        if self.fail_next_charges > 0:
            self.fail_next_charges -= 1
            result = ChargeResult(ok=False, psp_ref=None, message="mock decline")
        else:
            self.capture_count += 1
            result = ChargeResult(ok=True, psp_ref=f"psp_{idempotency_key}", message=None)
        self._charges[idempotency_key] = result
        return result

    async def refund(self, *, psp_ref: str, idempotency_key: str) -> ChargeResult:
        existing = self._refunds.get(idempotency_key)
        if existing is not None:
            return existing
        self.refund_count += 1
        result = ChargeResult(ok=True, psp_ref=psp_ref, message="refunded")
        self._refunds[idempotency_key] = result
        return result
