"""Endpoints d'authentification (Lot 1 — Azaël).

Ouvre/ferme une session via un **cookie httpOnly** portant un JWT. Gère les deux
profils du formulaire d'inscription : `candidat` (entité `Candidat`) et
`recruteur` (entité `Utilisateur` rattachée à une `Entreprise`).
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import CurrentIdentity, get_current_identity
from app.auth.cookies import clear_auth_cookie, set_auth_cookie
from app.core.database import get_db
from app.core.enums import PlanAbonnement, RoleUtilisateur, StatutAbonnement
from app.core.responses import success
from app.core.security import create_access_token, hash_password, verify_password
from app.models.abonnement import Abonnement
from app.models.candidat import Candidat
from app.models.entreprise import Entreprise
from app.models.utilisateur import Utilisateur
from app.schemas.auth import IdentityResponse, LoginRequest, RegisterRequest

# Durée de l'essai gratuit offert à chaque nouvelle entreprise (CDC §4).
DUREE_ESSAI_JOURS = 30

router = APIRouter(prefix="/auth", tags=["auth"])


def _identity_from_user(user: Utilisateur) -> IdentityResponse:
    return IdentityResponse(
        id=str(user.id),
        type="utilisateur",
        nom=user.nom,
        email=user.email,
        role=user.role,
        entreprise_id=str(user.entreprise_id),
    )


def _identity_from_candidat(candidat: Candidat) -> IdentityResponse:
    return IdentityResponse(
        id=str(candidat.id),
        type="candidat",
        nom=candidat.nom,
        email=candidat.email,
    )


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    if payload.profil == "candidat":
        exists = db.query(Candidat).filter(Candidat.email == payload.email).first()
        if exists:
            raise HTTPException(status.HTTP_409_CONFLICT, "Cet email a déjà un compte.")
        candidat = Candidat(
            nom=payload.nom,
            email=payload.email,
            mot_de_passe_hash=hash_password(payload.mot_de_passe),
        )
        db.add(candidat)
        db.commit()
        db.refresh(candidat)
        token = create_access_token(
            str(candidat.id), type_compte="candidat", nom=candidat.nom
        )
        set_auth_cookie(response, token)
        return success(_identity_from_candidat(candidat), "Compte candidat créé.")

    # profil == "recruteur"
    if not payload.nom_entreprise or not payload.nom_entreprise.strip():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Le nom de l'entreprise est requis pour un recruteur.",
        )
    if db.query(Utilisateur).filter(Utilisateur.email == payload.email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Cet email a déjà un compte.")

    nom_ent = payload.nom_entreprise.strip()
    entreprise = (
        db.query(Entreprise)
        .filter(func.lower(Entreprise.nom) == nom_ent.lower())
        .first()
    )
    # Entreprise inconnue → créée, et l'utilisateur en devient l'admin RH.
    if entreprise is None:
        entreprise = Entreprise(nom=nom_ent)
        db.add(entreprise)
        db.flush()
        # Nouvelle entreprise → essai gratuit Starter de 30 jours.
        maintenant = datetime.now(UTC)
        db.add(
            Abonnement(
                entreprise_id=entreprise.id,
                plan=PlanAbonnement.starter,
                statut=StatutAbonnement.essai,
                date_debut=maintenant,
                date_fin=maintenant + timedelta(days=DUREE_ESSAI_JOURS),
            )
        )
        role = RoleUtilisateur.admin_rh
    else:
        role = RoleUtilisateur.recruteur

    user = Utilisateur(
        entreprise_id=entreprise.id,
        nom=payload.nom,
        email=payload.email,
        mot_de_passe_hash=hash_password(payload.mot_de_passe),
        role=role,
        actif=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(
        str(user.id),
        type_compte="utilisateur",
        nom=user.nom,
        role=user.role.value,
        entreprise_id=str(user.entreprise_id),
    )
    set_auth_cookie(response, token)
    return success(_identity_from_user(user), "Compte créé.")


@router.post("/login")
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(Utilisateur).filter(Utilisateur.email == payload.email).first()
    if user and user.mot_de_passe_hash and verify_password(
        payload.mot_de_passe, user.mot_de_passe_hash
    ):
        if not user.actif:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Compte désactivé.")
        token = create_access_token(
            str(user.id),
            type_compte="utilisateur",
            nom=user.nom,
            role=user.role.value,
            entreprise_id=str(user.entreprise_id),
        )
        set_auth_cookie(response, token)
        return success(_identity_from_user(user), "Connexion réussie.")

    candidat = db.query(Candidat).filter(Candidat.email == payload.email).first()
    if candidat and candidat.mot_de_passe_hash and verify_password(
        payload.mot_de_passe, candidat.mot_de_passe_hash
    ):
        token = create_access_token(
            str(candidat.id), type_compte="candidat", nom=candidat.nom
        )
        set_auth_cookie(response, token)
        return success(_identity_from_candidat(candidat), "Connexion réussie.")

    raise HTTPException(
        status.HTTP_401_UNAUTHORIZED, "Email ou mot de passe incorrect."
    )


@router.post("/logout")
def logout(response: Response):
    clear_auth_cookie(response)
    return success(message="Déconnexion réussie.")


@router.get("/me")
def me(
    identity: CurrentIdentity = Depends(get_current_identity),
    db: Session = Depends(get_db),
):
    """Identité de la session courante (recharge l'email depuis la base)."""
    if identity.type == "utilisateur":
        user = db.get(Utilisateur, identity.id)
        if user is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Compte introuvable.")
        return success(_identity_from_user(user))

    candidat = db.get(Candidat, identity.id)
    if candidat is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Compte introuvable.")
    return success(_identity_from_candidat(candidat))
