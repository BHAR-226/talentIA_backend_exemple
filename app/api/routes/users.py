"""CRUD Utilisateurs — gestion de l'équipe d'une entreprise (Tangara).

Réservé à l'**admin_rh** du tenant pour la gestion de l'équipe (créer, lister,
éditer, désactiver/supprimer un membre). Toujours scopé à `entreprise_id` de
l'admin RH connecté.

`/users/me` est ouvert à TOUT utilisateur interne connecté : chacun peut
consulter et éditer son propre profil (nom, email, mot de passe) — jamais
son propre rôle ni son statut `actif`.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.core.emailing import envoyer_email_verification
from app.core.enums import RoleUtilisateur
from app.core.plans import get_plan_limits
from app.core.responses import success
from app.core.security import (
    create_email_verification_token,
    hash_password,
    verify_password,
)
from app.models.abonnement import Abonnement
from app.models.audit import AuditLog
from app.models.utilisateur import Utilisateur
from app.schemas.utilisateur import (
    ChangerMotDePasseRequest,
    ProfilUtilisateurUpdate,
    UtilisateurCreate,
    UtilisateurResponse,
    UtilisateurUpdate,
)

router = APIRouter(prefix="/users", tags=["users"])

ROLES_ATTRIBUABLES = (
    RoleUtilisateur.recruteur,
    RoleUtilisateur.admin_rh,
    RoleUtilisateur.evaluateur_technique,
)

_require_admin_rh = require_roles(RoleUtilisateur.admin_rh)


# ==========================================================
# Fonctions utilitaires
# ==========================================================

def _get_ou_404(db: Session, entreprise_id: uuid.UUID, user_id: uuid.UUID) -> Utilisateur:
    """Récupère un utilisateur de l'entreprise ou lève une 404."""
    membre = (
        db.query(Utilisateur)
        .filter(
            Utilisateur.id == user_id,
            Utilisateur.entreprise_id == entreprise_id,
            Utilisateur.deleted_at.is_(None)  # Soft delete
        )
        .first()
    )
    if membre is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable."
        )
    return membre


def _est_dernier_admin_rh_actif(
    db: Session, entreprise_id: uuid.UUID, exclure_id: uuid.UUID
) -> bool:
    """Vérifie si l'utilisateur est le dernier admin RH actif."""
    autres_admins = (
        db.query(Utilisateur)
        .filter(
            Utilisateur.entreprise_id == entreprise_id,
            Utilisateur.role == RoleUtilisateur.admin_rh,
            Utilisateur.actif.is_(True),
            Utilisateur.id != exclure_id,
            Utilisateur.deleted_at.is_(None)
        )
        .count()
    )
    return autres_admins == 0


def _verifier_changement_email(user: Utilisateur, nouvel_email: str, db: Session) -> None:
    """Vérifie les contraintes liées au changement d'email."""
    if nouvel_email != user.email:
        if db.query(Utilisateur).filter(Utilisateur.email == nouvel_email).first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cet email a déjà un compte."
            )
        # Changer d'email exige une nouvelle vérification
        user.email_verifie = False
        token = create_email_verification_token(str(user.id), type_compte="utilisateur")
        envoyer_email_verification(nouvel_email, user.nom, token)


# ==========================================================
# Profil personnel (tout utilisateur interne)
# ==========================================================

@router.get("/me")
def mon_profil(user: Utilisateur = Depends(get_current_user)):
    """Récupère le profil de l'utilisateur connecté."""
    return success(UtilisateurResponse.model_validate(user))


