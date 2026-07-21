"""Point d'entrée de l'API TalentIA.

Assemble l'application : CORS (avec credentials pour le cookie de session),
handlers d'erreurs unifiés et routers.
"""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

# 1. Imports des routes existantes et des nouvelles routes (campagnes & offres)
from app.api.routes import (
    abonnements,
    admin,
    auth,
    campagnes,
    entreprises,
    health,
    offres,
)
from app.core.config import settings
from app.core.responses import (
    http_exception_handler,
    validation_exception_handler,
)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="API TalentIA ATS — avec gestion des Offres & Campagnes.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,  # indispensable pour le cookie httpOnly
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# 2. Déclaration de l'ensemble des routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(entreprises.router)
app.include_router(abonnements.router)
app.include_router(admin.router)

# --- Routes Métier Yasmine ---
app.include_router(campagnes.router)
app.include_router(offres.router)


@app.get("/", tags=["root"])
def root() -> dict:
    return {"success": True, "message": f"{settings.app_name} — documentation sur /docs"}