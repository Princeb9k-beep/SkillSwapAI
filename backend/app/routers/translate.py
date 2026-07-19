"""Live translation endpoints (spec §3.3)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..deps import get_current_user
from ..models import User
from ..responses import ok
from ..schemas import TranslateRequest
from ..skills.translate import LANGUAGES, translate

router = APIRouter(prefix="/translate", tags=["translate"])


@router.get("/languages")
async def languages(_: User = Depends(get_current_user)) -> object:
    return ok(data=LANGUAGES)


@router.post("")
async def do_translate(
    payload: TranslateRequest,
    _: User = Depends(get_current_user),
) -> object:
    """Translate text into a target language."""
    result = await translate(payload.text, payload.target_language)
    return ok(data=result, message="Translated")
