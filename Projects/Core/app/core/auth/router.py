from fastapi import APIRouter, Depends

from app.core.auth.dependency import require_principal
from app.core.auth.principal import Principal

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.get("/whoami")
def whoami(principal: Principal = Depends(require_principal)):
    return {"principal_id": principal.principal_id, "name": principal.name}
