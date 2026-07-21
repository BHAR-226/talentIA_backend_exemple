"""Sonde de santé (liveness) — ne dépend pas de la base pour rester verte même
si la DB est momentanément indisponible."""

from fastapi import APIRouter

from app.core.responses import success

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return success({"status": "ok"}, message="API opérationnelle")
