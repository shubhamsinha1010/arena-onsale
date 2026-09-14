from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from arena_onsale.api.admission import require_admission
from arena_onsale.api.deps import get_runtime, get_session
from arena_onsale.checkout.errors import (
    FinalizeFailedError,
    PaymentFailedError,
    ReservationNotActiveError,
    ReservationNotFoundError,
)
from arena_onsale.checkout.models import Order
from arena_onsale.checkout.schemas import CheckoutRequest, CheckoutResponse
from arena_onsale.checkout.service import CheckoutService, checkout_service
from arena_onsale.shared.runtime import Runtime

router = APIRouter(tags=["checkout"], dependencies=[Depends(require_admission)])


def get_checkout_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    runtime: Annotated[Runtime, Depends(get_runtime)],
) -> CheckoutService:
    return checkout_service(session, runtime.psp, runtime.clock, runtime.settings)


def _response(order: Order) -> CheckoutResponse:
    return CheckoutResponse(
        id=order.id,
        status=order.status.value,
        amount_cents=order.amount_cents,
        currency=order.currency,
        created_at=order.created_at,
    )


@router.post("/checkout", response_model=CheckoutResponse, status_code=201)
async def create_checkout(
    body: CheckoutRequest,
    response: Response,
    service: Annotated[CheckoutService, Depends(get_checkout_service)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> CheckoutResponse:
    if not idempotency_key.strip():
        raise HTTPException(status_code=400, detail="Idempotency-Key is required")
    try:
        order, created = await service.checkout(
            session_id=body.session_id,
            idempotency_key=idempotency_key,
            hold_id=body.hold_id,
            ga_reservation_id=body.ga_reservation_id,
        )
    except ReservationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="reservation not found") from exc
    except ReservationNotActiveError as exc:
        raise HTTPException(status_code=409, detail="reservation is not active") from exc
    except PaymentFailedError as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc
    except FinalizeFailedError as exc:
        raise HTTPException(
            status_code=409,
            detail="booking could not be confirmed; payment was refunded",
        ) from exc
    if not created:
        response.status_code = 200
    return _response(order)


@router.get("/orders/{order_id}", response_model=CheckoutResponse)
async def get_order(
    order_id: UUID,
    service: Annotated[CheckoutService, Depends(get_checkout_service)],
) -> CheckoutResponse:
    order = await service.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="order not found")
    return _response(order)
