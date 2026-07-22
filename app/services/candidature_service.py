"""
Services métier des candidatures.

Toute la logique métier est centralisée ici :

- création
- consultation
- changement de statut
- validation des champs personnalisés
"""

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.enums import StatutCandidature
from app.models.candidature import Candidature
from app.models.offre import Offre

# ==========================================================
# Lecture
# ==========================================================


def get(
    db: Session,
    candidature_id: UUID,
) -> Candidature | None:
    """
    Retourne une candidature par son identifiant.
    """

    return (
        db.query(Candidature)
        .filter(Candidature.id == candidature_id)
        .first()
    )



def list_by_candidat(
    db: Session,
    candidat_id: UUID,
) -> list[Candidature]:
    """
    Retourne toutes les candidatures d'un candidat.
    """

    return (
        db.query(Candidature)
        .filter(Candidature.candidat_id == candidat_id)
        .order_by(Candidature.date_soumission.desc())
        .all()
    )



def list_by_offre(
    db: Session,
    offre_id: UUID,
) -> list[Candidature]:
    """
    Retourne toutes les candidatures d'une offre.
    """

    return (
        db.query(Candidature)
        .filter(Candidature.offre_id == offre_id)
        .order_by(Candidature.date_soumission.desc())
        .all()
    )


# ==========================================================
# Validation champs personnalisés
# ==========================================================


def validate_custom_fields(
    answers: dict[str, Any],
    definitions: list[dict[str, Any]],
) -> None:
    """
    Vérifie que les réponses du candidat respectent
    les champs personnalisés définis sur l'offre.

    Exemple :

    definitions:
    [
        {
            "nom": "experience",
            "obligatoire": True
        }
    ]

    answers:
    {
        "experience": "2 ans"
    }
    """

    for field in definitions:

        name = field.get("nom")

        if not name:
            continue

        required = field.get(
            "obligatoire",
            False,
        )

        if required and name not in answers:
            raise ValueError(
                f"Le champ obligatoire '{name}' est manquant."
            )



# ==========================================================
# Création
# ==========================================================


def create(
    db: Session,
    *,
    offre: Offre,
    candidat_id: UUID,
    lettre_motivation: str | None,
    cv_url: str | None,
    champs_personnalises: dict[str, Any],
) -> Candidature:
    """
    Crée une nouvelle candidature.
    """

    validate_custom_fields(
        champs_personnalises,
        offre.champs_personnalises_def,
    )


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

    return candidature



# ==========================================================
# Mise à jour
# ==========================================================


def update_statut(
    db: Session,
    candidature: Candidature,
    statut: StatutCandidature,
) -> Candidature:
    """
    Met à jour le statut d'une candidature.
    """

    candidature.statut = statut

    db.commit()
    db.refresh(candidature)

    return candidature