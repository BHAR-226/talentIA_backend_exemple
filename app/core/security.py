"""Primitives de sécurité : hachage de mot de passe (bcrypt) et jetons JWT.

Le jeton est un JWT signé HS256. Il n'est JAMAIS renvoyé au client dans le corps
de la réponse ni stocké côté JS : il est déposé dans un cookie httpOnly (voir
`app/auth/cookies.py`), conformément à la décision de sécurité du projet.
"""

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

import bcrypt
import jwt

from app.core.config import settings

ALGORITHM = "HS256"


# ==========================================================
# Hachage de mot de passe
# ==========================================================

def hash_password(password: str) -> str:
    """
    Hache un mot de passe avec bcrypt.
    
    Args:
        password: Mot de passe en clair
        
    Returns:
        str: Mot de passe haché
    """
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """
    Vérifie un mot de passe par rapport à son hash.
    
    Args:
        password: Mot de passe en clair
        hashed: Hash du mot de passe
        
    Returns:
        bool: True si le mot de passe correspond
    """
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def is_password_strong(password: str) -> bool:
    """
    Vérifie si un mot de passe est assez fort.
    
    Critères:
    - Au moins 8 caractères
    - Au moins une lettre majuscule
    - Au moins une lettre minuscule
    - Au moins un chiffre
    - Au moins un caractère spécial
    
    Args:
        password: Mot de passe à vérifier
        
    Returns:
        bool: True si le mot de passe est fort
    """
    if len(password) < 8:
        return False
    if not any(c.isupper() for c in password):
        return False
    if not any(c.islower() for c in password):
        return False
    if not any(c.isdigit() for c in password):
        return False
    if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        return False
    return True


# ==========================================================
# Génération de tokens
# ==========================================================

def generate_secure_token(length: int = 32) -> str:
    """
    Génère un token sécurisé aléatoire.
    
    Args:
        length: Longueur du token
        
    Returns:
        str: Token sécurisé
    """
    return secrets.token_urlsafe(length)


def generate_otp(length: int = 6) -> str:
    """
    Génère un code OTP numérique.
    
    Args:
        length: Longueur du code
        
    Returns:
        str: Code OTP
    """
    return ''.join(secrets.choice('0123456789') for _ in range(length))


# ==========================================================
# JWT - Tokens d'accès
# ==========================================================

def create_access_token(
    subject: str,
    *,
    type_compte: str,
    nom: str,
    role: Optional[str] = None,
    entreprise_id: Optional[str] = None,
    additional_claims: Optional[dict[str, Any]] = None,
) -> str:
    """
    Crée un JWT pour un compte (`subject` = id).

    `type_compte` vaut "utilisateur" (interne, avec rôle + entreprise) ou
    "candidat". Le rôle et l'entreprise ne concernent que les utilisateurs.

    Args:
        subject: ID du compte
        type_compte: Type de compte ("utilisateur" ou "candidat")
        nom: Nom de l'utilisateur
        role: Rôle (uniquement pour les utilisateurs)
        entreprise_id: ID de l'entreprise (uniquement pour les utilisateurs)
        additional_claims: Claims supplémentaires à ajouter

    Returns:
        str: JWT encodé
    """
    expire = datetime.now(UTC) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    
    payload: dict[str, Any] = {
        "sub": subject,
        "type": type_compte,
        "nom": nom,
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    
    if role:
        payload["role"] = role
    if entreprise_id:
        payload["entreprise_id"] = entreprise_id
    if additional_claims:
        payload.update(additional_claims)
    
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Décode/valide un JWT.
    
    Args:
        token: JWT à décoder
        
    Returns:
        dict: Payload décodé
        
    Raises:
        jwt.PyJWTError: Si le token est invalide ou expiré
    """
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])


def refresh_access_token(token: str) -> str:
    """
    Rafraîchit un token d'accès.
    
    Args:
        token: Ancien token à rafraîchir
        
    Returns:
        str: Nouveau token
        
    Raises:
        jwt.PyJWTError: Si le token est invalide
    """
    payload = decode_access_token(token)
    # Supprimer l'ancienne expiration
    payload.pop("exp", None)
    # Créer un nouveau token avec les mêmes claims
    return create_access_token(
        subject=payload["sub"],
        type_compte=payload["type"],
        nom=payload["nom"],
        role=payload.get("role"),
        entreprise_id=payload.get("entreprise_id"),
    )


def get_token_expiration(token: str) -> Optional[datetime]:
    """
    Récupère la date d'expiration d'un token.
    
    Args:
        token: JWT à examiner
        
    Returns:
        Optional[datetime]: Date d'expiration ou None
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[ALGORITHM],
            options={"verify_exp": False}
        )
        exp = payload.get("exp")
        if exp:
            return datetime.fromtimestamp(exp, tz=UTC)
        return None
    except jwt.PyJWTError:
        return None