@router.put("/me")
def modifier_mon_profil(
    payload: ProfilUtilisateurUpdate,
    request: Request,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Édite son propre profil (nom, email, téléphone, fonction).
    
    **Restrictions :** 
    - Ne peut pas modifier son rôle
    - Ne peut pas modifier son statut `actif`
    - Changer d'email redemande une vérification
    """
    donnees = payload.model_dump(exclude_unset=True)

    # Vérifier le changement d'email
    if "email" in donnees:
        _verifier_changement_email(user, donnees["email"], db)

    # Mettre à jour les champs
    for champ, valeur in donnees.items():
        setattr(user, champ, valeur)

    db.commit()
    db.refresh(user)
    return success(
        UtilisateurResponse.model_validate(user),
        "Profil mis à jour avec succès."
    )


@router.put("/me/mot-de-passe")
def changer_mon_mot_de_passe(
    payload: ChangerMotDePasseRequest,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change son mot de passe (nécessite l'ancien mot de passe)."""
    if not verify_password(payload.mot_de_passe_actuel, user.mot_de_passe_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Mot de passe actuel incorrect."
        )

    user.mot_de_passe_hash = hash_password(payload.nouveau_mot_de_passe)
    db.commit()
    return success(message="Mot de passe mis à jour avec succès.")


# ==========================================================
# Gestion de l'équipe (admin_rh)
# ==========================================================

@router.get("")
def lister_utilisateurs(
    admin: Utilisateur = Depends(_require_admin_rh),
    db: Session = Depends(get_db),
):
    """Liste tous les membres de l'équipe (entreprise de l'admin RH).
    
    **Permissions :** Admin RH uniquement.
    """
    membres = (
        db.query(Utilisateur)
        .filter(
            Utilisateur.entreprise_id == admin.entreprise_id,
            Utilisateur.deleted_at.is_(None)
        )
        .order_by(Utilisateur.nom)
        .all()
    )
    return success([UtilisateurResponse.model_validate(m) for m in membres])


@router.post("", status_code=status.HTTP_201_CREATED)
def creer_utilisateur(
    payload: UtilisateurCreate,
    admin: Utilisateur = Depends(_require_admin_rh),
    db: Session = Depends(get_db),
):
    """Ajoute un membre à l'équipe (même entreprise que l'admin RH).
    
    Le compte est `actif` immédiatement, mais un email de confirmation est
    envoyé : la connexion reste bloquée tant que l'email n'est pas vérifié.
    
    **Permissions :** Admin RH uniquement.
    """
    # Vérifier le rôle
    if payload.role not in ROLES_ATTRIBUABLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Rôle non attribuable. Rôles autorisés : {', '.join(r.value for r in ROLES_ATTRIBUABLES)}"
        )

    # Vérifier le quota de recruteurs du plan d'abonnement
    if payload.role == RoleUtilisateur.recruteur:
        abonnement = (
            db.query(Abonnement)
            .filter(Abonnement.entreprise_id == admin.entreprise_id)
            .first()
        )
        if abonnement is not None:
            limite_recruteurs = get_plan_limits(abonnement.plan).get("recruteurs")
            if limite_recruteurs is not None:
                nb_recruteurs_actifs = (
                    db.query(Utilisateur)
                    .filter(
                        Utilisateur.entreprise_id == admin.entreprise_id,
                        Utilisateur.role == RoleUtilisateur.recruteur,
                        Utilisateur.actif.is_(True),
                        Utilisateur.deleted_at.is_(None),
                    )
                    .count()
                )
                if nb_recruteurs_actifs >= limite_recruteurs:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=(
                            f"Quota de recruteurs atteint pour le plan '{abonnement.plan.value}' "
                            f"({limite_recruteurs} maximum). Passez à un plan supérieur pour "
                            "ajouter des recruteurs."
                        )
                    )

    # Vérifier l'email
    if db.query(Utilisateur).filter(Utilisateur.email == payload.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cet email a déjà un compte."
        )

    # Créer l'utilisateur
    membre = Utilisateur(
        entreprise_id=admin.entreprise_id,
        nom=payload.nom,
        email=payload.email,
        mot_de_passe_hash=hash_password(payload.mot_de_passe),
        role=payload.role,
        actif=True,
        telephone=payload.telephone,
        fonction=payload.fonction,
    )
    db.add(membre)
    db.commit()
    db.refresh(membre)

    # Envoyer email de vérification
    token = create_email_verification_token(str(membre.id), type_compte="utilisateur")
    envoyer_email_verification(membre.email, membre.nom, token)

    # Audit log
    audit = AuditLog.create_log(
        table_name="utilisateurs",
        record_id=membre.id,
        action="CREATE",
        user_id=admin.id,
        user_email=admin.email,
        changes={
            "nom": membre.nom,
            "email": membre.email,
            "role": membre.role.value,
            "telephone": membre.telephone,
            "fonction": membre.fonction
        }
    )
    db.add(audit)
    db.commit()

    return success(
        UtilisateurResponse.model_validate(membre),
        "Utilisateur créé. Un email de confirmation lui a été envoyé.",
    )


@router.get("/{user_id}")
def get_utilisateur(
    user_id: uuid.UUID,
    admin: Utilisateur = Depends(_require_admin_rh),
    db: Session = Depends(get_db),
):
    """Récupère un membre de l'équipe par son ID.
    
    **Permissions :** Admin RH uniquement.
    """
    membre = _get_ou_404(db, admin.entreprise_id, user_id)
    return success(UtilisateurResponse.model_validate(membre))


