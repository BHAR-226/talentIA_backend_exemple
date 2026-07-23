"""Pose et efface le cookie de session (httpOnly). Le JWT ne transite jamais
par le corps de réponse ni par le stockage JS — uniquement par ce cookie."""

from typing import Literal, Optional

from fastapi import Response

from app.core.config import settings

# Type pour les options SameSite
SameSite = Literal["lax", "strict", "none"]


def set_auth_cookie(
    response: Response,
    token: str,
    max_age: Optional[int] = None,
    path: str = "/",
) -> None:
    """
    Dépose le cookie de session httpOnly contenant le JWT.

    Args:
        response: L'objet Response FastAPI
        token: Le JWT à stocker dans le cookie
        max_age: Durée de vie du cookie en secondes (défaut: config)
        path: Chemin d'accès du cookie (défaut: "/")
    """
    if max_age is None:
        max_age = settings.access_token_expire_minutes * 60

    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,  # type: ignore[arg-type]
        max_age=max_age,
        path=path,
    )


def clear_auth_cookie(
    response: Response,
    path: str = "/",
) -> None:
    """
    Supprime le cookie de session.

    Args:
        response: L'objet Response FastAPI
        path: Chemin d'accès du cookie (défaut: "/")
    """
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path=path,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,  # type: ignore[arg-type]
    )


def refresh_auth_cookie(
    response: Response,
    token: str,
    max_age: Optional[int] = None,
) -> None:
    """
    Rafraîchit le cookie de session avec un nouveau token.

    Utile pour prolonger la durée de session lors d'activité.

    Args:
        response: L'objet Response FastAPI
        token: Le nouveau JWT
        max_age: Durée de vie du cookie en secondes (défaut: config)
    """
    # Supprimer l'ancien cookie
    clear_auth_cookie(response)
    # Déposer le nouveau
    set_auth_cookie(response, token, max_age)


def get_auth_cookie_config() -> dict:
    """
    Retourne la configuration du cookie de session.

    Returns:
        dict: Configuration du cookie (key, httponly, secure, samesite)
    """
    return {
        "key": settings.auth_cookie_name,
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": settings.cookie_samesite,
        "path": "/",
    }


# ==========================================================
# Constantes pour les options de cookie
# ==========================================================

class CookieOptions:
    """Options prédéfinies pour les cookies."""

    # Session standard (défaut)
    SESSION = {
        "httponly": True,
        "secure": False,  # À mettre à True en production
        "samesite": "lax",
        "path": "/",
    }

    # Session sécurisée (production)
    SECURE_SESSION = {
        "httponly": True,
        "secure": True,
        "samesite": "strict",
        "path": "/",
    }

    # Session cross-site (pour API tierces)
    CROSS_SITE = {
        "httponly": True,
        "secure": True,
        "samesite": "none",
        "path": "/",
    }