def is_token_expired(token: str) -> bool:
    """
    Vérifie si un token est expiré.
    
    Args:
        token: JWT à vérifier
        
    Returns:
        bool: True si le token est expiré
    """
    exp = get_token_expiration(token)
    if exp is None:
        return True
    return datetime.now(UTC) > exp


# ==========================================================
# JWT - Tokens de vérification d'email
# ==========================================================

def create_email_verification_token(subject: str, *, type_compte: str) -> str:
    """
    Jeton à usage unique pour confirmer une adresse email à l'inscription.

    Distinct du JWT de session (`purpose` dédié, durée de vie courte) : même
    signé avec la même clé, il ne peut pas servir à s'authentifier sur l'API.

    Args:
        subject: ID du compte
        type_compte: Type de compte ("utilisateur" ou "candidat")

    Returns:
        str: Jeton de vérification
    """
    expire = datetime.now(UTC) + timedelta(
        minutes=settings.email_verification_expire_minutes
    )
    payload = {
        "sub": subject,
        "type": type_compte,
        "purpose": "verify_email",
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_email_verification_token(token: str) -> dict[str, Any]:
    """
    Décode un jeton de vérification d'email et vérifie qu'il a le bon usage.
    
    Args:
        token: Jeton à décoder
        
    Returns:
        dict: Payload décodé
        
    Raises:
        jwt.InvalidTokenError: Si le jeton est invalide ou n'a pas le bon usage
    """
    payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    if payload.get("purpose") != "verify_email":
        raise jwt.InvalidTokenError("Jeton invalide pour cet usage.")
    return payload


# ==========================================================
# JWT - Tokens de réinitialisation de mot de passe
# ==========================================================

def create_password_reset_token(subject: str, *, type_compte: str) -> str:
    """
    Crée un jeton de réinitialisation de mot de passe.
    
    Args:
        subject: ID du compte
        type_compte: Type de compte ("utilisateur" ou "candidat")
        
    Returns:
        str: Jeton de réinitialisation
    """
    expire = datetime.now(UTC) + timedelta(
        minutes=settings.email_verification_expire_minutes
    )
    payload = {
        "sub": subject,
        "type": type_compte,
        "purpose": "reset_password",
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_password_reset_token(token: str) -> dict[str, Any]:
    """
    Décode un jeton de réinitialisation de mot de passe.
    
    Args:
        token: Jeton à décoder
        
    Returns:
        dict: Payload décodé
        
    Raises:
        jwt.InvalidTokenError: Si le jeton est invalide ou n'a pas le bon usage
    """
    payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    if payload.get("purpose") != "reset_password":
        raise jwt.InvalidTokenError("Jeton invalide pour cet usage.")
    return payload


# ==========================================================
# Validation et vérification
# ==========================================================

def validate_token_type(token: str, expected_type: str) -> bool:
    """
    Vérifie le type d'un token.
    
    Args:
        token: JWT à vérifier
        expected_type: Type attendu ("access", "verify_email", "reset_password")
        
    Returns:
        bool: True si le token est du bon type
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[ALGORITHM],
            options={"verify_exp": False}
        )
        purpose = payload.get("purpose")
        if expected_type == "access":
            return purpose is None
        return purpose == expected_type
    except jwt.PyJWTError:
        return False


def get_user_id_from_token(token: str) -> Optional[str]:
    """
    Extrait l'ID utilisateur d'un token sans vérifier l'expiration.
    
    Args:
        token: JWT à décoder
        
    Returns:
        Optional[str]: ID utilisateur ou None
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[ALGORITHM],
            options={"verify_exp": False}
        )
        return payload.get("sub")
    except jwt.PyJWTError:
        return None