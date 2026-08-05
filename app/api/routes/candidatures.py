"""Routes API pour la gestion des candidatures.
"""

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_candidat, get_current_user
from app.core.database import get_db
from app.core.enums import RoleUtilisateur, StatutCandidature
from app.core.plans import get_plan_limits
from app.core.responses import success
from app.core.validators import validate_custom_fields, validate_file_upload
from app.models.abonnement import Abonnement
from app.models.campagne import Campagne
from app.models.candidat import Candidat
from app.models.candidature import Candidature
from app.models.offre import Offre
from app.models.utilisateur import Utilisateur
from app.schemas.candidature import (
    CandidatureBulkUpdate,
    CandidatureResponse,
    CandidatureUpdate,
    CandidatureUpdateStatut,
)

router = APIRouter(prefix="/candidatures", tags=["candidatures"])

# Configuration du dossier de stockage des CV
UPLOAD_DIR = Path("storage/cvs")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ==========================================================
# Fonctions utilitaires
# ==========================================================

def _get_candidature_or_404(
    db: Session,
    candidature_id: uuid.UUID,
    entreprise_id: uuid.UUID | None = None,
    candidat_id: uuid.UUID | None = None
) -> Candidature:
    """Récupère une candidature avec vérification des droits."""
    query = db.query(Candidature)

    if entreprise_id:
        query = query.join(Offre).join(Campagne).filter(
            Campagne.entreprise_id == entreprise_id,
            Campagne.deleted_at.is_(None)
        )
    elif candidat_id:
        query = query.filter(Candidature.candidat_id == candidat_id)

    candidature = query.filter(
        Candidature.id == candidature_id,
        Candidature.deleted_at.is_(None)  # Soft delete
    ).first()

    if candidature is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Candidature introuvable.")
    return candidature


def _check_recruteur_or_admin(user: Utilisateur) -> None:
    """Vérifie que l'utilisateur est recruteur ou admin RH."""
    if user.role not in (RoleUtilisateur.recruteur, RoleUtilisateur.admin_rh):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Réservé aux recruteurs et administrateurs RH."
        )


# ==========================================================
# Création d'une candidature
# ==========================================================

@router.post("", status_code=status.HTTP_201_CREATED)
def postuler(
    offre_id: uuid.UUID = Form(...),
    lettre_motivation: str | None = Form(None),
    champs_personnalises: str = Form("{}"),
    cv: UploadFile = File(...),
    db: Session = Depends(get_db),
    candidat: Candidat = Depends(get_current_candidat),
):
    """Postuler à une offre avec upload de CV.

    **Champs :**
    - `offre_id` : ID de l'offre (requis)
    - `lettre_motivation` : Lettre de motivation (optionnel)
    - `champs_personnalises` : JSON des réponses aux champs personnalisés
    - `cv` : Fichier CV (PDF ou DOCX, max 5Mo)
    """
    # Vérifier que l'offre existe et est ouverte
    offre = db.get(Offre, offre_id)
    if offre is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Offre introuvable.")

    if offre.is_deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Offre introuvable.")

    if not offre.reception_ouverte:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Cette offre n'accepte plus de candidatures."
        )

    if offre.date_limite is not None and datetime.now(UTC) > offre.date_limite:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "La date limite de candidature est dépassée."
        )

    if not offre.est_publiee:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Cette offre n'est pas publiée."
        )

    # Vérifier que le candidat n'a pas déjà postulé
    existing = (
        db.query(Candidature)
        .filter(
            Candidature.offre_id == offre_id,
            Candidature.candidat_id == candidat.id,
            Candidature.deleted_at.is_(None)
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Vous avez déjà postulé à cette offre."
        )

    # Vérifier le quota de candidatures par offre du plan d'abonnement
    campagne = db.get(Campagne, offre.campagne_id)
    if campagne is not None:
        abonnement = (
            db.query(Abonnement)
            .filter(Abonnement.entreprise_id == campagne.entreprise_id)
            .first()
        )
        if abonnement is not None:
            limite = get_plan_limits(abonnement.plan).get("candidatures_par_offre")
            if limite is not None:
                nb_candidatures = (
                    db.query(Candidature)
                    .filter(
                        Candidature.offre_id == offre_id,
                        Candidature.deleted_at.is_(None),
                    )
                    .count()
                )
                if nb_candidatures >= limite:
                    raise HTTPException(
                        status.HTTP_403_FORBIDDEN,
                        "Cette offre a atteint son nombre maximum de candidatures."
                    )

    # Valider les champs personnalisés
    try:
        champs = json.loads(champs_personnalises)
    except json.JSONDecodeError:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Format champs_personnalises invalide."
        ) from None

    if offre.champs_personnalises_def:
        try:
            validate_custom_fields(champs, offre.champs_personnalises_def)
        except ValueError as e:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from e

    # Valider et sauvegarder le CV
    try:
        content = cv.file.read()
        file_info = validate_file_upload(cv.filename or "unknown", content)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from e

    # Sauvegarder le fichier
    filename = f"{uuid.uuid4()}{file_info['extension']}"
    file_path = UPLOAD_DIR / filename

    with open(file_path, "wb") as buffer:
        buffer.write(content)

    # URL servie par le mount StaticFiles `/static/cv` (voir app/main.py)
    cv_url = f"/static/cv/{filename}"

    # Créer la candidature
    candidature = Candidature(
        offre_id=offre_id,
        candidat_id=candidat.id,
        lettre_motivation=lettre_motivation,
        champs_personnalises=champs,
        cv_url=cv_url,
    )

    db.add(candidature)
    db.commit()
    db.refresh(candidature)

    return success(
        CandidatureResponse.model_validate(candidature),
        "Candidature soumise avec succès."
    )


