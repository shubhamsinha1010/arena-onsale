from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from arena_onsale.api.admission import require_admission
from arena_onsale.api.deps import get_runtime, get_session
from arena_onsale.inventory.errors import (
    GaNotFoundError,
    GaQuantityError,
    GaUnavailableError,
    HoldConflictError,
)
from arena_onsale.inventory.ga_schemas import CreateGaReservationRequest, GaReservationResponse
from arena_onsale.inventory.ga_service import GaReservationService, ga_service
from arena_onsale.inventory.models import GaReservation
from arena_onsale.shared.runtime import Runtime

router = APIRouter(tags=["ga"], dependencies=[Depends(require_admission)])


def get_ga_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    runtime: Annotated[Runtime, Depends(get_runtime)],
) -> GaReservationService:
    return ga_service(session, runtime.clock, runtime.settings)


def _response(reservation: GaReservation) -> GaReservationResponse:
    return GaReservationResponse(
        id=reservation.id,
        match_id=reservation.match_id,
        quantity=reservation.quantity,
        status=reservation.status.value,
        expires_at=reservation.expires_at,
    )


@router.post(
    "/matches/{match_id}/ga-reservations",
    response_model=GaReservationResponse,
    status_code=201,
)
async def create_ga_reservation(
    match_id: UUID,
    body: CreateGaReservationRequest,
    response: Response,
    service: Annotated[GaReservationService, Depends(get_ga_service)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> GaReservationResponse:
    if not idempotency_key.strip():
        raise HTTPException(status_code=400, detail="Idempotency-Key is required")
    try:
        reservation, created = await service.reserve(
            match_id=match_id,
            quantity=body.quantity,
            session_id=body.session_id,
            idempotency_key=idempotency_key,
        )
    except GaQuantityError as exc:
        raise HTTPException(
            status_code=400,
            detail={"message": "quantity not allowed", "maximum": exc.maximum},
        ) from exc
    except GaNotFoundError as exc:
        raise HTTPException(status_code=404, detail="ga pool not found") from exc
    except GaUnavailableError as exc:
        raise HTTPException(
            status_code=409,
            detail="tickets unavailable, please try another match",
        ) from exc
    except HoldConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail="idempotency key already used by another session",
        ) from exc
    if not created:
        response.status_code = 200
    return _response(reservation)


@router.get("/ga-reservations/{reservation_id}", response_model=GaReservationResponse)
async def get_ga_reservation(
    reservation_id: UUID,
    service: Annotated[GaReservationService, Depends(get_ga_service)],
) -> GaReservationResponse:
    reservation = await service.get(reservation_id)
    if reservation is None:
        raise HTTPException(status_code=404, detail="reservation not found")
    return _response(reservation)
