from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from arena_onsale.api.deps import get_runtime
from arena_onsale.shared.runtime import Runtime
from arena_onsale.waiting_room.schemas import JoinRequest, WaitingRoomResponse, WaitingRoomStats

router = APIRouter(prefix="/waiting-room", tags=["waiting-room"])


@router.post("/join", response_model=WaitingRoomResponse)
async def join(
    body: JoinRequest,
    runtime: Annotated[Runtime, Depends(get_runtime)],
) -> dict[str, object]:
    try:
        return await runtime.waiting_room.join(body.visitor_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/status/{visitor_id}", response_model=WaitingRoomResponse)
async def status(
    visitor_id: str,
    runtime: Annotated[Runtime, Depends(get_runtime)],
) -> dict[str, object]:
    snapshot = await runtime.waiting_room.status(visitor_id)
    if snapshot["state"] == "unknown":
        raise HTTPException(status_code=404, detail="visitor is not in the waiting room")
    return snapshot


@router.get("/stats", response_model=WaitingRoomStats)
async def stats(runtime: Annotated[Runtime, Depends(get_runtime)]) -> dict[str, int]:
    return await runtime.waiting_room.stats()
