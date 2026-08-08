"""Validateurs personnalisés pour les données."""

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import settings

# ==========================================================
# Validateurs d'email
# ==========================================================

# Liste des domaines d'emails jetables
BLOCKED_EMAIL_DOMAINS = [
    'tempmail.com', '10minutemail.com', 'guerrillamail.com',
    'mailinator.com', 'trashmail.com', 'temp-mail.org',
    'yopmail.com', 'throwawaymail.com', 'mailnesia.com',
    'spamgourmet.com', 'guerrillamail.net', 'mailsac.com',
]

# Liste des domaines d'emails professionnels autorisés
ALLOWED_EMAIL_DOMAINS = [
    'gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com',
    'protonmail.com', 'proton.me', 'icloud.com',
]


def validate_email_domain(
    email: str,
    blocked_domains: list[str] | None = None,
    allow_empty: bool = False
) -> str:
    """Valide le domaine d'un email et bloque les domaines jetables.

    Args:
        email: Adresse email à valider
        blocked_domains: Liste des domaines bloqués (optionnel)
        allow_empty: Permettre un email vide (défaut: False)

    Returns:
        str: Email validé

    Raises:
        ValueError: Si le domaine est bloqué
    """
    if not email and allow_empty:
        return email

    if not email:
        raise ValueError("L'email est requis")

    if '@' not in email:
        raise ValueError("Format d'email invalide")

    if blocked_domains is None:
        blocked_domains = BLOCKED_EMAIL_DOMAINS

    domain = email.split('@')[1].lower()

    if domain in blocked_domains:
        raise ValueError(f"Domaine email non autorisé: {domain}")

    return email


