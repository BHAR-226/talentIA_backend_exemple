"""Point d'entrée de l'API TalentIA.

Assemble l'application : CORS (avec credentials pour le cookie de session),
handlers d'erreurs unifiés et routers. Les endpoints métier (auth, entreprises,
offres, candidatures…) seront branchés lot par lot sur ce socle.
"""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import abonnements, admin, auth, entreprises, health
from app.core.config import settings
from app.core.responses import (
    http_exception_handler,
    validation_exception_handler,
)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="API TalentIA ATS — socle (Lot 0).",
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

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(entreprises.router)
app.include_router(abonnements.router)
app.include_router(admin.router)


@app.get("/", tags=["root"])
def root() -> dict:
    return {"success": True, "message": f"{settings.app_name} — documentation sur /docs"}
