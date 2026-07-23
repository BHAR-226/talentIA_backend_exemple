"""Profil candidat (self-service) + upload de CV.

Le CV est **optionnel** : un candidat peut s'inscrire sans CV et l'ajouter/
le remplacer à tout moment ensuite via `POST /candidats/cv`.
"""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_candidat
from app.core.config import settings
from app.core.database import get_db
from app.core.responses import success
from app.core.security import hash_password, verify_password
from app.core.validators import validate_file_upload
from app.models.candidat import Candidat
from app.schemas.candidat import (
    CandidatProfilUpdate,
    CandidatResponse,
    ChangerMotDePasseCandidatRequest,
)

router = APIRouter(prefix="/candidats", tags=["candidats"])


# ==========================================================
# Profil candidat
# ==========================================================

@router.get("/me")
def mon_profil(candidat: Candidat = Depends(get_current_candidat)):
    """
    Récupère le profil du candidat connecté.
    
    **Accessible uniquement aux comptes candidat.**
    """
    return success(CandidatResponse.model_validate(candidat))


@router.put("/me")
def modifier_mon_profil(
    payload: CandidatProfilUpdate,
    candidat: Candidat = Depends(get_current_candidat),
    db: Session = Depends(get_db),
):
    """
    Modifie le profil du candidat connecté.
    
    **Champs modifiables :**
    - nom, téléphone, titre, expérience, localisation
    - LinkedIn, portfolio, disponibilité, préavis
    - Relocalisation, permis de conduire
    
    **Restriction :** L'email ne peut pas être modifié ici.
    """
    for champ, valeur in payload.model_dump(exclude_unset=True).items():
        setattr(candidat, champ, valeur)
    
    db.commit()
    db.refresh(candidat)
    return success(
        CandidatResponse.model_validate(candidat),
        "Profil mis à jour avec succès."
    )


@router.put("/me/mot-de-passe")
def changer_mon_mot_de_passe(
    payload: ChangerMotDePasseCandidatRequest,
    candidat: Candidat = Depends(get_current_candidat),
    db: Session = Depends(get_db),
):
    """
    Change le mot de passe du candidat connecté.
    
    **Nécessite :** L'ancien mot de passe pour confirmation.
    """
    if not candidat.mot_de_passe_hash or not verify_password(
        payload.mot_de_passe_actuel, candidat.mot_de_passe_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Mot de passe actuel incorrect."
        )
    
    candidat.mot_de_passe_hash = hash_password(payload.nouveau_mot_de_passe)
    db.commit()
    return success(message="Mot de passe mis à jour avec succès.")


# ==========================================================
# Gestion du CV
# ==========================================================

@router.post("/cv", status_code=status.HTTP_201_CREATED)
async def uploader_cv(
    cv: UploadFile = File(...),
    candidat: Candidat = Depends(get_current_candidat),
    db: Session = Depends(get_db),
):
    """
    Ajoute ou remplace le CV du candidat connecté.
    
    **Formats acceptés :** PDF, DOC, DOCX
    **Taille maximale :** 5 Mo (configurable)
    """
    # Lire et valider le fichier
    contenu = await cv.read()
    try:
        file_info = validate_file_upload(cv.filename or "unknown", contenu)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        ) from e

    # Créer le dossier de stockage
    dossier = Path(settings.cv_upload_dir)
    dossier.mkdir(parents=True, exist_ok=True)

    # Supprimer l'ancien fichier
    if candidat.cv_url:
        ancien = Path(settings.cv_upload_dir) / Path(candidat.cv_url).name
        ancien.unlink(missing_ok=True)

    # Sauvegarder le nouveau fichier
    nom_fichier = f"{uuid.uuid4()}{file_info['extension']}"
    chemin_fichier = dossier / nom_fichier
    chemin_fichier.write_bytes(contenu)

    # Mettre à jour l'URL du CV
    candidat.cv_url = f"/static/cv/{nom_fichier}"
    db.commit()
    db.refresh(candidat)
    
    return success(
        CandidatResponse.model_validate(candidat),
        f"CV enregistré avec succès ({file_info['extension']}, {file_info['size'] // 1024} KB)."
    )


@router.get("/cv")
def obtenir_cv(
    candidat: Candidat = Depends(get_current_candidat),
):
    """
    Récupère l'URL du CV du candidat connecté.
    
    **Retourne :** L'URL du CV ou `null` si aucun CV n'est uploadé.
    """
    return success({
        "cv_url": candidat.cv_url,
        "a_upload_cv": candidat.a_upload_cv
    })


@router.delete("/cv")
def supprimer_cv(
    candidat: Candidat = Depends(get_current_candidat),
    db: Session = Depends(get_db),
):
    """
    Supprime le CV du candidat connecté.
    """
    if candidat.cv_url:
        ancien = Path(settings.cv_upload_dir) / Path(candidat.cv_url).name
        ancien.unlink(missing_ok=True)
        candidat.cv_url = None
        db.commit()
        db.refresh(candidat)
    
    return success(message="CV supprimé avec succès.")


# ==========================================================
# Statistiques du candidat
# ==========================================================

@router.get("/me/stats")
def stats_candidat(
    candidat: Candidat = Depends(get_current_candidat),
    db: Session = Depends(get_db),
):
    """
    Statistiques du candidat connecté.
    
    **Statistiques retournées :**
    - Nombre total de candidatures
    - Nombre de candidatures par statut
    - Dernière candidature
    - Profil complété
    """
    from collections import Counter
    
    # Compter les candidatures par statut
    stats_par_statut = Counter(c.statut.value for c in candidat.candidatures if not c.is_deleted)
    
    # Dernière candidature
    derniere_candidature = None
    if candidat.candidatures:
        derniere = max(candidat.candidatures, key=lambda c: c.created_at)
        derniere_candidature = {
            "id": str(derniere.id),
            "statut": derniere.statut.value,
            "date": derniere.created_at,
            "offre_titre": derniere.offre.titre if derniere.offre else None
        }
    
    # Vérifier si le profil est complet
    profil_complet = all([
        candidat.nom,
        candidat.telephone,
        candidat.titre_principal,
        candidat.annees_experience is not None,
        candidat.localisation,
    ])
    
    stats = {
        "nombre_candidatures": candidat.nombre_candidatures,
        "stats_par_statut": dict(stats_par_statut),
        "derniere_candidature": derniere_candidature,
        "profil_complet": profil_complet,
        "a_upload_cv": candidat.a_upload_cv,
        "email_verifie": candidat.email_verifie,
    }
    
    return success(stats)