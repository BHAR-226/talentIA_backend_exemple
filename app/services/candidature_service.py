"""Services métier des candidatures.

Toute la logique métier est centralisée ici :
- création
- consultation
- changement de statut
- validation des champs personnalisés
- évaluations
"""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.enums import StatutCandidature
from app.core.validators import validate_custom_fields as core_validate_custom_fields
from app.models.candidat import Candidat
from app.models.candidature import Candidature
from app.models.offre import Offre

logger = logging.getLogger("talentia.candidature_service")


# ==========================================================
# Lecture
# ==========================================================

def get(db: Session, candidature_id: UUID) -> Candidature | None:
    """Retourne une candidature par son identifiant.
    """
    return (
        db.query(Candidature)
        .filter(
            Candidature.id == candidature_id,
            Candidature.deleted_at.is_(None)
        )
        .first()
    )


def get_with_relations(db: Session, candidature_id: UUID) -> Candidature | None:
    """Retourne une candidature avec ses relations (offre, candidat).
    """
    return (
        db.query(Candidature)
        .filter(
            Candidature.id == candidature_id,
            Candidature.deleted_at.is_(None)
        )
        .first()
    )


def list_by_candidat(
    db: Session,
    candidat_id: UUID,
    statut: StatutCandidature | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> list[Candidature]:
    """Retourne toutes les candidatures d'un candidat.
    
    Args:
        db: Session SQLAlchemy
        candidat_id: ID du candidat
        statut: Filtrer par statut (optionnel)
        limit: Nombre maximum de résultats (optionnel)
        offset: Offset pour la pagination (optionnel)
    """
    query = db.query(Candidature).filter(
        Candidature.candidat_id == candidat_id,
        Candidature.deleted_at.is_(None)
    )

    if statut:
        query = query.filter(Candidature.statut == statut)

    query = query.order_by(Candidature.date_soumission.desc())

    if offset:
        query = query.offset(offset)
    if limit:
        query = query.limit(limit)

    return query.all()


def list_by_offre(
    db: Session,
    offre_id: UUID,
    statut: StatutCandidature | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> list[Candidature]:
    """Retourne toutes les candidatures d'une offre.
    
    Args:
        db: Session SQLAlchemy
        offre_id: ID de l'offre
        statut: Filtrer par statut (optionnel)
        limit: Nombre maximum de résultats (optionnel)
        offset: Offset pour la pagination (optionnel)
    """
    query = db.query(Candidature).filter(
        Candidature.offre_id == offre_id,
        Candidature.deleted_at.is_(None)
    )

    if statut:
        query = query.filter(Candidature.statut == statut)

    query = query.order_by(Candidature.date_soumission.desc())

    if offset:
        query = query.offset(offset)
    if limit:
        query = query.limit(limit)

    return query.all()


def count_by_offre(db: Session, offre_id: UUID) -> int:
    """Compte le nombre de candidatures pour une offre."""
    return (
        db.query(Candidature)
        .filter(
            Candidature.offre_id == offre_id,
            Candidature.deleted_at.is_(None)
        )
        .count()
    )


def count_by_statut(db: Session, statut: StatutCandidature) -> int:
    """Compte le nombre de candidatures par statut."""
    return (
        db.query(Candidature)
        .filter(
            Candidature.statut == statut,
            Candidature.deleted_at.is_(None)
        )
        .count()
    )


# ==========================================================
# Validation des champs personnalisés
# ==========================================================

def validate_custom_fields(
    answers: dict[str, Any],
    definitions: list[dict[str, Any]],
) -> None:
    """Vérifie que les réponses du candidat respectent
    les champs personnalisés définis sur l'offre.

    Args:
        answers: Réponses du candidat
        definitions: Définitions des champs personnalisés

    Raises:
        ValueError: Si une validation échoue
    """
    try:
        core_validate_custom_fields(answers, definitions)
    except Exception as e:
        raise ValueError(f"Validation des champs personnalisés échouée: {str(e)}") from e


# ==========================================================
# Création
# ==========================================================

def create(
    db: Session,
    *,
    offre: Offre,
    candidat_id: UUID,
    lettre_motivation: str | None = None,
    cv_url: str | None = None,
    champs_personnalises: dict[str, Any] | None = None,
) -> Candidature:
    """Crée une nouvelle candidature.

    Args:
        db: Session SQLAlchemy
        offre: Offre à laquelle postuler
        candidat_id: ID du candidat
        lettre_motivation: Lettre de motivation (optionnel)
        cv_url: URL du CV (optionnel)
        champs_personnalises: Réponses aux champs personnalisés (optionnel)

    Returns:
        Candidature: La candidature créée

    Raises:
        ValueError: Si la validation échoue
    """
    if champs_personnalises is None:
        champs_personnalises = {}

    # Valider les champs personnalisés
    if offre.champs_personnalises_def:
        validate_custom_fields(champs_personnalises, offre.champs_personnalises_def)

    # Vérifier que le candidat existe
    candidat = db.get(Candidat, candidat_id)
    if not candidat:
        raise ValueError(f"Candidat {candidat_id} non trouvé")

    # Vérifier que le candidat n'a pas déjà postulé
    existing = (
        db.query(Candidature)
        .filter(
            Candidature.offre_id == offre.id,
            Candidature.candidat_id == candidat_id,
            Candidature.deleted_at.is_(None)
        )
        .first()
    )
    if existing:
        raise ValueError(f"Le candidat a déjà postulé à l'offre {offre.id}")

    # Créer la candidature
    candidature = Candidature(
        offre_id=offre.id,
        candidat_id=candidat_id,
        statut=StatutCandidature.recue,
        lettre_motivation=lettre_motivation,
        cv_url=cv_url,
        champs_personnalises=champs_personnalises,
        score_global=None,
        evaluation_ia=None,
    )

    db.add(candidature)
    db.commit()
    db.refresh(candidature)

    logger.info(f"✅ Candidature créée: {candidature.id} pour l'offre {offre.id}")

    return candidature


# ==========================================================
# Mise à jour
# ==========================================================

def update_statut(
    db: Session,
    candidature: Candidature,
    statut: StatutCandidature,
    commentaire: str | None = None,
) -> Candidature:
    """Met à jour le statut d'une candidature.

    Args:
        db: Session SQLAlchemy
        candidature: Candidature à mettre à jour
        statut: Nouveau statut
        commentaire: Commentaire optionnel

    Returns:
        Candidature: La candidature mise à jour
    """
    ancien_statut = candidature.statut

    # Utiliser la méthode du modèle
    candidature.changer_statut(statut, commentaire)

    db.commit()
    db.refresh(candidature)

    logger.info(
        f"🔄 Statut candidature {candidature.id} mis à jour: "
        f"{ancien_statut.value} → {statut.value}"
    )

    return candidature


def update_evaluation_ia(
    db: Session,
    candidature: Candidature,
    score: int,
    evaluation: dict[str, Any],
) -> Candidature:
    """Met à jour l'évaluation IA d'une candidature.

    Args:
        db: Session SQLAlchemy
        candidature: Candidature à mettre à jour
        score: Score global (0-100)
        evaluation: Détails de l'évaluation

    Returns:
        Candidature: La candidature mise à jour
    """
    candidature.score_global = score
    candidature.evaluation_ia = evaluation

    db.commit()
    db.refresh(candidature)

    logger.info(f"🤖 Évaluation IA mise à jour pour {candidature.id}: score {score}")

    return candidature


def update_commentaires(
    db: Session,
    candidature: Candidature,
    commentaires: str,
) -> Candidature:
    """Met à jour les commentaires d'une candidature.

    Args:
        db: Session SQLAlchemy
        candidature: Candidature à mettre à jour
        commentaires: Nouveaux commentaires

    Returns:
        Candidature: La candidature mise à jour
    """
    candidature.commentaires = commentaires

    db.commit()
    db.refresh(candidature)

    return candidature


# ==========================================================
# Suppression (soft delete)
# ==========================================================

def delete(
    db: Session,
    candidature: Candidature,
    user_id: UUID,
) -> bool:
    """Supprime logiquement une candidature.

    Args:
        db: Session SQLAlchemy
        candidature: Candidature à supprimer
        user_id: ID de l'utilisateur qui supprime

    Returns:
        bool: True si la suppression a réussi
    """
    candidature.soft_delete(user_id)
    db.commit()

    logger.info(f"🗑️ Candidature {candidature.id} supprimée par {user_id}")

    return True


# ==========================================================
# Statistiques
# ==========================================================

def get_stats_by_offre(db: Session, offre_id: UUID) -> dict[str, Any]:
    """Retourne les statistiques des candidatures pour une offre.

    Args:
        db: Session SQLAlchemy
        offre_id: ID de l'offre

    Returns:
        Dict: Statistiques (total, par statut, taux conversion)
    """
    candidatures = list_by_offre(db, offre_id)

    total = len(candidatures)

    # Statistiques par statut
    stats_par_statut = {}
    for statut in StatutCandidature:
        count = sum(1 for c in candidatures if c.statut == statut)
        if count > 0:
            stats_par_statut[statut.value] = count

    # Taux de conversion
    embauches = stats_par_statut.get(StatutCandidature.embauche.value, 0)
    taux_conversion = round((embauches / total) * 100, 2) if total > 0 else 0

    return {
        "total": total,
        "stats_par_statut": stats_par_statut,
        "embauches": embauches,
        "taux_conversion": taux_conversion,
    }


def get_stats_by_candidat(db: Session, candidat_id: UUID) -> dict[str, Any]:
    """Retourne les statistiques des candidatures pour un candidat.

    Args:
        db: Session SQLAlchemy
        candidat_id: ID du candidat

    Returns:
        Dict: Statistiques (total, par statut)
    """
    candidatures = list_by_candidat(db, candidat_id)

    total = len(candidatures)

    # Statistiques par statut
    stats_par_statut = {}
    for statut in StatutCandidature:
        count = sum(1 for c in candidatures if c.statut == statut)
        if count > 0:
            stats_par_statut[statut.value] = count

    return {
        "total": total,
        "stats_par_statut": stats_par_statut,
    }


# ==========================================================
# Actions en masse (bulk operations)
# ==========================================================

def bulk_update_statut(
    db: Session,
    candidature_ids: list[UUID],
    statut: StatutCandidature,
    commentaire: str | None = None,
) -> int:
    """Met à jour le statut de plusieurs candidatures.

    Args:
        db: Session SQLAlchemy
        candidature_ids: Liste des IDs des candidatures
        statut: Nouveau statut
        commentaire: Commentaire optionnel

    Returns:
        int: Nombre de candidatures mises à jour
    """
    candidatures = (
        db.query(Candidature)
        .filter(
            Candidature.id.in_(candidature_ids),
            Candidature.deleted_at.is_(None)
        )
        .all()
    )

    count = 0
    for candidature in candidatures:
        candidature.changer_statut(statut, commentaire)
        count += 1

    db.commit()

    logger.info(f"🔄 {count} candidatures mises à jour en statut {statut.value}")

    return count