@router.get("/me")
def mes_candidatures(
    candidat: Candidat = Depends(get_current_candidat),
    statut: str | None = Query(None, description="Filtrer par statut"),
    db: Session = Depends(get_db),
):
    """Liste toutes les candidatures du candidat connecté."""
    query = db.query(Candidature).filter(
        Candidature.candidat_id == candidat.id,
        Candidature.deleted_at.is_(None)
    )

    if statut:
        query = query.filter(Candidature.statut == statut)

    candidatures = query.order_by(Candidature.created_at.desc()).all()
    return success([CandidatureResponse.model_validate(c) for c in candidatures])


# ==========================================================
# Lecture des candidatures (recruteur)
# ==========================================================

@router.get("")
def lister_candidatures(
    user: Utilisateur = Depends(get_current_user),
    statut: StatutCandidature | None = Query(None, description="Filtrer par statut"),
    offre_id: uuid.UUID | None = Query(None, description="Filtrer par offre"),
    search: str | None = Query(None, description="Recherche sur le nom/email du candidat"),
    db: Session = Depends(get_db),
):
    """Liste toutes les candidatures de l'entreprise (vue Kanban global).

    **Filtres disponibles :**
    - `statut` : Filtrer par statut de candidature
    - `offre_id` : Filtrer par offre
    - `search` : Recherche textuelle sur le nom ou l'email du candidat

    **Permissions :** Recruteur ou Admin RH.
    """
    _check_recruteur_or_admin(user)

    query = (
        db.query(Candidature)
        .join(Offre)
        .join(Campagne)
        .filter(
            Campagne.entreprise_id == user.entreprise_id,
            Campagne.deleted_at.is_(None),
            Candidature.deleted_at.is_(None),
        )
    )

    if statut:
        query = query.filter(Candidature.statut == statut)

    if offre_id:
        query = query.filter(Candidature.offre_id == offre_id)

    if search:
        query = query.join(Candidat, Candidature.candidat_id == Candidat.id).filter(
            or_(
                Candidat.nom.ilike(f"%{search}%"),
                Candidat.email.ilike(f"%{search}%"),
            )
        )

    candidatures = query.order_by(Candidature.date_soumission.desc()).all()
    return success([CandidatureResponse.model_validate(c) for c in candidatures])


@router.get("/offre/{offre_id}")
def candidatures_offre(
    offre_id: uuid.UUID,
    user: Utilisateur = Depends(get_current_user),
    statut: str | None = Query(None, description="Filtrer par statut"),
    db: Session = Depends(get_db),
):
    """Liste toutes les candidatures d'une offre."""
    _check_recruteur_or_admin(user)

    # Vérifier que l'offre appartient à l'entreprise
    offre = (
        db.query(Offre)
        .join(Campagne)
        .filter(
            Offre.id == offre_id,
            Campagne.entreprise_id == user.entreprise_id,
            Offre.deleted_at.is_(None)
        )
        .first()
    )
    if offre is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Offre introuvable.")

    query = db.query(Candidature).filter(
        Candidature.offre_id == offre_id,
        Candidature.deleted_at.is_(None)
    )

    if statut:
        query = query.filter(Candidature.statut == statut)

    candidatures = query.order_by(Candidature.date_soumission.desc()).all()
    return success([CandidatureResponse.model_validate(c) for c in candidatures])


