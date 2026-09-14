from typing import Annotated

from fastapi import Depends, Header, HTTPException

from arena_onsale.api.deps import get_runtime
from arena_onsale.shared.runtime import Runtime


async def require_admission(
    runtime: Annotated[Runtime, Depends(get_runtime)],
    admission_token: Annotated[str | None, Header(alias="Admission-Token")] = None,
) -> str:
    """Catalog, holds, and checkout are behind the waiting room."""
    if not admission_token or not admission_token.strip():
        raise HTTPException(status_code=401, detail="Admission-Token is required")
    visitor_id = await runtime.waiting_room.visitor_for_token(admission_token.strip())
    if visitor_id is None:
        raise HTTPException(status_code=403, detail="admission token is invalid or expired")
    return visitor_id