def validate_email_format(email: str) -> bool:
    """Vérifie le format d'un email avec une expression régulière.

    Args:
        email: Adresse email à vérifier

    Returns:
        bool: True si le format est valide
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


# ==========================================================
# Validateur de téléphone
# ==========================================================

def validate_phone(phone: str) -> str:
    """Valide un numéro de téléphone.

    Args:
        phone: Numéro de téléphone à valider

    Returns:
        str: Numéro validé

    Raises:
        ValueError: Si le format est invalide
    """
    if not phone:
        return phone

    # Nettoyer le numéro
    cleaned = re.sub(r'[\s\-\(\)]', '', phone)

    # Format international ou local
    pattern = r'^[\+\d][\d]{8,15}$'
    if not re.match(pattern, cleaned):
        raise ValueError("Format de téléphone invalide. Utilisez le format international (+33...)")

    return phone


# ==========================================================
# Validateur de date
# ==========================================================

def validate_date(date_str: str, format: str = '%Y-%m-%d') -> datetime:
    """Valide une date au format spécifié.

    Args:
        date_str: Chaîne de date à valider
        format: Format attendu (défaut: YYYY-MM-DD)

    Returns:
        datetime: Date validée

    Raises:
        ValueError: Si le format est invalide
    """
    try:
        return datetime.strptime(date_str, format)
    except ValueError as e:
        raise ValueError(f"Format de date invalide. Format attendu: {format}") from e


# ==========================================================
# Validateur de champs personnalisés
# ==========================================================

def validate_custom_fields(
    values: dict[str, Any],
    field_definitions: list[dict[str, Any]]
) -> dict[str, Any]:
    """Valide les réponses aux champs personnalisés d'une offre.

    Args:
        values: Réponses du candidat
        field_definitions: Définitions des champs personnalisés

    Returns:
        Dict: Valeurs validées

    Raises:
        ValueError: Si une validation échoue
    """
    for field_def in field_definitions:
        field_name = field_def.get('libelle')
        field_type = field_def.get('type')
        required = field_def.get('obligatoire', False)
        options = field_def.get('options', [])
        max_length = field_def.get('max_length', 500)
        min_value = field_def.get('min_value')
        max_value = field_def.get('max_value')

        value = values.get(field_name)

        # Vérifier les champs obligatoires
        if required and (value is None or value == "" or value == []):
            raise ValueError(f"Le champ '{field_name}' est obligatoire")

        # Ignorer les champs vides non obligatoires
        if value is None or value == "" or value == []:
            continue

        # Valider selon le type
        if field_type == 'texte':
            if not isinstance(value, str):
                raise ValueError(f"'{field_name}' doit être du texte")
            if len(value) > max_length:
                raise ValueError(f"'{field_name}' trop long (max {max_length} caractères)")

        elif field_type == 'nombre':
            if not isinstance(value, int | float):
                raise ValueError(f"'{field_name}' doit être un nombre")
            if min_value is not None and value < min_value:
                raise ValueError(f"'{field_name}' doit être supérieur ou égal à {min_value}")
            if max_value is not None and value > max_value:
                raise ValueError(f"'{field_name}' doit être inférieur ou égal à {max_value}")
            if value < 0:
                raise ValueError(f"'{field_name}' doit être positif")

        elif field_type == 'date':
            pattern = r'^\d{4}-\d{2}-\d{2}$'
            if not re.match(pattern, str(value)):
                raise ValueError(f"'{field_name}' doit être une date (YYYY-MM-DD)")

        elif field_type == 'choix':
            if value not in options:
                raise ValueError(f"'{field_name}' valeur non autorisée. Choix: {', '.join(options)}")

        elif field_type == 'choix_multiple':
            if not isinstance(value, list):
                raise ValueError(f"'{field_name}' doit être une liste")
            if required and not value:
                raise ValueError(f"'{field_name}' doit contenir au moins une valeur")
            for item in value:
                if item not in options:
                    raise ValueError(f"'{field_name}' valeur non autorisée: {item}")

        elif field_type == 'boolean':
            if not isinstance(value, bool):
                raise ValueError(f"'{field_name}' doit être un booléen (true/false)")

        elif field_type == 'email':
            try:
                validate_email_domain(str(value))
            except ValueError as e:
                raise ValueError(f"'{field_name}' {str(e)}") from e

    return values


# ==========================================================
# Validateur de fichier uploadé
# ==========================================================

def validate_file_upload(filename: str, content: bytes) -> dict[str, Any]:
    """Valide un fichier uploadé (CV, etc.).

    Args:
        filename: Nom du fichier
        content: Contenu du fichier en bytes

    Returns:
        Dict: Informations sur le fichier validé (extension, mime_type, size)

    Raises:
        ValueError: Si la validation échoue
    """
    # Vérifier l'extension
    ext = Path(filename).suffix.lower()
    if ext not in settings.cv_allowed_extensions:
        raise ValueError(
            f"Format non supporté. Formats acceptés: {', '.join(settings.cv_allowed_extensions)}"
        )

    # Vérifier la taille
    max_size = settings.cv_max_size_mb * 1024 * 1024
    if len(content) > max_size:
        raise ValueError(
            f"Fichier trop volumineux (max {settings.cv_max_size_mb} Mo)"
        )

    if len(content) == 0:
        raise ValueError("Le fichier est vide")

    # Vérifier le MIME type
    mime_type = None
    try:
        import magic
        mime_type = magic.from_buffer(content[:1024], mime=True)
        if mime_type not in settings.cv_allowed_mime_types:
            raise ValueError(f"Type MIME non autorisé: {mime_type}")
    except ImportError:
        pass  # magic non installé, on ignore cette vérification

    return {
        'extension': ext,
        'mime_type': mime_type,
        'size': len(content),
        'size_kb': round(len(content) / 1024, 2),
        'size_mb': round(len(content) / (1024 * 1024), 2),
    }


# ==========================================================
# Validateur d'URL
# ==========================================================

def validate_url(url: str) -> str:
    """Valide une URL.

    Args:
        url: URL à valider

    Returns:
        str: URL validée

    Raises:
        ValueError: Si l'URL est invalide
    """
    if not url:
        return url

    pattern = r'^https?://[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}(/.*)?$'
    if not re.match(pattern, url):
        raise ValueError("URL invalide")

    return url


# ==========================================================
# Validateur de mot de passe
# ==========================================================

def validate_password(password: str, min_length: int = 8) -> str:
    """Valide un mot de passe selon des critères de sécurité.

    Args:
        password: Mot de passe à valider
        min_length: Longueur minimale (défaut: 8)

    Returns:
        str: Mot de passe validé

    Raises:
        ValueError: Si le mot de passe ne respecte pas les critères
    """
    if len(password) < min_length:
        raise ValueError(f"Le mot de passe doit contenir au moins {min_length} caractères")

    if not any(c.isupper() for c in password):
        raise ValueError("Le mot de passe doit contenir au moins une majuscule")

    if not any(c.islower() for c in password):
        raise ValueError("Le mot de passe doit contenir au moins une minuscule")

    if not any(c.isdigit() for c in password):
        raise ValueError("Le mot de passe doit contenir au moins un chiffre")

    if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        raise ValueError("Le mot de passe doit contenir au moins un caractère spécial")

    return password


# ==========================================================
# Validateur de code postal
# ==========================================================

def validate_postal_code(code: str, country: str = "FR") -> str:
    """Valide un code postal.

    Args:
        code: Code postal à valider
        country: Pays (défaut: FR)

    Returns:
        str: Code postal validé

    Raises:
        ValueError: Si le code postal est invalide
    """
    if not code:
        return code

    patterns = {
        "FR": r'^\d{5}$',
        "BE": r'^\d{4}$',
        "CH": r'^\d{4}$',
        "CA": r'^[A-Z]\d[A-Z] ?\d[A-Z]\d$',
        "US": r'^\d{5}(-\d{4})?$',
    }

    pattern = patterns.get(country.upper(), r'^\d{5}$')

    if not re.match(pattern, code):
        raise ValueError(f"Format de code postal invalide pour {country}")

    return code
