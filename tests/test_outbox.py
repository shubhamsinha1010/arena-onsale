from datetime import UTC, datetime
from uuid import uuid4

import pytest

from arena_onsale.checkout.models import OutboxEvent
from arena_onsale.checkout.outbox import LogTicketNotifier, publish_outbox


class FrozenClock:
    def __init__(self, moment: datetime) -> None:
        self.moment = moment

    def now(self) -> datetime:
        return self.moment


class FakeResult:
    def __init__(self, events: list[OutboxEvent]) -> None:
        self._events = events

    def scalars(self) -> list[OutboxEvent]:
        return self._events


class FakeSession:
    def __init__(self, events: list[OutboxEvent]) -> None:
        self.events = events
        self.executed = False

    async def execute(self, statement: object) -> FakeResult:
        del statement
        self.executed = True
        return FakeResult(self.events)


class RecordingNotifier:
    def __init__(self) -> None:
        self.delivered: list[OutboxEvent] = []

    async def deliver(self, event: OutboxEvent) -> None:
        self.delivered.append(event)


class BoomNotifier:
    async def deliver(self, event: OutboxEvent) -> None:
        del event
        raise RuntimeError("smtp down")


def _event(event_type: str = "TicketConfirmed") -> OutboxEvent:
    return OutboxEvent(
        id=uuid4(),
        aggregate_id=uuid4(),
        event_type=event_type,
        payload={"order_id": "x"},
        created_at=datetime(2026, 7, 19, tzinfo=UTC),
        published_at=None,
    )


@pytest.mark.asyncio
async def test_publish_outbox_delivers_then_stamps_published_at() -> None:
    event = _event()
    session = FakeSession([event])
    notifier = RecordingNotifier()
    clock = FrozenClock(datetime(2026, 7, 19, 12, 0, tzinfo=UTC))
    count = await publish_outbox(session, notifier, clock, batch_size=50)
    assert count == 1
    assert notifier.delivered == [event]
    assert event.published_at == clock.moment


@pytest.mark.asyncio
async def test_publish_outbox_skips_empty_batch() -> None:
    session = FakeSession([])
    count = await publish_outbox(
        session,
        RecordingNotifier(),
        FrozenClock(datetime(2026, 7, 19, tzinfo=UTC)),
        batch_size=10,
    )
    assert count == 0
    assert session.executed is True


@pytest.mark.asyncio
async def test_publish_outbox_zero_batch_does_not_touch_the_db() -> None:
    session = FakeSession([_event()])
    count = await publish_outbox(
        session,
        RecordingNotifier(),
        FrozenClock(datetime(2026, 7, 19, tzinfo=UTC)),
        batch_size=0,
    )
    assert count == 0
    assert session.executed is False


@pytest.mark.asyncio
async def test_deliver_failure_leaves_the_row_unpublished() -> None:
    event = _event()
    session = FakeSession([event])
    with pytest.raises(RuntimeError, match="smtp down"):
        await publish_outbox(
            session,
            BoomNotifier(),
            FrozenClock(datetime(2026, 7, 19, tzinfo=UTC)),
            batch_size=10,
        )
    assert event.published_at is None


@pytest.mark.asyncio
async def test_log_notifier_emails_confirmed_tickets(caplog: pytest.LogCaptureFixture) -> None:
    event = _event("TicketConfirmed")
    with caplog.at_level("INFO", logger="arena_onsale.outbox"):
        await LogTicketNotifier().deliver(event)
    assert "email+qr" in caplog.text
    assert str(event.aggregate_id) in caplog.text


@pytest.mark.asyncio
async def test_log_notifier_alerts_on_finalize_failed(caplog: pytest.LogCaptureFixture) -> None:
    event = _event("FinalizeFailed")
    with caplog.at_level("ERROR", logger="arena_onsale.outbox"):
        await LogTicketNotifier().deliver(event)
    assert "ops alert" in caplog.text
    assert "FinalizeFailed" in caplog.text
