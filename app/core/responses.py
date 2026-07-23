"""
Conventions de réponse et gestion d'erreurs unifiées.

Toutes les réponses suivent une enveloppe commune :

succès →
{
    "success": true,
    "message": "...",
    "data": ...
}

erreur →
{
    "success": false,
    "error": {
        "code": "...",
        "message": "...",
        "details": ...
    }
}

Les handlers ci-dessous appliquent ce format aux exceptions HTTP
et aux erreurs de validation, pour un contrat homogène côté frontend.
"""

from typing import Any, Generic, Optional, TypeVar

from fastapi import Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

T = TypeVar("T")


# ==========================================================
# Modèle de réponse Pydantic
# ==========================================================

class APIResponse(BaseModel, Generic[T]):
    """
    Enveloppe standard des réponses API.

    Exemple :
    {
        "success": true,
        "message": "Opération réussie.",
        "data": {}
    }
    """

    success: bool
    message: Optional[str] = None
    data: Optional[T] = None

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Opération réussie",
                "data": {"id": "123", "name": "Test"}
            }
        }


class APIError(BaseModel):
    """Modèle d'erreur standardisé."""

    code: Optional[int] = None
    message: str
    details: Optional[Any] = None

    class Config:
        json_schema_extra = {
            "example": {
                "code": 404,
                "message": "Ressource non trouvée",
                "details": {"resource": "user", "id": "123"}
            }
        }


class APIErrorResponse(BaseModel):
    """Réponse d'erreur standardisée."""

    success: bool = False
    error: APIError

    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error": {
                    "code": 404,
                    "message": "Ressource non trouvée",
                    "details": {"resource": "user", "id": "123"}
                }
            }
        }


# ==========================================================
# Fonctions de réponse
# ==========================================================

def success(
    data: Any = None,
    message: Optional[str] = None,
) -> dict[str, Any]:
    """
    Retourne une réponse succès standardisée.

    Args:
        data: Données à retourner (optionnel)
        message: Message de succès (optionnel)

    Returns:
        dict: Réponse formatée {success: True, message, data}

    Exemple:
        return success({"id": 1, "name": "Test"}, "Créé avec succès")
        # {"success": True, "message": "Créé avec succès", "data": {"id": 1, "name": "Test"}}
    """
    return {
        "success": True,
        "message": message,
        "data": data,
    }


def error_payload(
    message: str,
    code: Optional[int] = None,
    details: Any = None,
) -> dict[str, Any]:
    """
    Retourne une réponse erreur standardisée.

    Args:
        message: Message d'erreur
        code: Code d'erreur (optionnel)
        details: Détails supplémentaires (optionnel)

    Returns:
        dict: Réponse formatée {success: False, error: {code, message, details}}

    Exemple:
        return error_payload("Ressource non trouvée", 404, {"id": "123"})
        # {"success": False, "error": {"code": 404, "message": "Ressource non trouvée", "details": {"id": "123"}}}
    """
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details,
        },
    }


def paginated_response(
    items: list[Any],
    total: int,
    page: int,
    per_page: int,
    message: Optional[str] = None,
) -> dict[str, Any]:
    """
    Retourne une réponse paginée standardisée.

    Args:
        items: Liste des éléments de la page
        total: Nombre total d'éléments
        page: Numéro de la page
        per_page: Nombre d'éléments par page
        message: Message optionnel

    Returns:
        dict: Réponse paginée formatée

    Exemple:
        return paginated_response(items, 100, 1, 20)
        # {
        #     "success": True,
        #     "message": None,
        #     "data": [...],
        #     "pagination": {
        #         "page": 1,
        #         "per_page": 20,
        #         "total": 100,
        #         "total_pages": 5,
        #         "has_next": True,
        #         "has_previous": False
        #     }
        # }
    """
    total_pages = (total + per_page - 1) // per_page if per_page > 0 else 0

    return {
        "success": True,
        "message": message,
        "data": items,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_previous": page > 1,
        },
    }


# ==========================================================
# Exception handlers
# ==========================================================

async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """
    Handler pour les exceptions HTTP standardisées.

    Args:
        request: Requête FastAPI
        exc: Exception HTTP

    Returns:
        JSONResponse: Réponse d'erreur formatée
    """
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(
            message=str(exc.detail),
            code=exc.status_code,
        ),
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """
    Handler pour les erreurs de validation Pydantic.

    Args:
        request: Requête FastAPI
        exc: Erreur de validation

    Returns:
        JSONResponse: Réponse d'erreur formatée avec détails de validation
    """
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_payload(
            message="Données invalides.",
            code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=jsonable_encoder(exc.errors()),
        ),
    )


async def generic_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """
    Handler pour les exceptions non gérées.

    Args:
        request: Requête FastAPI
        exc: Exception non gérée

    Returns:
        JSONResponse: Réponse d'erreur formatée
    """
    # Log l'erreur
    import logging
    logger = logging.getLogger("talentia.responses")
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_payload(
            message="Une erreur interne est survenue.",
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details={"error_type": type(exc).__name__} if exc else None,
        ),
    )


# ==========================================================
# Fonctions utilitaires
# ==========================================================

def is_success_response(response: dict) -> bool:
    """
    Vérifie si une réponse est un succès.

    Args:
        response: Réponse à vérifier

    Returns:
        bool: True si la réponse est un succès
    """
    return response.get("success", False)


def get_response_data(response: dict) -> Any:
    """
    Extrait les données d'une réponse.

    Args:
        response: Réponse à extraire

    Returns:
        Any: Données de la réponse
    """
    return response.get("data")


def get_response_message(response: dict) -> Optional[str]:
    """
    Extrait le message d'une réponse.

    Args:
        response: Réponse à extraire

    Returns:
        Optional[str]: Message de la réponse
    """
    return response.get("message")


def get_error_message(response: dict) -> Optional[str]:
    """
    Extrait le message d'erreur d'une réponse.

    Args:
        response: Réponse à extraire

    Returns:
        Optional[str]: Message d'erreur
    """
    error = response.get("error")
    if error:
        return error.get("message")
    return None


def get_error_code(response: dict) -> Optional[int]:
    """
    Extrait le code d'erreur d'une réponse.

    Args:
        response: Réponse à extraire

    Returns:
        Optional[int]: Code d'erreur
    """
    error = response.get("error")
    if error:
        return error.get("code")
    return None