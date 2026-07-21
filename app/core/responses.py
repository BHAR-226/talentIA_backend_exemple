"""Conventions de réponse et gestion d'erreurs unifiées.

Toutes les réponses suivent une enveloppe commune :
  succès  → {"success": true,  "message": ..., "data": ...}
  erreur  → {"success": false, "error": {"code", "message", "details"}}

Les handlers ci-dessous appliquent ce format aux exceptions HTTP et aux erreurs
de validation, pour un contrat homogène côté frontend.
"""

from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def success(data: Any = None, message: str | None = None) -> dict[str, Any]:
    return {"success": True, "message": message, "data": data}


def error_payload(
    message: str,
    code: int | str | None = None,
    details: Any = None,
) -> dict[str, Any]:
    return {
        "success": False,
        "error": {"code": code, "message": message, "details": details},
    }


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(str(exc.detail), code=exc.status_code),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=error_payload(
            "Données invalides.", code=422, details=jsonable_encoder(exc.errors())
        ),
    )
