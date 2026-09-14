from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from arena_onsale.api.deps import get_runtime, get_session
from arena_onsale.inventory.errors import HoldConflictError, SeatUnavailableError
from arena_onsale.inventory.locking import RedisSeatLockGate
from arena_onsale.inventory.models import Hold
from arena_onsale.inventory.schemas import CreateHoldRequest, HeldSeat, HoldResponse
from arena_onsale.inventory.service import HoldService
from arena_onsale.shared.runtime import Runtime

router = APIRouter(tags=["holds"])


def _service(
    session: Annotated[AsyncSession, Depends(get_session)],
    runtime: Annotated[Runtime, Depends(get_runtime)],
) -> HoldService:
    return HoldService(
        session,
        RedisSeatLockGate(runtime.redis),
        runtime.clock,
        runtime.settings,
    )


def _response(hold: Hold, seats: list[HeldSeat]) -> HoldResponse:
    return HoldResponse(
        id=hold.id,
        match_id=hold.match_id,
        status=hold.status.value,
        expires_at=hold.expires_at,
        seats=seats,
    )


async def _held_seats(service: HoldService, hold_id: UUID) -> list[HeldSeat]:
    seats = await service.seats_for_hold(hold_id)
    return [
        HeldSeat(id=seat.id, section=seat.section, row=seat.row, number=seat.number)
        for seat in seats
    ]


@router.post("/matches/{match_id}/holds", response_model=HoldResponse, status_code=201)
async def create_hold(
    match_id: UUID,
    body: CreateHoldRequest,
    response: Response,
    service: Annotated[HoldService, Depends(_service)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> HoldResponse:
    if not idempotency_key.strip():
        raise HTTPException(status_code=400, detail="Idempotency-Key is required")
    try:
        hold, created = await service.reserve(
            match_id=match_id,
            seat_ids=body.seat_ids,
            session_id=body.session_id,
            idempotency_key=idempotency_key,
        )
    except SeatUnavailableError as exc:
        raise HTTPException(
            status_code=409,
            detail={"message": "seat taken", "seat_ids": [str(s) for s in exc.seat_ids]},
        ) from exc
    except HoldConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail="idempotency key already used by another session",
        ) from exc
    if not created:
        response.status_code = 200
    return _response(hold, await _held_seats(service, hold.id))


@router.get("/holds/{hold_id}", response_model=HoldResponse)
async def get_hold(
    hold_id: UUID,
    service: Annotated[HoldService, Depends(_service)],
) -> HoldResponse:
    hold = await service.get(hold_id)
    if hold is None:
        raise HTTPException(status_code=404, detail="hold not found")
    return _response(hold, await _held_seats(service, hold.id))
