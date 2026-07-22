"""
Routes API pour la gestion des candidatures.
"""

import json
import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.api.deps import (
    CurrentIdentity,
    get_current_identity,
    require_roles,
)
from app.core.database import get_db
from app.core.enums import RoleUtilisateur
from app.core.responses import APIResponse, success
from app.models.offre import Offre
from app.models.utilisateur import Utilisateur
from app.schemas.candidature import (
    CandidatureResponse,
    CandidatureUpdateStatut,
)
from app.services import candidature_service

router = APIRouter(
    prefix="/candidatures",
    tags=["Candidatures"],
)


_require_recruteur_ou_admin = require_roles(
    RoleUtilisateur.recruteur,
    RoleUtilisateur.admin_rh,
)


UPLOAD_DIR = Path("storage/cvs")

MAX_FILE_SIZE = 5 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".docx",
}


# ==========================================================
# Création candidature
# ==========================================================


@router.post(
    "",
    response_model=APIResponse[CandidatureResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_candidature(
    offre_id: uuid.UUID = Form(...),
    lettre_motivation: str | None = Form(None),
    champs_personnalises: str = Form("{}"),
    cv: UploadFile = File(...),
    db: Session = Depends(get_db),
    identity: CurrentIdentity = Depends(get_current_identity),
):

    if identity.type != "candidat":
        raise HTTPException(
            status_code=403,
            detail="Seuls les candidats peuvent déposer une candidature.",
        )


    offre = db.get(
        Offre,
        offre_id,
    )


    if offre is None:
        raise HTTPException(
            status_code=404,
            detail="Offre introuvable.",
        )


    if not offre.reception_ouverte:
        raise HTTPException(
            status_code=409,
            detail="Cette offre n'accepte plus de candidatures.",
        )


    extension = Path(
        cv.filename
    ).suffix.lower()


    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Format CV invalide. PDF ou DOCX uniquement.",
        )


    content = cv.file.read()


    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Le CV dépasse la taille maximale autorisée (5 Mo).",
        )


    UPLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


    filename = (
        f"{uuid.uuid4()}"
        f"{extension}"
    )


    file_path = UPLOAD_DIR / filename


    with open(file_path, "wb") as buffer:
        buffer.write(content)


    try:
        champs = json.loads(
            champs_personnalises
        )
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Format champs_personnalises invalide.",
        ) from None


    try:

        candidature = candidature_service.create(
            db,
            offre=offre,
            candidat_id=identity.id,
            lettre_motivation=lettre_motivation,
            cv_url=str(file_path),
            champs_personnalises=champs,
        )

    except ValueError as error:

        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from None


    return success(
        data=candidature,
        message="Candidature créée avec succès.",
    )



# ==========================================================
# Lecture
# ==========================================================


@router.get(
    "/{candidature_id}",
    response_model=APIResponse[CandidatureResponse],
)
def get_candidature(
    candidature_id: uuid.UUID,
    db: Session = Depends(get_db),
):

    candidature = candidature_service.get(
        db,
        candidature_id,
    )

    if candidature is None:
        raise HTTPException(
            status_code=404,
            detail="Candidature non trouvée.",
        )


    return success(
        data=candidature,
        message="Candidature récupérée.",
    )



@router.get(
    "/candidat/{candidat_id}",
    response_model=APIResponse[list[CandidatureResponse]],
)
def list_by_candidat(
    candidat_id: uuid.UUID,
    db: Session = Depends(get_db),
):

    return success(
        data=candidature_service.list_by_candidat(
            db,
            candidat_id,
        ),
        message="Historique des candidatures.",
    )



@router.get(
    "/offre/{offre_id}",
    response_model=APIResponse[list[CandidatureResponse]],
)
def list_by_offre(
    offre_id: uuid.UUID,
    db: Session = Depends(get_db),
):

    return success(
        data=candidature_service.list_by_offre(
            db,
            offre_id,
        ),
        message="Candidatures de l'offre.",
    )



# ==========================================================
# Mise à jour statut Kanban
# ==========================================================


@router.put(
    "/{candidature_id}/statut",
    response_model=APIResponse[CandidatureResponse],
)
def update_statut(
    candidature_id: uuid.UUID,
    statut_in: CandidatureUpdateStatut,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(
        _require_recruteur_ou_admin
    ),
):

    candidature = candidature_service.get(
        db,
        candidature_id,
    )


    if candidature is None:
        raise HTTPException(
            status_code=404,
            detail="Candidature non trouvée.",
        )


    candidature = candidature_service.update_statut(
        db,
        candidature,
        statut_in.statut,
    )


    return success(
        data=candidature,
        message="Statut mis à jour.",
    )