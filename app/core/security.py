"""Primitives de sécurité : hachage de mot de passe (bcrypt) et jetons JWT.

Le jeton est un JWT signé HS256. Il n'est JAMAIS renvoyé au client dans le corps
de la réponse ni stocké côté JS : il est déposé dans un cookie httpOnly (voir
`app/auth/cookies.py`), conformément à la décision de sécurité du projet.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.core.config import settings

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def create_access_token(
    subject: str,
    *,
    type_compte: str,
    nom: str,
    role: str | None = None,
    entreprise_id: str | None = None,
) -> str:
    """Crée un JWT pour un compte (`subject` = id).

    `type_compte` vaut "utilisateur" (interne, avec rôle + entreprise) ou
    "candidat". Le rôle et l'entreprise ne concernent que les utilisateurs.
    """
    expire = datetime.now(UTC) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "type": type_compte,
        "nom": nom,
        "role": role,
        "entreprise_id": entreprise_id,
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Décode/valide un JWT. Lève `jwt.PyJWTError` si invalide ou expiré."""
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