@router.put("/{user_id}")
def update_utilisateur(
    user_id: uuid.UUID,
    payload: UtilisateurUpdate,
    admin: Utilisateur = Depends(_require_admin_rh),
    db: Session = Depends(get_db),
):
    """Édite un membre de l'équipe (nom, email, rôle, activation).
    
    C'est ICI qu'un admin RH approuve un recruteur resté en attente
    après son inscription sur une entreprise existante (`actif: true`).
    
    **Permissions :** Admin RH uniquement.
    """
    membre = _get_ou_404(db, admin.entreprise_id, user_id)
    donnees = payload.model_dump(exclude_unset=True)

    # Vérifier le rôle
    if "role" in donnees and donnees["role"] not in ROLES_ATTRIBUABLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Rôle non attribuable. Rôles autorisés : {', '.join(r.value for r in ROLES_ATTRIBUABLES)}"
        )

    # Vérifier le changement d'email
    if "email" in donnees:
        _verifier_changement_email(membre, donnees["email"], db)

    # Vérifier les garde-fous
    desactivation = donnees.get("actif") is False
    retrogradation = "role" in donnees and donnees["role"] != RoleUtilisateur.admin_rh

    if membre.id == admin.id:
        if desactivation:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Impossible de désactiver son propre compte."
            )
        if retrogradation:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Impossible de changer son propre rôle d'admin RH."
            )
    elif membre.role == RoleUtilisateur.admin_rh and (desactivation or retrogradation):
        if _est_dernier_admin_rh_actif(db, admin.entreprise_id, exclure_id=membre.id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Impossible : c'est le dernier admin RH actif de l'entreprise."
            )

    # Mettre à jour les champs
    for champ, valeur in donnees.items():
        setattr(membre, champ, valeur)

    db.commit()
    db.refresh(membre)

    # Audit log
    audit = AuditLog.create_log(
        table_name="utilisateurs",
        record_id=membre.id,
        action="UPDATE",
        user_id=admin.id,
        user_email=admin.email,
        changes=donnees
    )
    db.add(audit)
    db.commit()

    return success(
        UtilisateurResponse.model_validate(membre),
        "Utilisateur mis à jour avec succès."
    )


@router.delete("/{user_id}")
def supprimer_utilisateur(
    user_id: uuid.UUID,
    admin: Utilisateur = Depends(_require_admin_rh),
    db: Session = Depends(get_db),
):
    """Supprime un membre de l'équipe (soft delete).
    
    Pour un simple départ ou une suspension temporaire, préférer
    `PUT /users/{id}` avec `actif: false`.
    
    **Permissions :** Admin RH uniquement.
    """
    membre = _get_ou_404(db, admin.entreprise_id, user_id)

    # Vérifier les garde-fous
    if membre.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de supprimer son propre compte."
        )

    if membre.role == RoleUtilisateur.admin_rh and _est_dernier_admin_rh_actif(
        db, admin.entreprise_id, exclure_id=membre.id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible : c'est le dernier admin RH actif de l'entreprise."
        )

    # Soft delete
    membre.soft_delete(admin.id)
    db.commit()

    # Audit log
    audit = AuditLog.create_log(
        table_name="utilisateurs",
        record_id=membre.id,
        action="DELETE",
        user_id=admin.id,
        user_email=admin.email,
        changes={"deleted_by": str(admin.id)}
    )
    db.add(audit)
    db.commit()

    return success(message="Utilisateur supprimé avec succès.")


# ==========================================================
# Routes de gestion des rôles (admin RH)
# ==========================================================

@router.post("/{user_id}/promouvoir/admin-rh")
def promouvoir_admin_rh(
    user_id: uuid.UUID,
    admin: Utilisateur = Depends(_require_admin_rh),
    db: Session = Depends(get_db),
):
    """Promeut un utilisateur au rôle Admin RH.
    
    **Permissions :** Admin RH uniquement.
    """
    membre = _get_ou_404(db, admin.entreprise_id, user_id)

    if membre.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous êtes déjà Admin RH."
        )

    membre.promouvoir_admin_rh()
    db.commit()
    db.refresh(membre)

    return success(
        UtilisateurResponse.model_validate(membre),
        f"{membre.nom} promu Admin RH avec succès."
    )


@router.post("/{user_id}/promouvoir/recruteur")
def promouvoir_recruteur(
    user_id: uuid.UUID,
    admin: Utilisateur = Depends(_require_admin_rh),
    db: Session = Depends(get_db),
):
    """Promeut un utilisateur au rôle Recruteur.
    
    **Permissions :** Admin RH uniquement.
    """
    membre = _get_ou_404(db, admin.entreprise_id, user_id)
    membre.promouvoir_recruteur()
    db.commit()
    db.refresh(membre)

    return success(
        UtilisateurResponse.model_validate(membre),
        f"{membre.nom} promu Recruteur avec succès."
    )


@router.post("/{user_id}/promouvoir/evaluateur")
def promouvoir_evaluateur(
    user_id: uuid.UUID,
    admin: Utilisateur = Depends(_require_admin_rh),
    db: Session = Depends(get_db),
):
    """Promeut un utilisateur au rôle Évaluateur Technique.
    
    **Permissions :** Admin RH uniquement.
    """
    membre = _get_ou_404(db, admin.entreprise_id, user_id)
    membre.promouvoir_evaluateur_technique()
    db.commit()
    db.refresh(membre)

    return success(
        UtilisateurResponse.model_validate(membre),
        f"{membre.nom} promu Évaluateur Technique avec succès."
    )
