"""
UX/UI Pro Max — consistent API response ergonomics.

The `nextlevelbuilder/ui-ux-pro-max-skill` emphasizes consistent, predictable UI
states (loading / success / empty / error) and clear messaging. We mirror that on
the API boundary so the frontend can render those states uniformly: every endpoint
returns the same envelope shape, and every error carries a human-readable message.

    { "success": bool, "data": <payload|null>, "message": str, "meta": {...} }
"""

from __future__ import annotations

from typing import Any

from fastapi import status
from fastapi.responses import JSONResponse


def ok(
    data: Any = None,
    message: str = "OK",
    meta: dict[str, Any] | None = None,
    status_code: int = status.HTTP_200_OK,
) -> JSONResponse:
    """A successful response in the standard envelope."""
    return JSONResponse(
        status_code=status_code,
        content={
            "success": True,
            "data": data,
            "message": message,
            "meta": meta or {},
        },
    )


def error(
    message: str,
    status_code: int = status.HTTP_400_BAD_REQUEST,
    *,
    code: str | None = None,
    details: Any = None,
) -> JSONResponse:
    """
    An error response in the standard envelope. `message` is always safe to show
    to a user; `code` is a stable machine string the frontend can branch on.
    """
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "data": None,
            "message": message,
            "meta": {"code": code or "error", "details": details},
        },
    )


def envelope(data: Any, message: str = "OK", meta: dict[str, Any] | None = None) -> dict:
    """Plain dict variant, for endpoints declared with a response_model or returned raw."""
    return {"success": True, "data": data, "message": message, "meta": meta or {}}
