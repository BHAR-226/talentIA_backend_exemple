"""Pose et efface le cookie de session (httpOnly). Le JWT ne transite jamais
par le corps de réponse ni par le stockage JS — uniquement par ce cookie."""

from typing import Literal

from fastapi import Response

from app.core.config import settings


def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,  # type: ignore[arg-type]
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,  # type: ignore[arg-type]
    )


# Exposé pour référence/typage éventuel des options SameSite acceptées.
SameSite = Literal["lax", "strict", "none"]
