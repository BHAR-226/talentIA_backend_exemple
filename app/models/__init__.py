"""Modèles SQLAlchemy. Importés ici pour que `Base.metadata` les connaisse
tous (indispensable à l'autogénération Alembic)."""

from app.models.abonnement import Abonnement
from app.models.campagne import Campagne
from app.models.candidat import Candidat
from app.models.candidature import Candidature
from app.models.entreprise import Entreprise
from app.models.offre import Offre
from app.models.utilisateur import Utilisateur

__all__ = [
    "Entreprise",
    "Utilisateur",
    "Abonnement",
    "Campagne",
    "Offre",
    "Candidat",
    "Candidature",
]