@router.get("/candidat/{candidat_id}")
def list_by_candidat(
    candidat_id: uuid.UUID,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Liste toutes les candidatures d'un candidat (accès recruteur/admin RH)."""
    _check_recruteur_or_admin(user)

    # Vérifier que le candidat a postulé à des offres de l'entreprise
    query = (
        db.query(Candidature)
        .join(Offre)
        .join(Campagne)
        .filter(
            Candidature.candidat_id == candidat_id,
            Campagne.entreprise_id == user.entreprise_id,
            Candidature.deleted_at.is_(None)
        )
    )

    candidatures = query.order_by(Candidature.created_at.desc()).all()
    return success([CandidatureResponse.model_validate(c) for c in candidatures])


@router.get("/{candidature_id}")
def get_candidature(
    candidature_id: uuid.UUID,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Récupère une candidature (accès recruteur/admin RH)."""
    _check_recruteur_or_admin(user)
    candidature = _get_candidature_or_404(db, candidature_id, user.entreprise_id)
    return success(CandidatureResponse.model_validate(candidature))


# ==========================================================
# Mise à jour du statut
# ==========================================================

@router.put("/{candidature_id}/statut")
def update_statut_candidature(
    candidature_id: uuid.UUID,
    payload: CandidatureUpdateStatut,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Met à jour le statut d'une candidature (pipeline Kanban).

    **Permissions :** Recruteur ou Admin RH.
    """
    _check_recruteur_or_admin(user)
    candidature = _get_candidature_or_404(db, candidature_id, user.entreprise_id)

    # Mettre à jour le statut
    candidature.changer_statut(payload.statut, payload.commentaires)
    db.commit()
    db.refresh(candidature)

    return success(
        CandidatureResponse.model_validate(candidature),
        f"Statut mis à jour : {payload.statut.value}"
    )


@router.put("/{candidature_id}")
def update_candidature(
    candidature_id: uuid.UUID,
    payload: CandidatureUpdate,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Met à jour complète une candidature (statut, commentaires, évaluations).

    **Permissions :** Recruteur ou Admin RH.
    """
    _check_recruteur_or_admin(user)
    candidature = _get_candidature_or_404(db, candidature_id, user.entreprise_id)

    if payload.statut:
        candidature.changer_statut(payload.statut, payload.commentaires)

    if payload.evaluation_technique:
        candidature.evaluation_technique = payload.evaluation_technique

    if payload.entretien_notes:
        candidature.entretien_notes = payload.entretien_notes

    db.commit()
    db.refresh(candidature)

    return success(
        CandidatureResponse.model_validate(candidature),
        "Candidature mise à jour avec succès."
    )


@router.post("/bulk/statut")
def bulk_update_statut(
    payload: CandidatureBulkUpdate,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Met à jour le statut de plusieurs candidatures en une fois.

    **Permissions :** Recruteur ou Admin RH.
    """
    _check_recruteur_or_admin(user)

    # Récupérer toutes les candidatures
    candidatures = (
        db.query(Candidature)
        .join(Offre)
        .join(Campagne)
        .filter(
            Candidature.id.in_(payload.candidature_ids),
            Campagne.entreprise_id == user.entreprise_id,
            Candidature.deleted_at.is_(None)
        )
        .all()
    )

    if len(candidatures) != len(payload.candidature_ids):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Certaines candidatures sont introuvables."
        )

    # Mettre à jour
    for candidature in candidatures:
        candidature.changer_statut(payload.statut, payload.commentaires)

    db.commit()

    return success(
        message=f"{len(candidatures)} candidatures mises à jour."
    )


# ==========================================================
# Actions spécifiques
# ==========================================================

@router.post("/{candidature_id}/preselectionner")
def preselectionner_candidature(
    candidature_id: uuid.UUID,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Présélectionne une candidature."""
    _check_recruteur_or_admin(user)
    candidature = _get_candidature_or_404(db, candidature_id, user.entreprise_id)
    candidature.presélectionner()
    db.commit()
    db.refresh(candidature)
    return success(
        CandidatureResponse.model_validate(candidature),
        "Candidature présélectionnée."
    )


@router.post("/{candidature_id}/refuser")
def refuser_candidature(
    candidature_id: uuid.UUID,
    motif: str = Query(..., min_length=1, max_length=500),
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Refuse une candidature avec un motif."""
    _check_recruteur_or_admin(user)
    candidature = _get_candidature_or_404(db, candidature_id, user.entreprise_id)
    candidature.refuser(motif)
    db.commit()
    db.refresh(candidature)
    return success(
        CandidatureResponse.model_validate(candidature),
        "Candidature refusée."
    )


@router.post("/{candidature_id}/embaucher")
def embaucher_candidature(
    candidature_id: uuid.UUID,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Valide l'embauche d'un candidat."""
    _check_recruteur_or_admin(user)
    candidature = _get_candidature_or_404(db, candidature_id, user.entreprise_id)
    candidature.embaucher()
    db.commit()
    db.refresh(candidature)
    return success(
        CandidatureResponse.model_validate(candidature),
        "Candidat embauché !"
    )


@router.post("/{candidature_id}/vivier")
def mettre_en_vivier(
    candidature_id: uuid.UUID,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Place une candidature en vivier de talents."""
    _check_recruteur_or_admin(user)
    candidature = _get_candidature_or_404(db, candidature_id, user.entreprise_id)
    candidature.mettre_en_vivier()
    db.commit()
    db.refresh(candidature)
    return success(
        CandidatureResponse.model_validate(candidature),
        "Candidature ajoutée au vivier de talents."
    )
