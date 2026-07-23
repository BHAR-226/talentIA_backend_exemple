"""Endpoints d'authentification (Lot 1 — Azaël, étoffé par Tangara).

Ouvre/ferme une session via un **cookie httpOnly** portant un JWT. Gère les deux
profils du formulaire d'inscription : `candidat` (entité `Candidat`) et
`recruteur` (entité `Utilisateur` rattachée à une `Entreprise`).

Sécurité (Tangara) :
  - **Vérification d'email obligatoire** avant toute connexion
  - **Approbation admin_rh obligatoire** pour un recruteur qui rejoint une
    entreprise EXISTANTE
  - **Anti brute-force** basique sur `/auth/login`
  - **Entreprise suspendue** → connexion refusée pour tous ses membres
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import CurrentIdentity, get_current_identity
from app.auth.cookies import clear_auth_cookie, set_auth_cookie
from app.core import rate_limit
from app.core.database import get_db
from app.core.emailing import envoyer_email_verification
from app.core.enums import (
    PlanAbonnement,
    RoleUtilisateur,
    StatutAbonnement,
    StatutEntreprise,
)
from app.core.responses import success
from app.core.security import (
    create_access_token,
    create_email_verification_token,
    decode_email_verification_token,
    hash_password,
    verify_password,
)
from app.models.abonnement import Abonnement
from app.models.audit import AuditLog
from app.models.candidat import Candidat
from app.models.entreprise import Entreprise
from app.models.utilisateur import Utilisateur
from app.schemas.auth import (
    IdentityResponse,
    LoginRequest,
    RegisterRequest,
    ResendVerificationRequest,
)

# Durée de l'essai gratuit offert à chaque nouvelle entreprise (CDC §4).
DUREE_ESSAI_JOURS = 30

router = APIRouter(prefix="/auth", tags=["auth"])


def _identity_from_user(user: Utilisateur) -> IdentityResponse:
    """Convertit un utilisateur en réponse d'identité."""
    return IdentityResponse(
        id=str(user.id),
        type="utilisateur",
        nom=user.nom,
        email=user.email,
        role=user.role,
        entreprise_id=str(user.entreprise_id),
        email_verifie=user.email_verifie,
        actif=user.actif,
    )


def _identity_from_candidat(candidat: Candidat) -> IdentityResponse:
    """Convertit un candidat en réponse d'identité."""
    return IdentityResponse(
        id=str(candidat.id),
        type="candidat",
        nom=candidat.nom,
        email=candidat.email,
        email_verifie=candidat.email_verifie,
        actif=True,
    )


# ==========================================================
# Inscription
# ==========================================================

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Crée un nouveau compte (candidat ou recruteur) et envoie un email de confirmation.
    
    **Candidat** : Compte créé immédiatement, email de vérification envoyé.
    
    **Recruteur** :
    - Nouvelle entreprise → Devient admin RH, compte actif immédiatement
    - Entreprise existante → Devient recruteur, en attente de validation admin RH
    """
    if payload.profil == "candidat":
        return _register_candidat(payload, db)
    return _register_recruteur(payload, request, db)


def _register_candidat(payload: RegisterRequest, db: Session):
    """Inscription d'un candidat."""
    if db.query(Candidat).filter(Candidat.email == payload.email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Cet email a déjà un compte.")
    
    candidat = Candidat(
        nom=payload.nom,
        email=payload.email,
        mot_de_passe_hash=hash_password(payload.mot_de_passe),
    )
    db.add(candidat)
    db.commit()
    db.refresh(candidat)

    token = create_email_verification_token(str(candidat.id), type_compte="candidat")
    envoyer_email_verification(candidat.email, candidat.nom, token)
    
    # Audit log
    audit = AuditLog.create_log(
        table_name="candidats",
        record_id=candidat.id,
        action="CREATE",
        user_email=candidat.email,
        changes={"nom": candidat.nom, "email": candidat.email}
    )
    db.add(audit)
    db.commit()
    
    return success(
        _identity_from_candidat(candidat),
        "Compte créé. Vérifiez votre boîte mail pour confirmer votre inscription.",
    )


def _register_recruteur(payload: RegisterRequest, request: Request, db: Session):
    """Inscription d'un recruteur."""
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
    
    if entreprise is None:
        # Nouvelle entreprise → Admin RH + essai gratuit
        entreprise = Entreprise(nom=nom_ent)
        db.add(entreprise)
        db.flush()
        
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
        actif = True
        message = "Compte créé. Vérifiez votre boîte mail pour l'activer."
    else:
        # Entreprise existante → Recruteur, en attente de validation
        role = RoleUtilisateur.recruteur
        actif = False
        message = (
            "Compte créé. Vérifiez votre boîte mail, puis attendez la validation "
            "d'un administrateur RH de votre entreprise."
        )

    user = Utilisateur(
        entreprise_id=entreprise.id,
        nom=payload.nom,
        email=payload.email,
        mot_de_passe_hash=hash_password(payload.mot_de_passe),
        role=role,
        actif=actif,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_email_verification_token(str(user.id), type_compte="utilisateur")
    envoyer_email_verification(user.email, user.nom, token)
    
    # Audit log
    audit = AuditLog.create_log(
        table_name="utilisateurs",
        record_id=user.id,
        action="CREATE",
        user_email=user.email,
        changes={
            "nom": user.nom,
            "email": user.email,
            "role": user.role.value,
            "entreprise": nom_ent
        }
    )
    db.add(audit)
    db.commit()
    
    return success(_identity_from_user(user), message)


# ==========================================================
# Vérification d'email
# ==========================================================

@router.get("/verify-email")
def verify_email(
    token: str,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Confirme l'adresse email depuis le lien envoyé à l'inscription.
    
    Si le compte est utilisable (actif), la session est ouverte directement.
    Un recruteur en attente de validation admin reste bloqué.
    """
    try:
        payload = decode_email_verification_token(token)
    except jwt.PyJWTError:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Lien de vérification invalide ou expiré."
        ) from None

    sub = payload.get("sub")
    type_compte = payload.get("type")

    if type_compte == "candidat":
        candidat = db.get(Candidat, UUID(sub))
        if candidat is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Compte introuvable.")
        
        candidat.email_verifie = True
        db.commit()
        db.refresh(candidat)
        
        token_session = create_access_token(
            str(candidat.id),
            type_compte="candidat",
            nom=candidat.nom
        )
        set_auth_cookie(response, token_session)
        return success(
            _identity_from_candidat(candidat),
            "Email confirmé. Bienvenue !"
        )

    user = db.get(Utilisateur, UUID(sub))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Compte introuvable.")
    
    user.email_verifie = True
    db.commit()
    db.refresh(user)

    if not user.actif:
        return success(
            _identity_from_user(user),
            "Email confirmé. Votre compte attend la validation d'un administrateur RH.",
        )

    token_session = create_access_token(
        str(user.id),
        type_compte="utilisateur",
        nom=user.nom,
        role=user.role.value,
        entreprise_id=str(user.entreprise_id),
    )
    set_auth_cookie(response, token_session)
    return success(_identity_from_user(user), "Email confirmé. Bienvenue !")


@router.post("/resend-verification")
def resend_verification(
    payload: ResendVerificationRequest,
    db: Session = Depends(get_db)
):
    """
    Renvoie le lien de confirmation d'email.
    
    Réponse volontairement identique que le compte existe ou non,
    pour ne pas révéler quels emails sont inscrits.
    """
    message = "Si un compte existe pour cet email, un lien de confirmation a été envoyé."

    user = db.query(Utilisateur).filter(Utilisateur.email == payload.email).first()
    if user and not user.email_verifie:
        token = create_email_verification_token(str(user.id), type_compte="utilisateur")
        envoyer_email_verification(user.email, user.nom, token)
        return success(message=message)

    candidat = db.query(Candidat).filter(Candidat.email == payload.email).first()
    if candidat and not candidat.email_verifie:
        token = create_email_verification_token(str(candidat.id), type_compte="candidat")
        envoyer_email_verification(candidat.email, candidat.nom, token)

    return success(message=message)


# ==========================================================
# Connexion / Déconnexion
# ==========================================================

@router.post("/login")
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Connecte un utilisateur ou un candidat.
    
    Vérifications :
    - Email vérifié
    - Compte actif
    - Entreprise non suspendue (pour les utilisateurs internes)
    - Rate limiting anti-brute force
    """
    # Vérifier le rate limiting
    blocage_restant = rate_limit.verifier_non_bloque(payload.email)
    if blocage_restant is not None:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Trop de tentatives échouées. Réessayez dans {int(blocage_restant // 60) + 1} min.",
        )

    # Tentative de connexion utilisateur
    user = db.query(Utilisateur).filter(Utilisateur.email == payload.email).first()
    if user and user.mot_de_passe_hash and verify_password(
        payload.mot_de_passe, user.mot_de_passe_hash
    ):
        return _login_user(user, response, db)

    # Tentative de connexion candidat
    candidat = db.query(Candidat).filter(Candidat.email == payload.email).first()
    if candidat and candidat.mot_de_passe_hash and verify_password(
        payload.mot_de_passe, candidat.mot_de_passe_hash
    ):
        return _login_candidat(candidat, response, db)

    # Échec
    rate_limit.enregistrer_echec(payload.email)
    raise HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Email ou mot de passe incorrect."
    )


def _login_user(user: Utilisateur, response: Response, db: Session):
    """Connecte un utilisateur interne."""
    if not user.email_verifie:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Email non confirmé. Vérifiez votre boîte mail.",
        )
    
    if not user.actif:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Compte désactivé ou en attente de validation par un administrateur.",
        )
    
    if user.entreprise.statut == StatutEntreprise.suspendue:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Entreprise suspendue."
        )

    rate_limit.reinitialiser(user.email)
    token = create_access_token(
        str(user.id),
        type_compte="utilisateur",
        nom=user.nom,
        role=user.role.value,
        entreprise_id=str(user.entreprise_id),
    )
    set_auth_cookie(response, token)
    
    user.update_last_login()
    db.commit()
    
    return success(_identity_from_user(user), "Connexion réussie.")


def _login_candidat(candidat: Candidat, response: Response, db: Session):
    """Connecte un candidat."""
    if not candidat.email_verifie:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Email non confirmé. Vérifiez votre boîte mail.",
        )
    
    rate_limit.reinitialiser(candidat.email)
    token = create_access_token(
        str(candidat.id),
        type_compte="candidat",
        nom=candidat.nom
    )
    set_auth_cookie(response, token)
    return success(_identity_from_candidat(candidat), "Connexion réussie.")


@router.post("/logout")
def logout(response: Response):
    """Déconnecte l'utilisateur en supprimant le cookie de session."""
    clear_auth_cookie(response)
    return success(message="Déconnexion réussie.")


# ==========================================================
# Profil
# ==========================================================

@router.get("/me")
def me(
    identity: CurrentIdentity = Depends(get_current_identity),
    db: Session = Depends(get_db),
):
    """
    Récupère l'identité de la session courante.
    
    Recharge les données depuis la base pour avoir les informations à jour.
    """
    if identity.type == "utilisateur":
        user = db.get(Utilisateur, identity.id)
        if user is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Compte introuvable.")
        return success(_identity_from_user(user))

    candidat = db.get(Candidat, identity.id)
    if candidat is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Compte introuvable.")
    return success(_identity_from_candidat(candidat))